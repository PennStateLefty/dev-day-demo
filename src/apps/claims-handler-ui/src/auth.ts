import type { AccountInfo } from "@azure/msal-browser";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export interface Session {
  mode: "local" | "azure";
  signedIn: boolean;
  signIn(): Promise<void>;
  signOut(): Promise<void>;
  request(path: string, options?: RequestInit): Promise<Response>;
}

const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;

export async function initializeSession(): Promise<Session> {
  const response = await fetch(`${API_BASE}/auth-config`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Authentication configuration failed (${response.status}).`);
  const configuration: unknown = await response.json();
  if (typeof configuration !== "object" || configuration === null || !("mode" in configuration)) {
    throw new Error("Invalid authentication configuration; no local fallback was used.");
  }
  if (configuration.mode === "local") {
    return {
      mode: "local",
      signedIn: true,
      async signIn() {},
      async signOut() {},
      request: (path, options) => fetch(`${API_BASE}${path}`, options),
    };
  }
  if (
    configuration.mode !== "azure" ||
    !("tenantId" in configuration) || typeof configuration.tenantId !== "string" ||
    !UUID.test(configuration.tenantId) ||
    !("clientId" in configuration) || typeof configuration.clientId !== "string" ||
    !UUID.test(configuration.clientId) ||
    !("scope" in configuration) || typeof configuration.scope !== "string" ||
    !/^api:\/\/[a-f0-9-]{36}\/claims\.invoke$/i.test(configuration.scope)
  ) {
    throw new Error("Invalid Azure authentication configuration; no local fallback was used.");
  }
  if (window.location.protocol !== "https:") {
    throw new Error("Azure sign-in requires HTTPS.");
  }
  const redirectUri = `${window.location.origin}/`;
  const scopes = [configuration.scope];
  const { InteractionRequiredAuthError, PublicClientApplication } =
    await import("@azure/msal-browser");
  const client = new PublicClientApplication({
    auth: {
      clientId: configuration.clientId,
      authority: `https://login.microsoftonline.com/${configuration.tenantId}`,
      redirectUri,
      postLogoutRedirectUri: redirectUri,
      navigateToLoginRequestUrl: false,
    },
    cache: { cacheLocation: "sessionStorage" },
  });
  await client.initialize();
  const redirect = await client.handleRedirectPromise();
  const accounts = client.getAllAccounts();
  const account: AccountInfo | null =
    redirect?.account ?? client.getActiveAccount() ?? (accounts.length === 1 ? accounts[0] : null);
  client.setActiveAccount(account);

  return {
    mode: "azure",
    signedIn: account !== null,
    signIn: () => client.loginRedirect({ scopes, prompt: "select_account" }),
    signOut: () => client.logoutRedirect({ account: client.getActiveAccount() }),
    async request(path, options) {
      // Never attach an access token to arbitrary URLs or follow API redirects.
      if (!path.startsWith("/api/") || path.startsWith("//")) {
        throw new Error("Only same-API business paths can receive a bearer token.");
      }
      const current = client.getActiveAccount();
      if (!current) throw new Error("Sign in before requesting claims data.");
      let accessToken: string;
      try {
        const result = await client.acquireTokenSilent({ scopes, account: current });
        accessToken = result.accessToken;
      } catch (error) {
        if (error instanceof InteractionRequiredAuthError) {
          throw new Error("Your session needs renewed consent or sign-in. Sign out and sign in again.");
        }
        throw error;
      }
      const headers = new Headers(options?.headers);
      headers.set("Authorization", `Bearer ${accessToken}`);
      return fetch(`${API_BASE}${path}`, { ...options, headers, redirect: "error" });
    },
  };
}

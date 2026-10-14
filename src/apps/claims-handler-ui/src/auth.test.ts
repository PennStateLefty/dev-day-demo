import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE, initializeSession } from "./auth";

const client = vi.hoisted(() => ({
  initialize: vi.fn(),
  handleRedirectPromise: vi.fn(),
  getAllAccounts: vi.fn(),
  getActiveAccount: vi.fn(),
  setActiveAccount: vi.fn(),
  loginRedirect: vi.fn(),
  logoutRedirect: vi.fn(),
  acquireTokenSilent: vi.fn(),
}));
const construct = vi.hoisted(() => vi.fn());
vi.mock("@azure/msal-browser", () => ({
  PublicClientApplication: class {
    constructor(configuration: unknown) {
      construct(configuration);
      return client;
    }
  },
  InteractionRequiredAuthError: class extends Error {},
}));

const config = {
  mode: "azure",
  tenantId: "00000000-0000-0000-0000-000000000001",
  clientId: "00000000-0000-0000-0000-000000000002",
  scope: "api://00000000-0000-0000-0000-000000000003/claims.invoke",
};
const account = { homeAccountId: "synthetic-test-account" };
let fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.resetAllMocks();
  fetchMock = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("window", {
    location: { protocol: "https:", origin: "https://demo.example" },
  });
  fetchMock.mockResolvedValue(new Response(JSON.stringify(config)));
  client.initialize.mockResolvedValue(undefined);
  client.handleRedirectPromise.mockResolvedValue(null);
  client.getAllAccounts.mockReturnValue([]);
  client.getActiveAccount.mockReturnValue(null);
});
afterEach(() => vi.unstubAllGlobals());

describe("runtime browser authentication", () => {
  it("keeps explicit local mode token-free", async () => {
    fetchMock.mockResolvedValueOnce(new Response('{"mode":"local"}'));
    const session = await initializeSession();
    expect(session.signedIn).toBe(true);
    await session.request("/api/claims");
    expect(fetchMock).toHaveBeenLastCalledWith(`${API_BASE}/api/claims`, undefined);
    expect(construct).not.toHaveBeenCalled();
  });

  it.each([{}, { mode: "unknown" }, configWith("tenantId", "common"),
    configWith("scope", "https://attacker.example")])(
    "rejects malformed configuration without local fallback: %j", async (value) => {
      fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(value)));
      await expect(initializeSession()).rejects.toThrow(/configuration/);
      expect(construct).not.toHaveBeenCalled();
    },
  );

  it("does not treat configuration outages as local mode", async () => {
    fetchMock.mockResolvedValueOnce(new Response("unavailable", { status: 503 }));
    await expect(initializeSession()).rejects.toThrow("503");
    expect(construct).not.toHaveBeenCalled();
  });

  it("initializes tenant-specific PKCE and waits for an explicit sign-in action", async () => {
    const session = await initializeSession();
    expect(session.signedIn).toBe(false);
    expect(client.loginRedirect).not.toHaveBeenCalled();
    expect(construct).toHaveBeenCalledWith(expect.objectContaining({
      auth: expect.objectContaining({
        clientId: config.clientId,
        authority: `https://login.microsoftonline.com/${config.tenantId}`,
        redirectUri: "https://demo.example/",
      }),
      cache: { cacheLocation: "sessionStorage" },
    }));
    await session.signIn();
    expect(client.loginRedirect).toHaveBeenCalledWith({
      scopes: [config.scope], prompt: "select_account",
    });
    await expect(session.request("/api/claims")).rejects.toThrow("Sign in");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uses access tokens, preserves headers and refuses redirects and arbitrary paths", async () => {
    client.handleRedirectPromise.mockResolvedValue({ account });
    client.getActiveAccount.mockReturnValue(account);
    client.acquireTokenSilent.mockResolvedValue({ accessToken: "synthetic-access-token" });
    const session = await initializeSession();
    expect(session.signedIn).toBe(true);
    expect(client.setActiveAccount).toHaveBeenCalledWith(account);
    await session.request("/api/claims/clm-demo-001/assess", {
      method: "POST", headers: { "Content-Type": "application/json" },
    });
    expect(client.acquireTokenSilent).toHaveBeenCalledWith({
      scopes: [config.scope], account,
    });
    const options = fetchMock.mock.calls[1][1];
    expect(options?.redirect).toBe("error");
    const headers = new Headers(options?.headers);
    expect(headers.get("Authorization")).toBe("Bearer synthetic-access-token");
    expect(headers.get("Content-Type")).toBe("application/json");
    for (const path of ["//attacker.example", "https://attacker.example", "/auth-config"]) {
      await expect(session.request(path)).rejects.toThrow("business paths");
    }
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not silently select among multiple cached accounts", async () => {
    client.getAllAccounts.mockReturnValue([account, { homeAccountId: "another-account" }]);
    expect((await initializeSession()).signedIn).toBe(false);
    expect(client.setActiveAccount).toHaveBeenCalledWith(null);
  });

  it("does not make an anonymous API request when token acquisition fails", async () => {
    client.getActiveAccount.mockReturnValue(account);
    client.acquireTokenSilent.mockRejectedValue(new Error("Token unavailable"));
    const session = await initializeSession();
    await expect(session.request("/api/claims")).rejects.toThrow("Token unavailable");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

function configWith(key: string, value: string) {
  return { ...config, [key]: value };
}

import { useEffect, useState } from "react";
import App from "./App";
import { initializeSession, type Session } from "./auth";

let sessionPromise: Promise<Session> | undefined;

export default function AuthGate() {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    sessionPromise ??= initializeSession();
    sessionPromise
      .then((value) => { if (active) setSession(value); })
      .catch(() => {
        if (active) setError("Authentication could not initialize. Check configuration and reload.");
      });
    return () => { active = false; };
  }, []);

  async function interact(action: () => Promise<void>) {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch {
      setError("Sign-in or sign-out could not complete. Try again or contact the demo operator.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {session?.mode === "azure" && (
        <section className="notice" aria-label="Authentication">
          <strong>Entra-protected synthetic demo.</strong>{" "}
          <button
            type="button"
            disabled={busy}
            onClick={() => void interact(session.signedIn ? session.signOut : session.signIn)}
          >
            {session.signedIn ? "Sign out" : "Sign in"}
          </button>
        </section>
      )}
      {error && <section className="error" role="alert">{error}</section>}
      {session?.signedIn ? (
        <App session={session} />
      ) : (
        <main className="layout">
          <h1>Claims review</h1>
          <p>{session ? "Sign in to access synthetic claims. Human review is always required." :
            "Initializing authentication..."}</p>
        </main>
      )}
    </>
  );
}

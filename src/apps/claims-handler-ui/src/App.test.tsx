// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import type { Session } from "./auth";

let container: HTMLDivElement;
let root: Root;
const claims = [{ claimId: "clm-demo-001" }, { claimId: "clm-demo-003" }];
let request: ReturnType<typeof vi.fn<Session["request"]>>;
let session: Session;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  vi.stubGlobal("URL", Object.assign(URL, {
    createObjectURL: vi.fn(() => "blob:synthetic"),
    revokeObjectURL: vi.fn(),
  }));
  request = vi.fn<Session["request"]>(async (path) => {
    if (path === "/api/claims") return Response.json(claims);
    if (path.endsWith("/artifacts")) return Response.json(
      path.includes("001") ? [{ artifactId: "art-demo-photo-001", artifactType: "damage_photo" }] : [],
    );
    if (path.endsWith("/content")) return new Response("image", {
      headers: { "Content-Type": "image/png" },
    });
    throw new Error(`Unexpected request: ${path}`);
  });
  session = { mode: "azure", signedIn: true, request, signIn: vi.fn(), signOut: vi.fn() };
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

it("previews through authenticated requests, makes no inference, and revokes image URLs", async () => {
  await act(async () => root.render(<App session={session} />));
  expect(container.querySelector("img")?.src).toContain("blob:synthetic");
  expect(request.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  await act(async () => {
    const select = container.querySelector("select")!;
    select.value = "clm-demo-003";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic");
  expect(container.querySelector("img")).toBeNull();
  expect(container.textContent).toContain("No damage photo");
});

it("starts one workflow run and ignores a late response for a previous selection", async () => {
  let finish: (response: Response) => void = () => {};
  const deferred = new Promise<Response>((resolve) => { finish = resolve; });
  const original = request.getMockImplementation()!;
  request.mockImplementation((path, options) =>
    path.endsWith("/workflow") ? deferred : original(path, options));
  await act(async () => root.render(<App session={session} />));
  await act(async () => {
    const button = container.querySelector("button")!;
    button.click();
    button.click();
  });
  expect(request.mock.calls.filter(([path]) => path.endsWith("/workflow"))).toHaveLength(1);
  await act(async () => {
    const select = container.querySelector("select")!;
    select.value = "clm-demo-003";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    finish(Response.json({ assessment: { summary: "STALE ASSESSMENT" } }));
    await deferred;
  });
  expect(container.textContent).not.toContain("STALE ASSESSMENT");
});

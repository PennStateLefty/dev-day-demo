// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App";
import type { Session } from "./auth";

let container: HTMLDivElement;
let root: Root;
const claims = [
  { claimId: "clm-demo-001", lossDate: "2024-09-12" },
  { claimId: "clm-demo-003" },
];
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
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = false; },
  });
  request = vi.fn<Session["request"]>(async (path) => {
    if (path === "/api/claims") return Response.json(claims);
    if (path.endsWith("/artifacts")) return Response.json(
      path.includes("001")
        ? [
          { artifactId: "art-demo-photo-001", artifactType: "damage_photo" },
          { artifactId: "art-demo-estimate-001", artifactType: "repair_estimate" },
          { artifactId: "art-demo-photo-001b", artifactType: "damage_photo" },
        ]
        : [],
    );
    if (path.endsWith("/content")) return new Response("image", {
      headers: { "Content-Type": "image/png" },
    });
    if (path.endsWith("/workflow")) return Response.json({
      assessment: {
        assessmentId: "asm-demo-001",
        claimId: "clm-demo-001",
        summary: "Synthetic assessment result.",
        completenessFindings: [],
        policyCitations: [],
        policyBasis: "not_assessed",
        triageRecommendation: "human_review",
        humanReviewRequired: true,
      },
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
  expect(container.querySelectorAll(".thumbnail")).toHaveLength(2);
  expect(container.textContent).not.toContain("art-demo-estimate-001");
  expect(request.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  await act(async () => {
    container.querySelector<HTMLButtonElement>(".thumbnail:nth-child(2)")!.click();
  });
  expect(container.querySelector<HTMLButtonElement>(".thumbnail:nth-child(2)")?.getAttribute("aria-pressed"))
    .toBe("true");
  await act(async () => {
    const select = container.querySelector("select")!;
    select.value = "clm-demo-003";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic");
  expect(container.querySelector("img")).toBeNull();
  expect(container.textContent).toContain("No damage photo");
  expect(container.querySelector("option[value='clm-demo-003']")?.textContent)
    .toContain("No loss date | Not run this session");
});

it("opens and closes the viewer without losing the selected photo", async () => {
  await act(async () => root.render(<App session={session} />));
  await act(async () => {
    container.querySelector<HTMLButtonElement>(".thumbnail:nth-child(2)")!.click();
  });
  await act(async () => {
    container.querySelector<HTMLButtonElement>(".image-open-button")!.click();
  });
  expect(container.querySelector("dialog")?.open).toBe(true);
  expect(container.querySelector<HTMLImageElement>("dialog img")?.src).toContain("blob:synthetic");
  await act(async () => {
    [...container.querySelectorAll<HTMLButtonElement>("dialog button")]
      .find((button) => button.textContent === "Close")!.click();
  });
  expect(container.querySelector("dialog")).toBeNull();
  expect(container.querySelector<HTMLButtonElement>(".thumbnail:nth-child(2)")?.getAttribute("aria-pressed"))
    .toBe("true");
  expect(request.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
});

it("keeps available photos usable when another photo request fails", async () => {
  const original = request.getMockImplementation()!;
  request.mockImplementation((path, options) =>
    path.endsWith("/art-demo-photo-001/content")
      ? Promise.resolve(new Response(null, { status: 503 }))
      : original(path, options));
  await act(async () => root.render(<App session={session} />));
  expect(container.textContent).toContain("Could not load 1 of 2 damage photos.");
  expect(container.querySelector(".image-open-button img")).not.toBeNull();
  expect(container.querySelectorAll(".thumbnail")).toHaveLength(0);
  expect(container.textContent).toContain("art-demo-photo-001b");
});

it("shows claim check progress without implying a human review decision", async () => {
  await act(async () => root.render(<App session={session} />));
  const option = container.querySelector("option[value='clm-demo-001']")!;
  expect(option.textContent).toContain("clm-demo-001 | 2024-09-12 | Not run this session");
  await act(async () => {
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Run handler checks")!.click();
  });
  expect(container.querySelector("option[value='clm-demo-001']")?.textContent)
    .toContain("Checks complete — human review required");
  expect(container.querySelector("option[value='clm-demo-001']")?.textContent)
    .not.toContain("Reviewed");
});

it("marks failed checks without labeling the claim as reviewed", async () => {
  request.mockImplementation((path) => path.endsWith("/workflow")
    ? Promise.resolve(Response.json({ detail: "Assessment unavailable." }, { status: 503 }))
    : Promise.resolve(Response.json(path === "/api/claims" ? claims : [])));
  await act(async () => root.render(<App session={session} />));
  await act(async () => {
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Run handler checks")!.click();
  });
  expect(container.querySelector("option[value='clm-demo-001']")?.textContent)
    .toContain("Checks failed");
  expect(container.querySelector('[role="alert"]')?.textContent)
    .toContain("Assessment unavailable.");
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

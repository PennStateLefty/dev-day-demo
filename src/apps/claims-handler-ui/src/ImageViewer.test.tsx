// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ImageViewer from "./ImageViewer";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = true; },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value(this: HTMLDialogElement) { this.open = false; },
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

it("opens a modal with bounded zoom controls and closes on Escape", async () => {
  const onClose = vi.fn();
  await act(async () => root.render(
    <ImageViewer
      src="blob:synthetic"
      alt="Synthetic damage photo"
      artifactId="art-demo-photo-001"
      onClose={onClose}
      onImageError={vi.fn()}
    />,
  ));

  const dialog = container.querySelector("dialog")!;
  expect(dialog.open).toBe(true);
  expect(dialog.getAttribute("aria-labelledby")).toBe("image-viewer-title");
  expect(container.textContent).toContain("100%");

  await act(async () => {
    container.querySelector<HTMLButtonElement>("button:nth-of-type(2)")!.click();
  });
  expect(container.textContent).toContain("125%");
  expect(container.querySelector<HTMLImageElement>(".viewer-viewport img")?.style.width)
    .toBe("125%");

  await act(async () => {
    for (let index = 0; index < 20; index += 1) {
      container.querySelectorAll<HTMLButtonElement>(".viewer-controls button")[1].click();
    }
  });
  expect(container.textContent).toContain("400%");
  expect(container.querySelectorAll<HTMLButtonElement>(".viewer-controls button")[1].disabled).toBe(true);

  await act(async () => {
    dialog.dispatchEvent(new Event("cancel", { bubbles: false, cancelable: true }));
  });
  expect(onClose).toHaveBeenCalledOnce();
});

it("resets zoom and closes through the explicit close button", async () => {
  const onClose = vi.fn();
  await act(async () => root.render(
    <ImageViewer
      src="blob:synthetic"
      alt="Synthetic damage photo"
      artifactId="art-demo-photo-001"
      onClose={onClose}
      onImageError={vi.fn()}
    />,
  ));
  await act(async () => {
    container.querySelectorAll<HTMLButtonElement>(".viewer-controls button")[1].click();
    container.querySelectorAll<HTMLButtonElement>(".viewer-controls button")[1].click();
  });
  expect(container.textContent).toContain("150%");
  await act(async () => {
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Reset")!.click();
  });
  expect(container.textContent).toContain("100%");
  await act(async () => {
    [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Close")!.click();
  });
  expect(onClose).toHaveBeenCalledOnce();
});

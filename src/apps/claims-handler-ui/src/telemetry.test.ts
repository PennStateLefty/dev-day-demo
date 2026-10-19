// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { initializeTelemetry } from "./telemetry";

const sdk = vi.hoisted(() => ({
  construct: vi.fn(),
  load: vi.fn(),
  initializer: vi.fn(),
  page: vi.fn(),
}));
vi.mock("@microsoft/applicationinsights-web", () => ({
  DistributedTracingModes: { W3C: 2 },
  ApplicationInsights: class {
    constructor(options: unknown) { sdk.construct(options); }
    loadAppInsights = sdk.load;
    addTelemetryInitializer = sdk.initializer;
    trackPageView = sdk.page;
  },
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("does not start an exporter in local mode", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ connectionString: "" })),
  ));
  await initializeTelemetry();
  expect(sdk.construct).not.toHaveBeenCalled();
});

it("enables W3C correlation only for the API and omits URL queries", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ connectionString: "configured-for-test" })),
  ));
  await initializeTelemetry();
  const config = sdk.construct.mock.calls[0][0].config;
  expect(config.distributedTracingMode).toBe(2);
  expect(config.correlationHeaderDomains).toEqual(["localhost:8000"]);
  expect(config.enableRequestHeaderTracking).toBe(false);
  expect(config.enableResponseHeaderTracking).toBe(false);
  expect(config.disableCookiesUsage).toBe(true);
  const item = { tags: {}, baseData: { uri: "https://demo.test/?code=secret#token" } };
  sdk.initializer.mock.calls[0][0](item);
  expect(item.baseData.uri).toBe("https://demo.test/");
  expect(item.tags).toEqual({ "ai.cloud.role": "claims-handler-ui" });
});

it("reports invalid telemetry configuration explicitly", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
  await expect(initializeTelemetry()).rejects.toThrow("Invalid telemetry configuration");
});

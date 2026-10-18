import { ApplicationInsights, DistributedTracingModes } from "@microsoft/applicationinsights-web";
import { API_BASE } from "./auth";

export async function initializeTelemetry(): Promise<void> {
  const response = await fetch(`${API_BASE}/telemetry-config`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Telemetry configuration failed (${response.status}).`);
  const configuration: unknown = await response.json();
  if (
    typeof configuration !== "object" || configuration === null ||
    !("connectionString" in configuration) ||
    typeof configuration.connectionString !== "string"
  ) {
    throw new Error("Invalid telemetry configuration.");
  }
  if (!configuration.connectionString) return;
  const api = new URL(API_BASE || "/", window.location.origin);
  const insights = new ApplicationInsights({
    config: {
      connectionString: configuration.connectionString,
      distributedTracingMode: DistributedTracingModes.W3C,
      enableCorsCorrelation: true,
      correlationHeaderDomains: [api.host],
      disableCookiesUsage: true,
      enableAutoRouteTracking: false,
      enableAjaxErrorStatusText: false,
      enableRequestHeaderTracking: false,
      enableResponseHeaderTracking: false,
      autoTrackPageVisitTime: false,
    },
  });
  insights.loadAppInsights();
  insights.addTelemetryInitializer((item) => {
    item.tags = { ...item.tags, "ai.cloud.role": "claims-handler-ui" };
    for (const field of ["uri", "url", "target", "refUri"]) {
      const value = item.baseData?.[field];
      if (typeof value === "string" && /^https?:/.test(value)) {
        const url = new URL(value);
        url.search = "";
        url.hash = "";
        item.baseData![field] = url.toString();
      }
    }
  });
  insights.trackPageView({ name: "Claims handler", uri: window.location.origin + "/" });
}

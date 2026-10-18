import React from "react";
import ReactDOM from "react-dom/client";
import AuthGate from "./AuthGate";
import { initializeTelemetry } from "./telemetry";
import "./styles.css";

initializeTelemetry().catch((error: unknown) => {
  console.error("Browser telemetry initialization failed.", error);
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthGate />
  </React.StrictMode>,
);

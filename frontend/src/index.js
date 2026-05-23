import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { installErrorReporter } from "@/lib/errorReporter";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider, AuthCallbackHandler } from "@/lib/auth";

installErrorReporter();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <AuthCallbackHandler />
        <App />
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

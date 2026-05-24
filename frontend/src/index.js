import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/index.css";
import App from "@/App";
import { MarketplacePage } from "@/components/marketplace/MarketplacePage";
import { CreatorPage } from "@/components/marketplace/CreatorPage";
import { ListingDetailPage } from "@/components/marketplace/ListingDetailPage";
import { PurchaseSuccessPage } from "@/components/marketplace/PurchaseSuccessPage";
import { installErrorReporter } from "@/lib/errorReporter";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider, AuthCallbackHandler } from "@/lib/auth";

installErrorReporter();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <AuthCallbackHandler />
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/marketplace" element={<MarketplacePage />} />
            <Route path="/marketplace/:jobId" element={<ListingDetailPage />} />
            <Route path="/marketplace/:jobId/success" element={<PurchaseSuccessPage />} />
            <Route path="/creator/:userId" element={<CreatorPage />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

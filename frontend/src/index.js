import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "@/index.css";
import App from "@/App";
import { LandingPage } from "@/components/LandingPage";
import { MarketplacePage } from "@/components/marketplace/MarketplacePage";
import { CreatorPage } from "@/components/marketplace/CreatorPage";
import { ListingDetailPage } from "@/components/marketplace/ListingDetailPage";
import { PurchaseSuccessPage } from "@/components/marketplace/PurchaseSuccessPage";
import { PayoutsPage } from "@/components/marketplace/PayoutsPage";
import { PricingPage } from "@/components/PricingPage";
import { installErrorReporter } from "@/lib/errorReporter";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider, AuthCallbackHandler } from "@/lib/auth";
import { QuotaProvider } from "@/lib/quota";
import { GlobalUpgradeModal } from "@/components/GlobalUpgradeModal";
import { Toaster } from "sonner";

installErrorReporter();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <QuotaProvider>
          <BrowserRouter>
            <AuthCallbackHandler />
            <GlobalUpgradeModal />
            <Toaster
              theme="dark"
              position="bottom-right"
              toastOptions={{
                className: "!rounded-none !border !border-zinc-700 !bg-zinc-950 !font-mono !text-xs",
              }}
            />
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/studio" element={<App />} />
              <Route path="/marketplace" element={<MarketplacePage />} />
              <Route path="/marketplace/:jobId" element={<ListingDetailPage />} />
              <Route path="/marketplace/:jobId/success" element={<PurchaseSuccessPage />} />
              <Route path="/creator/:userId" element={<CreatorPage />} />
              <Route path="/payouts" element={<PayoutsPage />} />
              <Route path="/pricing" element={<PricingPage />} />
            </Routes>
          </BrowserRouter>
        </QuotaProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

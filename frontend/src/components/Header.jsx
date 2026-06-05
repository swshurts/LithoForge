import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Zap, Store, Send } from "lucide-react";
import { toast } from "sonner";
import { UserMenu } from "./UserMenu";
import { QuotaCounter } from "./QuotaCounter";
import { exportUrl } from "../lib/api";
import {
  sendToForgeSlicer,
  PopupBlocked,
  AuthRequired,
  HandoffTimeout,
} from "../lib/forgeslicerHandoff";
import { useQuota } from "../lib/quota";

export const Header = ({ onGenerate, canGenerate, generating, jobId, baseMinLayers }) => {
  const [sending, setSending] = useState(false);
  const { showUpgrade } = useQuota();

  const handleSend = async () => {
    if (!jobId || sending) return;
    setSending(true);
    try {
      await sendToForgeSlicer({
        // 3MF carries the per-filament objects + slot/RGB metadata that
        // ForgeSlicer needs to recover the full colour palette. STL would
        // strip that down to a single colourless mesh, so this endpoint
        // is the correct handoff format.
        modelUrl: exportUrl(jobId, "3mf", { baseMinLayers }),
        filename: `lithoforge-${jobId.slice(0, 8)}.3mf`,
        sourceUrl: `${window.location.origin}/studio?job=${jobId}`,
      });
      toast.success("Sent to ForgeSlicer", { duration: 3500 });
    } catch (err) {
      if (err instanceof AuthRequired) {
        showUpgrade();
      } else if (err instanceof PopupBlocked) {
        toast.error(err.message);
      } else if (err instanceof HandoffTimeout) {
        toast.error(err.message);
      } else {
        toast.error(err.message || "Send to ForgeSlicer failed");
      }
    } finally {
      setSending(false);
    }
  };
  return (
    <header
      className="border-b border-zinc-800 bg-zinc-950 flex items-center justify-between px-5 h-14 z-30"
      data-testid="header"
    >
      <div className="flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2.5 group" data-testid="header-home-link">
          <div className="relative w-7 h-7 flex items-center justify-center">
            <div className="absolute inset-0 border border-zinc-700 group-hover:border-zinc-400 transition-colors" />
            <div className="absolute top-0 left-0 w-2 h-2 bg-cmyk-c" />
            <div className="absolute top-0 right-0 w-2 h-2 bg-cmyk-m" />
            <div className="absolute bottom-0 left-0 w-2 h-2 bg-cmyk-y" />
            <div className="absolute bottom-0 right-0 w-2 h-2 bg-cmyk-w border-l border-t border-zinc-700" />
          </div>
          <div>
            <div className="font-display text-base font-black tracking-tighter leading-none">
              LITHOFORGE
            </div>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-500 leading-none mt-0.5">
              Photo · Beer-Lambert
            </div>
          </div>
        </Link>
        <div className="hidden md:flex items-center gap-3 pl-4 border-l border-zinc-800">
          <QuotaCounter />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <a
          href="https://forgeslicer.com"
          target="_blank"
          rel="noopener noreferrer"
          data-testid="header-sister-tool-link"
          className="hidden md:flex items-center gap-1.5 pl-1 pr-2.5 py-1 border border-zinc-800 hover:border-amber-500/60 text-zinc-300 hover:text-zinc-100 font-mono text-[10px] uppercase tracking-[0.15em] transition-colors duration-150"
        >
          <img
            src="/forgeslicer-logo.webp"
            alt=""
            aria-hidden="true"
            className="w-4 h-4 object-cover border border-zinc-800"
            width={16}
            height={16}
          />
          Sister tool: ForgeSlicer.com&nbsp;→
        </a>
        <Link
          to="/pricing"
          data-testid="header-pricing-link"
          className="hidden lg:block text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors duration-150"
        >
          Pricing
        </Link>
        <Link
          to="/marketplace"
          data-testid="header-marketplace-link"
          className="hidden md:flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors duration-150"
        >
          <Store className="w-3.5 h-3.5" strokeWidth={1.5} />
          Marketplace
        </Link>
        <UserMenu />
        <button
          data-testid="header-send-to-forgeslicer"
          disabled={!jobId || sending || generating}
          onClick={handleSend}
          title={
            !jobId
              ? "Generate a lithophane first, then send it to ForgeSlicer."
              : "Open ForgeSlicer with this lithophane's STL pre-loaded"
          }
          className="hidden md:flex items-center gap-2 border border-amber-700/60 text-amber-100 hover:bg-amber-500/10 hover:border-amber-400 disabled:border-zinc-800 disabled:text-zinc-600 disabled:hover:bg-transparent disabled:cursor-not-allowed px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.18em] transition-colors duration-150"
        >
          {sending ? (
            <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <Send className="w-3.5 h-3.5" strokeWidth={2} />
          )}
          {sending ? "Sending…" : "Send to ForgeSlicer"}
        </button>
        <button
          data-testid="generate-btn"
          disabled={!canGenerate || generating}
          onClick={onGenerate}
          className="group flex items-center gap-2 bg-zinc-100 text-zinc-950 px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.2em] hover:bg-white disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed transition-colors duration-150"
        >
          <Zap className="w-3.5 h-3.5" strokeWidth={2} />
          {generating ? "Solving…" : "Generate"}
        </button>
      </div>
    </header>
  );
};

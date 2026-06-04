import React from "react";
import { Link } from "react-router-dom";
import { Zap, Store } from "lucide-react";
import { UserMenu } from "./UserMenu";
import { QuotaCounter } from "./QuotaCounter";

export const Header = ({ onGenerate, canGenerate, generating }) => {
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

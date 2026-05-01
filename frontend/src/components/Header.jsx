import React from "react";
import { Zap, Cpu, Github } from "lucide-react";

export const Header = ({ onGenerate, canGenerate, generating }) => {
  return (
    <header
      className="border-b border-zinc-800 bg-zinc-950 flex items-center justify-between px-5 h-14 z-30"
      data-testid="header"
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="relative w-7 h-7 flex items-center justify-center">
            <div className="absolute inset-0 border border-zinc-700" />
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
              CMYKW · Beer-Lambert
            </div>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-3 pl-4 border-l border-zinc-800">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500">
            <Cpu className="w-3 h-3" strokeWidth={1.5} />
            Backend solver
          </div>
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-600">
            · ΔE76 nearest-neighbour
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="hidden md:flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors duration-150"
        >
          <Github className="w-3.5 h-3.5" strokeWidth={1.5} />
          Docs
        </a>
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

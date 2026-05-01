import React, { useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, Eye, Grid3x3 } from "lucide-react";
import { UploadZone } from "./UploadZone";

const ViewTabs = ({ active, setActive }) => (
  <div
    className="inline-flex border border-zinc-800 bg-zinc-950"
    data-testid="view-tabs"
  >
    {[
      { id: "preview", label: "COLOUR", icon: Eye },
      { id: "heightmap", label: "HEIGHT", icon: Grid3x3 },
      { id: "original", label: "SOURCE", icon: RefreshCw },
    ].map((t) => {
      const Icon = t.icon;
      return (
        <button
          key={t.id}
          data-testid={`view-tab-${t.id}`}
          onClick={() => setActive(t.id)}
          className={`flex items-center gap-1.5 px-3 py-1.5 font-mono text-[10px] font-bold tracking-[0.15em] transition-colors duration-150 ${
            active === t.id
              ? "bg-zinc-100 text-zinc-950"
              : "text-zinc-400 hover:text-zinc-100"
          }`}
        >
          <Icon className="w-3 h-3" strokeWidth={1.5} />
          {t.label}
        </button>
      );
    })}
  </div>
);

export const Viewport = ({
  onFile,
  sourceUrl,
  result,
  loading,
  progressLabel,
  onReset,
  renderMode,
}) => {
  const [view, setView] = useState("preview");

  useEffect(() => {
    if (result && view === "original") setView("preview");
  }, [result]); // eslint-disable-line

  if (!sourceUrl) {
    return (
      <div className="relative h-full">
        <UploadZone onFile={onFile} />
      </div>
    );
  }

  const previewSrc = result
    ? view === "heightmap"
      ? `data:image/png;base64,${result.heightmap_png_base64}`
      : view === "original"
      ? sourceUrl
      : `data:image/png;base64,${result.preview_png_base64}`
    : sourceUrl;

  return (
    <div
      className="relative h-full flex flex-col grid-bg"
      data-testid="viewport"
    >
      <div className="absolute inset-0 scanline pointer-events-none" />
      <div className="relative z-10 flex items-center justify-between px-5 py-3 border-b border-zinc-800 bg-zinc-950/60 backdrop-blur">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
            Viewport
          </span>
          {result && (
            <span
              className="font-mono text-[10px] text-zinc-400 tabular-nums"
              data-testid="viewport-stats"
            >
              · ΔE {result.delta_e_mean.toFixed(2)} · {result.total_layers}{" "}
              layers · {result.filaments.length} filaments
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {result && <ViewTabs active={view} setActive={setView} />}
          <button
            onClick={onReset}
            data-testid="reset-btn"
            className="font-mono text-[10px] uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors duration-150"
          >
            ← NEW IMAGE
          </button>
        </div>
      </div>

      <div className="relative z-10 flex-1 flex items-center justify-center p-6 overflow-hidden">
        <div
          className="relative border border-zinc-800 max-h-full max-w-full"
          data-testid="viewport-image-wrap"
        >
          <img
            src={previewSrc}
            alt="lithophane"
            className="block max-h-[70vh] max-w-full object-contain"
            data-testid="viewport-image"
            style={
              view === "heightmap"
                ? { filter: "contrast(1.1)", imageRendering: "pixelated" }
                : undefined
            }
          />
          {view === "preview" && result && (
            <div className="absolute top-2 left-2 font-mono text-[9px] tracking-[0.2em] text-zinc-300 bg-black/60 px-2 py-0.5 border border-white/10">
              {renderMode === "painting"
                ? "PAINT PREVIEW · NEAREST-FILAMENT MAPPING"
                : "SIMULATED BACKLIT OUTPUT"}
            </div>
          )}
          {view === "heightmap" && (
            <div className="absolute top-2 left-2 font-mono text-[9px] tracking-[0.2em] text-zinc-300 bg-black/60 px-2 py-0.5 border border-white/10">
              HEIGHT MAP · BRIGHTER = THICKER
            </div>
          )}
        </div>
      </div>

      {loading && (
        <div
          className="absolute inset-0 bg-black/70 z-20 flex items-center justify-center backdrop-blur-sm"
          data-testid="loading-overlay"
        >
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="w-8 h-8 animate-spin text-zinc-200" strokeWidth={1.5} />
            <div className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
              {progressLabel || "OPTIMIZING..."}
            </div>
            <div className="font-mono text-[10px] text-zinc-600 max-w-xs text-center tracking-wider">
              Building Beer-Lambert LUT · Matching ΔE in Lab space
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

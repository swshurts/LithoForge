import React from "react";
import { Download, FileBox, Layers, FileText, Wand2 } from "lucide-react";
import { PaletteEditor } from "./PaletteEditor";
import { exportUrl } from "../lib/api";

const DeltaBadge = ({ label, value, accent }) => (
  <div className="panel-muted p-3 space-y-1">
    <div className="text-[9px] uppercase tracking-[0.18em] text-zinc-500">
      {label}
    </div>
    <div className="flex items-baseline gap-2">
      <span
        className="font-mono text-2xl font-bold tabular-nums"
        style={{ color: accent }}
      >
        {value.toFixed(2)}
      </span>
      <span className="font-mono text-[10px] text-zinc-500">ΔE</span>
    </div>
  </div>
);

const quality = (de) => {
  if (de < 2) return { label: "IMPERCEPTIBLE", color: "#22c55e" };
  if (de < 5) return { label: "VERY CLOSE", color: "#84cc16" };
  if (de < 10) return { label: "ACCEPTABLE", color: "#eab308" };
  if (de < 20) return { label: "NOTICEABLE", color: "#f97316" };
  return { label: "FAR", color: "#ef4444" };
};

const DownloadButton = ({ href, icon: Icon, label, sub, testid }) => (
  <a
    href={href}
    download
    data-testid={testid}
    className="group flex items-center gap-3 p-3 panel-muted hover:border-zinc-600 transition-colors duration-150"
  >
    <div className="w-9 h-9 border border-zinc-800 flex items-center justify-center group-hover:bg-zinc-100 group-hover:text-zinc-950 transition-colors duration-150">
      <Icon className="w-4 h-4" strokeWidth={1.5} />
    </div>
    <div className="flex-1 min-w-0">
      <div className="text-xs font-bold uppercase tracking-[0.12em]">{label}</div>
      <div className="font-mono text-[10px] text-zinc-500 truncate">{sub}</div>
    </div>
    <Download
      className="w-4 h-4 text-zinc-600 group-hover:text-zinc-200 transition-colors duration-150"
      strokeWidth={1.5}
    />
  </a>
);

export const StatsPanel = ({
  result,
  filaments,
  setFilaments,
  maxActive,
  autoOrder,
  setAutoOrder,
  onSuggestPalette,
  suggesting,
  canSuggest,
  vibrancy,
  setVibrancy,
  onPaletteSizeChange,
}) => {
  const q = result ? quality(result.delta_e_mean) : null;

  return (
    <div
      className="h-full overflow-y-auto p-5 space-y-6"
      data-testid="stats-panel"
    >
      <div className="space-y-2">
        <div className="grid grid-cols-3 border border-zinc-800" data-testid="vibrancy-toggle">
          {[
            { id: 0.0, label: "Accurate" },
            { id: 0.5, label: "Balanced" },
            { id: 1.0, label: "Vibrant" },
          ].map((opt, i) => {
            const active = Math.abs(opt.id - vibrancy) < 0.05;
            return (
              <button
                key={opt.id}
                onClick={() => setVibrancy(opt.id)}
                data-testid={`vibrancy-${opt.label.toLowerCase()}`}
                className={`px-2 py-1.5 text-[9px] font-bold uppercase tracking-[0.12em] transition-colors duration-150 ${
                  active
                    ? "bg-zinc-100 text-zinc-950"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
                } ${i > 0 ? "border-l border-zinc-800" : ""}`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
        <button
          onClick={onSuggestPalette}
          disabled={!canSuggest || suggesting}
          data-testid="suggest-palette-btn"
          className="w-full flex items-center justify-center gap-2 border border-zinc-700 hover:border-zinc-400 hover:bg-zinc-900 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:border-zinc-700 py-2 font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-200 transition-colors duration-150"
        >
          <Wand2 className="w-3 h-3" strokeWidth={1.5} />
          {suggesting ? "Analysing…" : "Suggest palette from photo"}
        </button>
        {!canSuggest && !suggesting && (
          <div className="font-mono text-[9px] text-zinc-600 text-center">
            Upload a photograph first
          </div>
        )}
      </div>

      <PaletteEditor
        filaments={filaments}
        setFilaments={setFilaments}
        maxActive={maxActive}
        autoOrder={autoOrder}
        setAutoOrder={setAutoOrder}
        onPaletteSizeChange={onPaletteSizeChange}
      />

      <div className="border-t border-zinc-800" />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
            Colour fidelity
          </span>
          {q && (
            <span
              className="font-mono text-[10px] font-bold tracking-[0.15em]"
              style={{ color: q.color }}
              data-testid="fidelity-label"
            >
              {q.label}
            </span>
          )}
        </div>
        {result ? (
          <div className="grid grid-cols-2 gap-2">
            <DeltaBadge
              label="Mean"
              value={result.delta_e_mean}
              accent={q.color}
            />
            <DeltaBadge
              label="95th pct"
              value={result.delta_e_p95}
              accent="#a1a1aa"
            />
          </div>
        ) : (
          <div className="panel-muted p-4 text-center">
            <div className="text-xs text-zinc-500">
              Run optimization to see ΔE stats
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-zinc-800" />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
            Layer allocation
          </span>
          <span className="font-mono text-[10px] text-zinc-500">
            {result ? `${result.total_layers} layers` : "—"}
          </span>
        </div>
        {result ? (
          <div className="space-y-1.5" data-testid="allocation-list">
            {result.timeline.map((t, i) => (
              <div
                key={i}
                className="flex items-center gap-2 font-mono text-[11px]"
              >
                <div
                  className="w-3 h-3 border border-zinc-700"
                  style={{ background: t.color }}
                />
                <span className="text-zinc-300 flex-1">{t.name}</span>
                <span className="text-zinc-500 tabular-nums">{t.layers}×</span>
                <span className="text-zinc-600 tabular-nums w-20 text-right">
                  {t.start_z_mm.toFixed(2)}–{t.end_z_mm.toFixed(2)}mm
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="panel-muted p-4 text-center text-xs text-zinc-500">
            —
          </div>
        )}
      </div>

      <div className="border-t border-zinc-800" />

      <div className="space-y-3">
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
          Export
        </div>
        <div className="space-y-2">
          <DownloadButton
            href={result ? exportUrl(result.job_id, "stl") : "#"}
            icon={FileBox}
            label="STL mesh"
            sub="Heightmap geometry"
            testid="download-stl"
          />
          <DownloadButton
            href={result ? exportUrl(result.job_id, "swaps") : "#"}
            icon={FileText}
            label="Swap instructions"
            sub="M600 + Z heights"
            testid="download-swaps"
          />
          <DownloadButton
            href={result ? exportUrl(result.job_id, "3mf") : "#"}
            icon={Layers}
            label="3MF bundle"
            sub="Mesh + filament metadata"
            testid="download-3mf"
          />
        </div>
        {!result && (
          <div className="font-mono text-[10px] text-zinc-600 text-center pt-1">
            Generate a lithophane first
          </div>
        )}
      </div>
    </div>
  );
};

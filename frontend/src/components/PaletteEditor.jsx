import React, { useState } from "react";
import { Pencil, Check, ArrowLeft, ArrowRight, Sparkles } from "lucide-react";

const Swatch = ({ filament, idx, total, onChange, onMove, disabled }) => {
  const [editing, setEditing] = useState(false);
  const [hex, setHex] = useState(filament.hex);
  const [td, setTd] = useState(filament.td);

  const commit = () => {
    onChange(idx, { ...filament, hex, td: parseFloat(td) || filament.td });
    setEditing(false);
  };

  return (
    <div
      data-testid={`filament-swatch-${filament.name.toLowerCase()}`}
      className="group relative"
    >
      <div
        className="w-full aspect-square border border-zinc-800 transition-transform duration-150 group-hover:scale-[1.02]"
        style={{ background: filament.hex }}
      />
      <div className="mt-1.5 flex items-center justify-between gap-1">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-zinc-400 truncate">
          {filament.name}
        </span>
        <button
          onClick={() => setEditing((e) => !e)}
          className="text-zinc-600 hover:text-zinc-200 transition-colors duration-150 shrink-0"
          data-testid={`edit-filament-${filament.name.toLowerCase()}`}
          disabled={disabled}
        >
          {editing ? <Check className="w-3 h-3" /> : <Pencil className="w-3 h-3" />}
        </button>
      </div>
      <div className="font-mono text-[9px] text-zinc-500 mt-0.5 tabular-nums truncate">
        {filament.hex.toUpperCase()}·TD{filament.td.toFixed(1)}
      </div>

      <div className="mt-1 flex items-center justify-between gap-1">
        <button
          onClick={() => onMove(idx, idx - 1)}
          disabled={disabled || idx === 0}
          data-testid={`move-left-${filament.name.toLowerCase()}`}
          className="w-5 h-5 flex items-center justify-center border border-zinc-800 text-zinc-500 hover:text-zinc-100 hover:border-zinc-600 disabled:opacity-20 disabled:hover:text-zinc-500 disabled:hover:border-zinc-800 transition-colors duration-150"
        >
          <ArrowLeft className="w-2.5 h-2.5" strokeWidth={2} />
        </button>
        <span className="font-mono text-[9px] text-zinc-600 tabular-nums">
          {idx + 1}/{total}
        </span>
        <button
          onClick={() => onMove(idx, idx + 1)}
          disabled={disabled || idx === total - 1}
          data-testid={`move-right-${filament.name.toLowerCase()}`}
          className="w-5 h-5 flex items-center justify-center border border-zinc-800 text-zinc-500 hover:text-zinc-100 hover:border-zinc-600 disabled:opacity-20 disabled:hover:text-zinc-500 disabled:hover:border-zinc-800 transition-colors duration-150"
        >
          <ArrowRight className="w-2.5 h-2.5" strokeWidth={2} />
        </button>
      </div>

      {editing && (
        <div className="absolute z-20 top-full left-0 right-0 mt-1 panel p-2 space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={hex}
              onChange={(e) => setHex(e.target.value)}
              className="w-6 h-6 bg-transparent border border-zinc-800 cursor-pointer p-0"
              data-testid={`color-input-${filament.name.toLowerCase()}`}
            />
            <input
              type="text"
              value={hex}
              onChange={(e) => setHex(e.target.value)}
              className="flex-1 min-w-0 bg-zinc-950 border border-zinc-800 font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-zinc-600"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-zinc-500">TD</span>
            <input
              type="number"
              step="0.1"
              min="0.2"
              max="10"
              value={td}
              onChange={(e) => setTd(e.target.value)}
              className="flex-1 bg-zinc-950 border border-zinc-800 font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-zinc-600"
              data-testid={`td-input-${filament.name.toLowerCase()}`}
            />
          </div>
          <button
            onClick={commit}
            className="w-full bg-zinc-100 text-zinc-950 text-[10px] font-bold uppercase tracking-[0.15em] py-1.5 hover:bg-white"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
};

export const PaletteEditor = ({
  filaments,
  setFilaments,
  maxActive,
  autoOrder,
  setAutoOrder,
}) => {
  const onChange = (idx, f) =>
    setFilaments((list) => list.map((x, i) => (i === idx ? f : x)));

  const onMove = (from, to) => {
    if (to < 0 || to >= filaments.length || from === to) return;
    setFilaments((list) => {
      const next = [...list];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
    // Manually moving things implies the user wants their order respected.
    if (autoOrder) setAutoOrder(false);
  };

  const activeCount = Math.min(maxActive, filaments.length);

  return (
    <div className="space-y-3" data-testid="palette-editor">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
          Palette
        </span>
        <span className="font-mono text-[10px] text-zinc-500 tabular-nums">
          {activeCount}/{filaments.length} active
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {filaments.map((f, i) => (
          <div
            key={f.name}
            className={`transition-opacity duration-150 ${
              i < maxActive ? "opacity-100" : "opacity-30"
            }`}
          >
            <Swatch
              filament={f}
              idx={i}
              total={filaments.length}
              onChange={onChange}
              onMove={onMove}
              disabled={i >= maxActive}
            />
          </div>
        ))}
      </div>

      <div className="font-mono text-[9px] text-zinc-600 leading-relaxed pt-1">
        Order is bottom → top of the print. Slot 1 sits against the back-light
        (thin regions show it); the last slot caps the deepest shadows.
      </div>

      <label
        className="flex items-center justify-between gap-2 panel-muted px-3 py-2 cursor-pointer select-none hover:border-zinc-600 transition-colors duration-150"
        data-testid="auto-order-toggle"
      >
        <div className="flex items-center gap-2">
          <Sparkles
            className={`w-3 h-3 ${autoOrder ? "text-zinc-100" : "text-zinc-600"}`}
            strokeWidth={1.5}
          />
          <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-zinc-300">
            Auto-order on generate
          </span>
        </div>
        <input
          type="checkbox"
          checked={autoOrder}
          onChange={(e) => setAutoOrder(e.target.checked)}
          className="accent-zinc-100 w-3.5 h-3.5"
          data-testid="auto-order-checkbox"
        />
      </label>
    </div>
  );
};

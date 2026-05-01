import React, { useState } from "react";
import { Pencil, Check } from "lucide-react";

const Swatch = ({ filament, idx, onChange }) => {
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
      <div className="mt-1.5 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-zinc-400">
          {filament.name}
        </span>
        <button
          onClick={() => setEditing((e) => !e)}
          className="text-zinc-600 hover:text-zinc-200 transition-colors duration-150"
          data-testid={`edit-filament-${filament.name.toLowerCase()}`}
        >
          {editing ? <Check className="w-3 h-3" /> : <Pencil className="w-3 h-3" />}
        </button>
      </div>
      <div className="font-mono text-[10px] text-zinc-500 mt-0.5 tabular-nums">
        {filament.hex.toUpperCase()} · TD {filament.td.toFixed(1)}
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
              className="flex-1 bg-zinc-950 border border-zinc-800 font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-zinc-600"
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

export const PaletteEditor = ({ filaments, setFilaments, maxActive }) => {
  const onChange = (idx, f) =>
    setFilaments((list) => list.map((x, i) => (i === idx ? f : x)));

  return (
    <div className="space-y-3" data-testid="palette-editor">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
          CMYKW Palette
        </span>
        <span className="font-mono text-[10px] text-zinc-500 tabular-nums">
          {Math.min(maxActive, filaments.length)}/{filaments.length} active
        </span>
      </div>
      <div className="grid grid-cols-5 gap-2">
        {filaments.map((f, i) => (
          <div
            key={f.name}
            className={`transition-opacity duration-150 ${
              i < maxActive ? "opacity-100" : "opacity-30"
            }`}
          >
            <Swatch filament={f} idx={i} onChange={onChange} />
          </div>
        ))}
      </div>
    </div>
  );
};

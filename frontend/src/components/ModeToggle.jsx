import React from "react";
import { Lightbulb, Palette } from "lucide-react";

const MODES = [
  {
    id: "lithophane",
    label: "Lithophane",
    sub: "Backlit · Beer-Lambert",
    icon: Lightbulb,
  },
  {
    id: "painting",
    label: "Painting",
    sub: "Reflective · Palette",
    icon: Palette,
  },
];

export const ModeToggle = ({ mode, setMode, disabled }) => (
  <div
    className="grid grid-cols-2 gap-0 border border-zinc-800"
    data-testid="mode-toggle"
  >
    {MODES.map((m) => {
      const Icon = m.icon;
      const active = m.id === mode;
      return (
        <button
          key={m.id}
          data-testid={`mode-${m.id}`}
          onClick={() => setMode(m.id)}
          disabled={disabled}
          className={`flex flex-col items-start gap-1 px-3 py-2.5 text-left transition-colors duration-150 ${
            active
              ? "bg-zinc-100 text-zinc-950"
              : "bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
          } ${
            m.id === "painting" ? "border-l border-zinc-800" : ""
          } disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          <div className="flex items-center gap-1.5">
            <Icon className="w-3 h-3" strokeWidth={1.5} />
            <span className="font-mono text-[10px] font-bold uppercase tracking-[0.15em]">
              {m.label}
            </span>
          </div>
          <span
            className={`font-mono text-[9px] tracking-[0.1em] ${
              active ? "text-zinc-700" : "text-zinc-600"
            }`}
          >
            {m.sub}
          </span>
        </button>
      );
    })}
  </div>
);

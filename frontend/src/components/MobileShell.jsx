import React, { useState } from "react";
import { Sliders, Palette, X } from "lucide-react";

/**
 * Bottom-tab + slide-up panel layout for touch devices (< lg).
 *
 * Deliberately avoids Radix Dialog / Sheet because their portal + focus-
 * trap behaviour throws sanitized "Script error." entries on Safari iPad
 * when controls are touched mid-animation. We use a plain fixed div
 * instead — same visual effect, no portal magic.
 */
export const MobileShell = ({ viewport, configPanel, statsPanel }) => {
  const [open, setOpen] = useState(null); // 'config' | 'palette' | null

  const tabs = [
    {
      id: "config",
      label: "Setup",
      icon: Sliders,
      content: configPanel,
      title: "Setup · geometry & image edits",
    },
    {
      id: "palette",
      label: "Palette & stats",
      icon: Palette,
      content: statsPanel,
      title: "Palette · stats · export",
    },
  ];

  const active = tabs.find((t) => t.id === open) || null;

  return (
    <div className="flex flex-col h-full relative">
      {/* viewport takes all remaining height */}
      <div className="flex-1 min-h-0 overflow-hidden">{viewport}</div>

      {/* fixed bottom tab bar */}
      <div
        className="flex border-t border-zinc-800 bg-zinc-950 relative z-30"
        data-testid="mobile-tab-bar"
      >
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = open === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setOpen(isActive ? null : t.id)}
              data-testid={`mobile-tab-${t.id}`}
              className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors ${
                isActive
                  ? "bg-zinc-100 text-zinc-950"
                  : "text-zinc-300 active:bg-zinc-900"
              }`}
            >
              <Icon className="w-4 h-4" strokeWidth={1.5} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Backdrop */}
      {active && (
        <div
          onClick={() => setOpen(null)}
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          data-testid="mobile-backdrop"
          aria-hidden
        />
      )}

      {/* Slide-up panel — plain absolutely-positioned div, no Radix Dialog */}
      <div
        className={`fixed left-0 right-0 bottom-0 z-50 bg-zinc-950 border-t border-zinc-800 transition-transform duration-300 ease-out ${
          active ? "translate-y-0" : "translate-y-full pointer-events-none"
        }`}
        style={{ height: "78vh" }}
        data-testid="mobile-sheet"
      >
        {active && (
          <div className="flex flex-col h-full">
            <div className="border-b border-zinc-800 px-5 py-3 flex items-center justify-between flex-shrink-0">
              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-zinc-100">
                {active.title}
              </div>
              <button
                onClick={() => setOpen(null)}
                aria-label="Close"
                data-testid="mobile-sheet-close"
                className="w-8 h-8 flex items-center justify-center border border-zinc-800 text-zinc-400 hover:text-zinc-100 hover:border-zinc-600 transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto">
              {active.content}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

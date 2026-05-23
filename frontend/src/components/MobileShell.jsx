import React, { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from "./ui/sheet";
import { Sliders, Palette } from "lucide-react";

/**
 * Bottom-tab + sheet layout for touch devices (< lg).
 * Renders the viewport full-screen with a fixed bottom toolbar that
 * pulls up Config / Palette as half-height bottom sheets.
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
      description: "Presets, crop, brightness, dimensions & swap count.",
    },
    {
      id: "palette",
      label: "Palette & stats",
      icon: Palette,
      content: statsPanel,
      title: "Palette · stats · export",
      description: "Filaments, ΔE fidelity, layer allocation & downloads.",
    },
  ];

  const active = tabs.find((t) => t.id === open) || null;

  return (
    <div className="flex flex-col h-full">
      {/* viewport takes all remaining height */}
      <div className="flex-1 min-h-0 overflow-hidden">{viewport}</div>

      {/* fixed bottom tab bar */}
      <div
        className="flex border-t border-zinc-800 bg-zinc-950"
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

      <Sheet open={open !== null} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent
          side="bottom"
          className="h-[78vh] p-0 bg-zinc-950 border-zinc-800 rounded-none flex flex-col"
          data-testid="mobile-sheet"
          // Safari iPad throws an uncaught "Script error." when Radix's
          // default auto-focus fires while the slide-in animation is still
          // in progress. Disabling autofocus on open/close removes the race
          // — the user can tap controls inside the sheet immediately and
          // the first interaction no longer crashes.
          onOpenAutoFocus={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => e.preventDefault()}
        >
          {active && (
            <>
              <div className="border-b border-zinc-800 px-5 py-3 flex items-center justify-between flex-shrink-0">
                <div>
                  <SheetTitle className="font-mono text-[11px] uppercase tracking-[0.22em] text-zinc-100">
                    {active.title}
                  </SheetTitle>
                  <SheetDescription className="font-mono text-[9px] text-zinc-600 tracking-[0.1em] mt-0.5">
                    {active.description}
                  </SheetDescription>
                </div>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
                {active.content}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
};

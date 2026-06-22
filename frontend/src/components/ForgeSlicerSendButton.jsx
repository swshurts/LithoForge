/**
 * ForgeSlicerSendButton — one-click "send to ForgeSlicer" for any
 * generated part.
 *
 * For non-box geometries it's a single button that ships the lithophane
 * as a 3MF (preserves colour swaps). For box geometry it expands into a
 * dropdown so the user can pick which part to ship: lithophane / frame
 * / back panel / diffuser.
 *
 * The button is disabled until `result?.job_id` exists. The actual
 * heavy lifting (mesh build + multipart POST + Bearer auth forwarding)
 * happens on the backend at /api/forgeslicer/send/{job_id}.
 */
import React, { useState } from "react";
import { Send, Loader2, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { sendToForgeSlicer } from "../lib/api";

const PARTS_FOR_BOX = [
  { part: "lithophane", format: "3mf", label: "Lithophane (3MF)", sub: "Colour-aware, ready to slice" },
  { part: "lightbox_frame", format: "stl", label: "Lightbox frame (STL)", sub: "Walls + front bezel + LED bezels" },
  { part: "lightbox_back", format: "stl", label: "Back panel (STL)", sub: "Slide-in with 6mm cable notch" },
  { part: "lightbox_diffuser", format: "stl", label: "Diffuser (STL)", sub: "Translucent insert · only if enabled" },
];

const PART_FOR_SIMPLE = { part: "lithophane", format: "3mf", label: "Lithophane (3MF)" };

export const ForgeSlicerSendButton = ({ result, geometry, boxDiffuser }) => {
  const [busy, setBusy] = useState(null); // null | part key
  const [open, setOpen] = useState(false);

  const handleSend = async (part, format) => {
    if (!result?.job_id) {
      toast.error("Generate a model first");
      return;
    }
    setBusy(part);
    setOpen(false);
    const t = toast.loading(`Sending ${part} to ForgeSlicer…`);
    try {
      const out = await sendToForgeSlicer(result.job_id, { part, format });
      toast.success("Sent to ForgeSlicer", {
        id: t,
        description: `${out.source_shape} · ${(out.bytes_sent / 1024).toFixed(1)} KB`,
        action: {
          label: "Open ForgeSlicer",
          onClick: () => window.open("https://forgeslicer.com/inbox", "_blank", "noopener"),
        },
      });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === "string"
        ? detail
        : detail?.forgeslicer_response?.detail
          || detail?.error
          || err?.message
          || "Send failed";
      toast.error("ForgeSlicer send failed", { id: t, description: msg });
    } finally {
      setBusy(null);
    }
  };

  const isBox = geometry === "box";
  const disabled = !result?.job_id;

  if (!isBox) {
    return (
      <button
        type="button"
        onClick={() => handleSend(PART_FOR_SIMPLE.part, PART_FOR_SIMPLE.format)}
        disabled={disabled || busy !== null}
        data-testid="send-to-forgeslicer-btn"
        className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-amber-400/40 bg-amber-400/10 hover:bg-amber-400/20 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-[10px] uppercase tracking-[0.18em] text-amber-100 transition-colors"
      >
        {busy !== null
          ? <Loader2 size={14} className="animate-spin" />
          : <Send size={14} />}
        Send to ForgeSlicer
      </button>
    );
  }

  // Box mode: dropdown picker. Filter out diffuser if disabled.
  const parts = PARTS_FOR_BOX.filter((p) => p.part !== "lightbox_diffuser" || (boxDiffuser ?? true));

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((v) => !v)}
        disabled={disabled || busy !== null}
        data-testid="send-to-forgeslicer-btn"
        className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-amber-400/40 bg-amber-400/10 hover:bg-amber-400/20 disabled:opacity-40 disabled:cursor-not-allowed font-mono text-[10px] uppercase tracking-[0.18em] text-amber-100 transition-colors"
      >
        {busy !== null
          ? <Loader2 size={14} className="animate-spin" />
          : <Send size={14} />}
        Send to ForgeSlicer
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div
          className="absolute z-30 left-0 right-0 mt-1 bg-zinc-950 border border-amber-400/30 shadow-2xl overflow-hidden"
          data-testid="forgeslicer-parts-menu"
        >
          {parts.map((p) => (
            <button
              key={p.part}
              type="button"
              onClick={() => handleSend(p.part, p.format)}
              disabled={busy !== null}
              data-testid={`forgeslicer-part-${p.part}`}
              className="w-full text-left px-3 py-2.5 hover:bg-amber-400/10 disabled:opacity-50 border-b border-zinc-800 last:border-b-0"
            >
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-zinc-200">
                {p.label}
              </div>
              <div className="font-mono text-[9px] text-zinc-500 mt-0.5">
                {p.sub}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

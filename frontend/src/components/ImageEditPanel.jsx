import React from "react";
import { Slider } from "./ui/slider";
import { Label } from "./ui/label";
import { RotateCcw } from "lucide-react";

export const DEFAULT_EDITS = {
  brightness: 100, // 0..200 (100 = unchanged)
  contrast: 100,
  saturation: 100, // 0 = grayscale
  cropL: 0,        // % from left
  cropR: 0,        // % from right
  cropT: 0,        // % from top
  cropB: 0,        // % from bottom
};

export const editsAreActive = (e) =>
  e.brightness !== 100 ||
  e.contrast !== 100 ||
  e.saturation !== 100 ||
  e.cropL !== 0 ||
  e.cropR !== 0 ||
  e.cropT !== 0 ||
  e.cropB !== 0;

export const editsToCssFilter = (e) =>
  `brightness(${e.brightness / 100}) contrast(${e.contrast / 100}) saturate(${e.saturation / 100})`;

export const editsToClipPath = (e) => {
  const l = e.cropL;
  const r = 100 - e.cropR;
  const t = e.cropT;
  const b = 100 - e.cropB;
  return `polygon(${l}% ${t}%, ${r}% ${t}%, ${r}% ${b}%, ${l}% ${b}%)`;
};

const Row = ({ label, value, unit, children, testid }) => (
  <div className="space-y-1.5" data-testid={testid}>
    <div className="flex items-center justify-between">
      <Label className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500">
        {label}
      </Label>
      <span className="font-mono text-xs text-zinc-300 tabular-nums">
        {value}
        <span className="text-zinc-600 ml-1">{unit}</span>
      </span>
    </div>
    {children}
  </div>
);

export const ImageEditPanel = ({ edits, setEdits, disabled }) => {
  const update = (key, v) => setEdits((e) => ({ ...e, [key]: v }));
  const reset = () => setEdits({ ...DEFAULT_EDITS });
  const active = editsAreActive(edits);

  return (
    <div data-testid="image-edit-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500">
          Image
        </div>
        <button
          onClick={reset}
          disabled={disabled || !active}
          data-testid="image-edit-reset"
          className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-500 transition-colors duration-150"
        >
          <RotateCcw className="w-2.5 h-2.5" strokeWidth={2} />
          Reset
        </button>
      </div>

      <div className="space-y-3">
        <Row
          label="Brightness"
          value={edits.brightness - 100 >= 0 ? `+${edits.brightness - 100}` : `${edits.brightness - 100}`}
          unit=""
          testid="row-brightness"
        >
          <Slider
            data-testid="brightness-slider"
            value={[edits.brightness]}
            onValueChange={([v]) => update("brightness", v)}
            min={20}
            max={200}
            step={1}
            disabled={disabled}
          />
        </Row>

        <Row
          label="Contrast"
          value={edits.contrast - 100 >= 0 ? `+${edits.contrast - 100}` : `${edits.contrast - 100}`}
          unit=""
          testid="row-contrast"
        >
          <Slider
            data-testid="contrast-slider"
            value={[edits.contrast]}
            onValueChange={([v]) => update("contrast", v)}
            min={20}
            max={200}
            step={1}
            disabled={disabled}
          />
        </Row>

        <Row
          label="Saturation"
          value={
            edits.saturation === 0
              ? "B&W"
              : edits.saturation - 100 >= 0
                ? `+${edits.saturation - 100}`
                : `${edits.saturation - 100}`
          }
          unit=""
          testid="row-saturation"
        >
          <Slider
            data-testid="saturation-slider"
            value={[edits.saturation]}
            onValueChange={([v]) => update("saturation", v)}
            min={0}
            max={200}
            step={1}
            disabled={disabled}
          />
          <div className="font-mono text-[9px] text-zinc-600 mt-0.5">
            0 = black & white · 100 = original · 200 = vivid
          </div>
        </Row>

        <div className="border-t border-zinc-800 my-2" />

        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500">
          Crop
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Row label="Left" value={edits.cropL} unit="%" testid="row-cropL">
            <Slider
              data-testid="crop-left-slider"
              value={[edits.cropL]}
              onValueChange={([v]) => update("cropL", v)}
              min={0}
              max={45}
              step={1}
              disabled={disabled}
            />
          </Row>
          <Row label="Right" value={edits.cropR} unit="%" testid="row-cropR">
            <Slider
              data-testid="crop-right-slider"
              value={[edits.cropR]}
              onValueChange={([v]) => update("cropR", v)}
              min={0}
              max={45}
              step={1}
              disabled={disabled}
            />
          </Row>
          <Row label="Top" value={edits.cropT} unit="%" testid="row-cropT">
            <Slider
              data-testid="crop-top-slider"
              value={[edits.cropT]}
              onValueChange={([v]) => update("cropT", v)}
              min={0}
              max={45}
              step={1}
              disabled={disabled}
            />
          </Row>
          <Row label="Bottom" value={edits.cropB} unit="%" testid="row-cropB">
            <Slider
              data-testid="crop-bottom-slider"
              value={[edits.cropB]}
              onValueChange={([v]) => update("cropB", v)}
              min={0}
              max={45}
              step={1}
              disabled={disabled}
            />
          </Row>
        </div>
      </div>
    </div>
  );
};

/** Apply current edits to an HTMLImageElement and return a Promise<Blob>. */
export const renderEditedImage = (img, edits, format = "image/png", quality = 0.95) =>
  new Promise((resolve, reject) => {
    try {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      const cx = Math.round((edits.cropL / 100) * w);
      const cy = Math.round((edits.cropT / 100) * h);
      const cw = Math.max(1, Math.round((1 - (edits.cropL + edits.cropR) / 100) * w));
      const ch = Math.max(1, Math.round((1 - (edits.cropT + edits.cropB) / 100) * h));

      const canvas = document.createElement("canvas");
      canvas.width = cw;
      canvas.height = ch;
      const ctx = canvas.getContext("2d");
      ctx.filter = editsToCssFilter(edits);
      ctx.drawImage(img, cx, cy, cw, ch, 0, 0, cw, ch);
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("Canvas toBlob failed"))),
        format,
        quality
      );
    } catch (e) {
      reject(e);
    }
  });

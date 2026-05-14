import React, { useEffect, useRef } from "react";
import { editsToCssFilter } from "./ImageEditPanel";

/**
 * Compact luminance + RGB histogram. Re-computes whenever edits change by
 * drawing the original image at small size into an offscreen canvas with
 * the current CSS filter applied, reading ImageData, binning into 64 bins.
 * Highlights clipping at 0 and 255.
 */

const BINS = 64;

const computeBins = (imageData) => {
  const data = imageData.data;
  const lum = new Uint32Array(BINS);
  const r = new Uint32Array(BINS);
  const g = new Uint32Array(BINS);
  const b = new Uint32Array(BINS);
  for (let i = 0; i < data.length; i += 4) {
    const R = data[i];
    const G = data[i + 1];
    const B = data[i + 2];
    const L = 0.2126 * R + 0.7152 * G + 0.0722 * B;
    lum[Math.min(BINS - 1, Math.floor((L / 256) * BINS))]++;
    r[Math.min(BINS - 1, Math.floor((R / 256) * BINS))]++;
    g[Math.min(BINS - 1, Math.floor((G / 256) * BINS))]++;
    b[Math.min(BINS - 1, Math.floor((B / 256) * BINS))]++;
  }
  return { lum, r, g, b };
};

export const Histogram = ({ image, edits }) => {
  const canvasRef = useRef(null);
  const offscreenRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    if (!image.naturalWidth || !image.naturalHeight) return;
    if (!offscreenRef.current) {
      offscreenRef.current = document.createElement("canvas");
    }
    const off = offscreenRef.current;
    const W = 200;
    const H = Math.max(1, Math.round((image.naturalHeight / image.naturalWidth) * W));
    off.width = W;
    off.height = H;
    const offCtx = off.getContext("2d", { willReadFrequently: true });
    offCtx.filter = editsToCssFilter(edits);
    // Apply crop too so the histogram reflects the visible region.
    const cx = (edits.cropL / 100) * image.naturalWidth;
    const cy = (edits.cropT / 100) * image.naturalHeight;
    const cw = Math.max(
      1,
      (1 - (edits.cropL + edits.cropR) / 100) * image.naturalWidth
    );
    const ch = Math.max(
      1,
      (1 - (edits.cropT + edits.cropB) / 100) * image.naturalHeight
    );

    let imgData;
    try {
      offCtx.drawImage(image, cx, cy, cw, ch, 0, 0, W, H);
      imgData = offCtx.getImageData(0, 0, W, H);
    } catch (err) {
      // Tainted canvas (cross-origin image) or oversized buffer — skip the
      // histogram silently rather than crashing the whole edit panel.
      // Slider adjustments must keep working even if the histogram can't
      // read pixels back.
      // eslint-disable-next-line no-console
      console.warn("Histogram readback skipped:", err.message);
      return;
    }
    const { lum, r, g, b } = computeBins(imgData);

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const max = Math.max(
      Math.max(...lum),
      Math.max(...r),
      Math.max(...g),
      Math.max(...b),
      1
    );
    const drawSeries = (arr, fill, alpha = 0.55) => {
      ctx.fillStyle = fill;
      ctx.globalAlpha = alpha;
      const bw = cssW / BINS;
      for (let i = 0; i < BINS; i++) {
        const h = (arr[i] / max) * cssH;
        ctx.fillRect(i * bw, cssH - h, bw + 0.5, h);
      }
    };

    drawSeries(lum, "#a1a1aa", 0.85);
    drawSeries(r, "#ef4444", 0.45);
    drawSeries(g, "#22c55e", 0.45);
    drawSeries(b, "#3b82f6", 0.45);
    ctx.globalAlpha = 1;

    // Clipping markers — strong shadow / highlight clipping warnings.
    const totalPx = imgData.width * imgData.height;
    const shadowClip = lum[0] / totalPx;
    const highlightClip = lum[BINS - 1] / totalPx;
    if (shadowClip > 0.01) {
      ctx.fillStyle = "#1d4ed8";
      ctx.fillRect(0, cssH - 2, 4, 2);
    }
    if (highlightClip > 0.01) {
      ctx.fillStyle = "#facc15";
      ctx.fillRect(cssW - 4, cssH - 2, 4, 2);
    }
  }, [image, edits]);

  if (!image) return null;
  return (
    <div className="space-y-1" data-testid="histogram">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-zinc-500">
          Histogram
        </span>
        <span className="font-mono text-[9px] text-zinc-600">
          R · G · B · Luma
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="w-full h-12 bg-zinc-950 border border-zinc-800"
      />
    </div>
  );
};

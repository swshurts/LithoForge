import React, { useEffect, useMemo, useRef, useState } from "react";
import "@/App.css";
import { toast, Toaster } from "sonner";
import { Header } from "@/components/Header";
import { Viewport } from "@/components/Viewport";
import { ConfigPanel } from "@/components/ConfigPanel";
import { StatsPanel } from "@/components/StatsPanel";
import { LayerTimeline } from "@/components/LayerTimeline";
import { MobileShell } from "@/components/MobileShell";
import {
  DEFAULT_EDITS,
  editsAreActive,
  renderEditedImage,
} from "@/components/ImageEditPanel";
import {
  getDefaultFilaments,
  optimize,
  suggestPalette,
  uploadImage,
} from "@/lib/api";

const DEFAULT_CONFIG = {
  width_mm: 100,
  height_mm: 100,
  thickness_mm: 3.6,
  border_mm: 2,
  layer_height_mm: 0.12,
  max_swaps: 5,
  geometry: "flat",
  curve_radius_mm: 80,
  dome_mm: 0,
  render_mode: "painting",
  relief: 0.5,
  smoothing: 0,
  printer_id: "generic_orca",
};

export default function App() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [filaments, setFilaments] = useState([]);
  const [autoOrder, setAutoOrder] = useState(true);
  const [imageId, setImageId] = useState(null);
  const [sourceUrl, setSourceUrl] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progressLabel, setProgressLabel] = useState("");
  const [uploading, setUploading] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [vibrancy, setVibrancy] = useState(0.5);
  const [edits, setEdits] = useState({ ...DEFAULT_EDITS });
  // The original uploaded HTMLImageElement (kept so we can re-render edits).
  const originalImgRef = useRef(null);
  const [originalImg, setOriginalImg] = useState(null);
  // Track which edits the current `imageId` was uploaded under so we know
  // when we need to re-upload the canvas-rendered version.
  const [uploadedEdits, setUploadedEdits] = useState({ ...DEFAULT_EDITS });

  useEffect(() => {
    getDefaultFilaments()
      .then(setFilaments)
      .catch(() => toast.error("Failed to load default filaments"));
  }, []);

  const maxActive = config.max_swaps + 1;

  const handleFile = async (file) => {
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload an image file");
      return;
    }
    setUploading(true);
    setResult(null);
    setEdits({ ...DEFAULT_EDITS });
    try {
      const url = URL.createObjectURL(file);
      setSourceUrl(url);
      // Pre-load the original image element so we can re-render with edits.
      // NOTE: blob: URLs are same-origin; do NOT set crossOrigin — Safari
      // iOS rejects blob URLs with a crossOrigin attribute, leaving the
      // image element permanently in a broken state.
      const img = new Image();
      img.decoding = "async";
      img.onload = () => {
        originalImgRef.current = img;
        setOriginalImg(img);
      };
      img.onerror = () => {
        // Fall back to drawing directly from the blob via the viewport's
        // <img> tag — we'll re-create the canvas-source when needed.
        // eslint-disable-next-line no-console
        console.warn("Hidden image element failed to load — edits will use viewport <img> instead");
      };
      img.src = url;
      const data = await uploadImage(file);
      setImageId(data.image_id);
      setUploadedEdits({ ...DEFAULT_EDITS });
      toast.success(`Loaded ${data.width}×${data.height} image`);
    } catch (e) {
      toast.error("Upload failed");
      setSourceUrl(null);
    } finally {
      setUploading(false);
    }
  };

  // Make sure the backend's `imageId` reflects the *currently edited* version
  // of the source photo. If edits changed since last upload, re-render the
  // canvas, upload the resulting blob, and return the new image_id.
  const ensureCurrentImageId = async () => {
    if (!imageId) return null;
    if (!editsAreActive(edits)) return imageId;
    // Compare against the edits used at the previous upload.
    const sameAsUploaded =
      JSON.stringify(edits) === JSON.stringify(uploadedEdits);
    if (sameAsUploaded) return imageId;

    // Load (or re-load) the original from sourceUrl on demand so we never
    // fall through to the "upload as-is" branch just because of a race
    // between Image.decode and the upload network round-trip (common on
    // Safari iOS with large photos).
    let img = originalImgRef.current;
    if (!img && sourceUrl) {
      try {
        img = await new Promise((resolve, reject) => {
          const i = new Image();
          i.onload = () => resolve(i);
          i.onerror = () => reject(new Error("decode failed"));
          i.src = sourceUrl;
        });
        originalImgRef.current = img;
        setOriginalImg(img);
      } catch {
        img = null;
      }
    }
    if (!img) {
      toast.warning("Could not load original to apply edits — using upload as-is");
      return imageId;
    }
    const blob = await renderEditedImage(img, edits);
    const file = new File([blob], "edited.png", { type: blob.type });
    const data = await uploadImage(file);
    setImageId(data.image_id);
    setUploadedEdits({ ...edits });
    return data.image_id;
  };

  const handleGenerate = async () => {
    if (!imageId) {
      toast.error("Upload an image first");
      return;
    }
    setLoading(true);
    setProgressLabel(editsAreActive(edits) ? "Applying edits…" : "Building LUT…");
    try {
      const currentId = await ensureCurrentImageId();
      const payload = {
        image_id: currentId,
        ...config,
        filaments: filaments.slice(0, maxActive),
        auto_order: autoOrder,
      };
      setProgressLabel("Matching pixels…");
      const data = await optimize(payload);
      setResult(data);
      // Tell JobHistory to refresh so the newly-saved job appears.
      window.dispatchEvent(new Event("lithoforge:job-finished"));
      toast.success(`Optimized · ΔE ${data.delta_e_mean.toFixed(2)}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Optimization failed");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setSourceUrl(null);
    setImageId(null);
    setResult(null);
    setOriginalImg(null);
    originalImgRef.current = null;
    setEdits({ ...DEFAULT_EDITS });
    setUploadedEdits({ ...DEFAULT_EDITS });
  };

  // Keep max_swaps consistent with the actual palette length: at most
  // (length-1) so a 5-filament palette caps at 4 swaps, etc.
  const handlePaletteSizeChange = (newSize) => {
    setConfig((c) => {
      const cap = Math.max(1, newSize - 1);
      if (c.max_swaps > cap) return { ...c, max_swaps: cap };
      return c;
    });
  };

  const handleSuggestPalette = async () => {
    if (!imageId) {
      toast.error("Upload an image first");
      return;
    }
    setSuggesting(true);
    try {
      const currentId = await ensureCurrentImageId();
      const suggested = await suggestPalette(currentId, maxActive, vibrancy);
      setFilaments(suggested);
      setAutoOrder(true);
      toast.success(
        `Suggested ${suggested.length} filaments: ${suggested
          .map((f) => f.name)
          .join(" · ")}`
      );
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Suggestion failed");
    } finally {
      setSuggesting(false);
    }
  };

  /**
   * Restore a job from the user's cloud history. Hydrates the visible
   * preview + downloads + config + palette without needing a re-upload.
   */
  const handleRestoreJob = (job) => {
    const req = job.request || {};
    setConfig((c) => ({
      ...c,
      width_mm: req.width_mm ?? c.width_mm,
      height_mm: req.height_mm ?? c.height_mm,
      thickness_mm: req.thickness_mm ?? c.thickness_mm,
      border_mm: req.border_mm ?? c.border_mm,
      layer_height_mm: req.layer_height_mm ?? c.layer_height_mm,
      max_swaps: req.max_swaps ?? c.max_swaps,
      geometry: req.geometry ?? c.geometry,
      curve_radius_mm: req.curve_radius_mm ?? c.curve_radius_mm,
      render_mode: req.render_mode ?? c.render_mode,
      relief: req.relief ?? c.relief,
    }));
    if (job.filaments?.length) {
      setFilaments(job.filaments);
    }
    // Surface the stored preview + downloads in the viewport. The job_id
    // matches the existing in-memory hydrated job server-side so exports
    // work the moment the user clicks Download.
    setResult({
      job_id: job.job_id,
      preview_png_base64: job.preview_png_base64,
      heightmap_png_base64: job.heightmap_png_base64,
      delta_e_mean: job.delta_e_mean,
      delta_e_p95: job.delta_e_p95,
      total_layers: job.total_layers,
      layer_allocation: job.allocation,
      filaments: job.filaments,
      swap_heights_mm: job.swap_heights_mm,
      timeline: job.timeline,
    });
    // Reset source-image state so the viewport shows the restored render
    // (not a stale upload from the current session).
    setSourceUrl(null);
    setImageId(null);
    setOriginalImg(null);
    originalImgRef.current = null;
  };

  const canGenerate = useMemo(
    () => !!imageId && filaments.length > 0 && !uploading,
    [imageId, filaments, uploading]
  );

  // JS-driven responsive switch so panels only mount once. Tailwind's
  // `hidden lg:grid` would render both trees, doubling state and effects
  // (two histograms, two file inputs, etc.). Breakpoint set at 1280 so
  // iPad landscape (1024) gets the comfortable touch layout too.
  const [isDesktop, setIsDesktop] = React.useState(
    typeof window !== "undefined" ? window.innerWidth >= 1280 : true
  );
  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 1280px)");
    const update = (e) => setIsDesktop(e.matches);
    setIsDesktop(mq.matches);
    if (mq.addEventListener) mq.addEventListener("change", update);
    else mq.addListener(update); // Safari < 14 fallback
    return () => {
      if (mq.removeEventListener) mq.removeEventListener("change", update);
      else mq.removeListener(update);
    };
  }, []);

  const configPanelEl = (
    <ConfigPanel
      config={config}
      setConfig={setConfig}
      disabled={loading}
      paletteLength={filaments.length}
      edits={edits}
      setEdits={setEdits}
      hasImage={!!imageId}
      originalImg={originalImg}
      filaments={filaments}
      setFilaments={setFilaments}
      vibrancy={vibrancy}
      setVibrancy={setVibrancy}
    />
  );

  const viewportEl = (
    <Viewport
      onFile={handleFile}
      sourceUrl={sourceUrl}
      result={result}
      loading={loading || uploading}
      progressLabel={uploading ? "Uploading…" : progressLabel}
      onReset={handleReset}
      renderMode={config.render_mode}
      edits={edits}
      setEdits={setEdits}
      filaments={filaments}
    />
  );

  const statsPanelEl = (
    <StatsPanel
      result={result}
      filaments={filaments}
      setFilaments={setFilaments}
      maxActive={maxActive}
      autoOrder={autoOrder}
      setAutoOrder={setAutoOrder}
      onSuggestPalette={handleSuggestPalette}
      suggesting={suggesting}
      canSuggest={!!imageId && !loading}
      vibrancy={vibrancy}
      setVibrancy={setVibrancy}
      onPaletteSizeChange={handlePaletteSizeChange}
      onRestoreJob={handleRestoreJob}
    />
  );

  return (
    <div className="App h-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      <Header
        onGenerate={handleGenerate}
        canGenerate={canGenerate}
        generating={loading}
      />

      {/* Desktop ≥ lg: 3-column control room */}
      {isDesktop ? (
        <div
          className="grid flex-1 overflow-hidden"
          style={{ gridTemplateColumns: "300px 1fr 340px" }}
          data-testid="desktop-layout"
        >
          <aside className="border-r border-zinc-800 overflow-hidden">
            {configPanelEl}
          </aside>
          <main className="overflow-hidden relative">{viewportEl}</main>
          <aside className="border-l border-zinc-800 overflow-hidden">
            {statsPanelEl}
          </aside>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-hidden" data-testid="mobile-layout">
          <MobileShell
            viewport={viewportEl}
            configPanel={configPanelEl}
            statsPanel={statsPanelEl}
          />
        </div>
      )}

      <LayerTimeline
        timeline={result?.timeline}
        totalLayers={result?.total_layers || 0}
      />

      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          className: "!rounded-none !border !border-zinc-700 !bg-zinc-950 !font-mono !text-xs",
        }}
      />
    </div>
  );
}

import React, { useEffect, useMemo, useRef, useState } from "react";
import "@/App.css";
import { toast, Toaster } from "sonner";
import { Header } from "@/components/Header";
import { Viewport } from "@/components/Viewport";
import { ConfigPanel } from "@/components/ConfigPanel";
import { StatsPanel } from "@/components/StatsPanel";
import { LayerTimeline } from "@/components/LayerTimeline";
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
  render_mode: "painting",
  relief: 0.5,
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

  const canGenerate = useMemo(
    () => !!imageId && filaments.length > 0 && !uploading,
    [imageId, filaments, uploading]
  );

  return (
    <div className="App h-screen flex flex-col bg-zinc-950 text-zinc-100 overflow-hidden">
      <Header
        onGenerate={handleGenerate}
        canGenerate={canGenerate}
        generating={loading}
      />

      <div
        className="flex-1 grid overflow-hidden"
        style={{ gridTemplateColumns: "300px 1fr 340px" }}
      >
        <aside className="border-r border-zinc-800 overflow-hidden">
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
        </aside>

        <main className="overflow-hidden relative">
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
          />
        </main>

        <aside className="border-l border-zinc-800 overflow-hidden">
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
          />
        </aside>
      </div>

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

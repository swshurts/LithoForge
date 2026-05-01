import React, { useEffect, useMemo, useState } from "react";
import "@/App.css";
import { toast, Toaster } from "sonner";
import { Header } from "@/components/Header";
import { Viewport } from "@/components/Viewport";
import { ConfigPanel } from "@/components/ConfigPanel";
import { StatsPanel } from "@/components/StatsPanel";
import { LayerTimeline } from "@/components/LayerTimeline";
import { getDefaultFilaments, optimize, uploadImage } from "@/lib/api";

const DEFAULT_CONFIG = {
  width_mm: 100,
  height_mm: 100,
  thickness_mm: 3.0,
  border_mm: 2,
  layer_height_mm: 0.12,
  max_swaps: 5,
  geometry: "flat",
  curve_radius_mm: 80,
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
    try {
      const url = URL.createObjectURL(file);
      setSourceUrl(url);
      const data = await uploadImage(file);
      setImageId(data.image_id);
      toast.success(`Loaded ${data.width}×${data.height} image`);
    } catch (e) {
      toast.error("Upload failed");
      setSourceUrl(null);
    } finally {
      setUploading(false);
    }
  };

  const handleGenerate = async () => {
    if (!imageId) {
      toast.error("Upload an image first");
      return;
    }
    setLoading(true);
    setProgressLabel("Building LUT…");
    try {
      const payload = {
        image_id: imageId,
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

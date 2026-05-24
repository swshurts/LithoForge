import React from "react";
import { Slider } from "./ui/slider";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Input } from "./ui/input";
import { ModeToggle } from "./ModeToggle";
import { ImageEditPanel } from "./ImageEditPanel";
import { PresetManager } from "./PresetManager";
import { HelpHint } from "./HelpHint";
import { PrinterSelect } from "./PrinterSelect";

const Row = ({ label, value, unit, children, testid }) => (
  <div className="space-y-2" data-testid={testid}>
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

export const ConfigPanel = ({
  config,
  setConfig,
  disabled,
  paletteLength = 6,
  edits,
  setEdits,
  hasImage,
  originalImg,
  filaments,
  setFilaments,
  vibrancy,
  setVibrancy,
}) => {
  const update = (key, v) => setConfig((c) => ({ ...c, [key]: v }));
  const isPainting = config.render_mode === "painting";
  const isDisc = config.geometry === "disc";
  const swapsMax = Math.max(1, Math.min(7, paletteLength - 1));

  return (
    <div
      className="h-full overflow-y-auto p-5 space-y-6"
      data-testid="config-panel"
    >
      {setFilaments && (
        <>
          <PresetManager
            config={config}
            setConfig={setConfig}
            filaments={filaments}
            setFilaments={setFilaments}
            edits={edits}
            setEdits={setEdits}
            vibrancy={vibrancy}
            setVibrancy={setVibrancy}
            disabled={disabled}
          />
          <div className="border-t border-zinc-800" />
        </>
      )}

      {hasImage && edits && setEdits && (
        <>
          <ImageEditPanel
            edits={edits}
            setEdits={setEdits}
            disabled={disabled}
            image={originalImg}
          />
          <div className="border-t border-zinc-800" />
        </>
      )}

      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500 mb-3 flex items-center gap-1.5">
          Render mode
          <HelpHint title="Lithophane vs Painting" testId="help-render-mode">
            <strong className="text-zinc-200">Lithophane</strong> uses
            Beer-Lambert subtractive mixing — colors emerge from light
            passing through stacked translucent layers. Requires a
            back-light to view properly.
            <br /><br />
            <strong className="text-zinc-200">Painting</strong> maps each
            pixel to a single solid filament on top. No back-light needed,
            high-contrast colors, but cannot mix to in-between hues.
          </HelpHint>
        </div>
        <ModeToggle
          mode={config.render_mode}
          setMode={(m) => update("render_mode", m)}
          disabled={disabled}
        />
        <div className="font-mono text-[9px] text-zinc-600 leading-relaxed mt-2">
          {isPainting
            ? "Each pixel shows one filament's pure colour — no back-light needed. Dark filaments print at the bottom, light on top."
            : "Colour comes from light transmitted through the stack. Needs a back-light. Full CMYKW subtractive mixing."}
        </div>
      </div>

      <div className="border-t border-zinc-800" />

      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500 mb-3 flex items-center gap-1.5">
          Geometry
          <HelpHint title="Geometry" testId="help-geometry">
            <strong className="text-zinc-200">Width × Height</strong> set
            the print's physical dimensions in mm.
            <br /><br />
            <strong className="text-zinc-200">Thickness</strong> is the
            total Z height — more thickness = more layers = better color
            depth (lithophane mode), but longer print time.
            <br /><br />
            <strong className="text-zinc-200">Shape</strong>: flat works
            for any printer; curved/cylindrical require the matching
            print bed orientation; circular disc gives a round print
            (with optional gentle dome).
          </HelpHint>
        </div>
        <div className="space-y-4">
          <div>
            <Label className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500 mb-2 block">
              Target printer
            </Label>
            <PrinterSelect
              value={config.printer_id}
              onChange={(v) => update("printer_id", v)}
              disabled={disabled}
              testId="config-printer-select"
            />
            <div className="font-mono text-[9px] text-zinc-600 mt-1 leading-relaxed">
              Drives bed size, layer-change G-code (M600 vs AMS tool change),
              and which export formats are recommended.
            </div>
          </div>

          <div>
            <Label className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500 mb-2 block">
              Shape
            </Label>
            <Select
              value={config.geometry}
              onValueChange={(v) => update("geometry", v)}
              disabled={disabled}
            >
              <SelectTrigger
                data-testid="geometry-select"
                className="rounded-none bg-zinc-950 border-zinc-800 font-mono text-xs h-9"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-none bg-zinc-950 border-zinc-800">
                <SelectItem value="flat" className="font-mono text-xs rounded-none">
                  Flat rectangle
                </SelectItem>
                <SelectItem value="curved" className="font-mono text-xs rounded-none">
                  Curved panel
                </SelectItem>
                <SelectItem
                  value="cylindrical"
                  className="font-mono text-xs rounded-none"
                >
                  Cylindrical
                </SelectItem>
                <SelectItem
                  value="disc"
                  className="font-mono text-xs rounded-none"
                >
                  Circular disc
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Row
            label={isDisc ? "Diameter" : "Width"}
            value={isDisc ? Math.min(config.width_mm, config.height_mm) : config.width_mm}
            unit="mm"
            testid="row-width"
          >
            <Slider
              data-testid="width-slider"
              value={[isDisc ? Math.min(config.width_mm, config.height_mm) : config.width_mm]}
              onValueChange={([v]) => {
                if (isDisc) {
                  setConfig((c) => ({ ...c, width_mm: v, height_mm: v }));
                } else {
                  update("width_mm", v);
                }
              }}
              min={40}
              max={300}
              step={1}
              disabled={disabled}
            />
          </Row>

          {!isDisc && (
            <Row
              label="Height"
              value={config.height_mm}
              unit="mm"
              testid="row-height"
            >
              <Slider
                data-testid="height-slider"
                value={[config.height_mm]}
                onValueChange={([v]) => update("height_mm", v)}
                min={40}
                max={300}
                step={1}
                disabled={disabled}
              />
            </Row>
          )}

          <Row
            label="Thickness"
            value={config.thickness_mm.toFixed(2)}
            unit="mm"
            testid="row-thickness"
          >
            <Slider
              data-testid="thickness-slider"
              value={[config.thickness_mm]}
              onValueChange={([v]) => update("thickness_mm", v)}
              min={1.5}
              max={6}
              step={0.05}
              disabled={disabled}
            />
          </Row>

          <Row
            label="Border"
            value={config.border_mm.toFixed(1)}
            unit="mm"
            testid="row-border"
          >
            <Slider
              data-testid="border-slider"
              value={[config.border_mm]}
              onValueChange={([v]) => update("border_mm", v)}
              min={0}
              max={10}
              step={0.5}
              disabled={disabled}
            />
          </Row>

          {config.geometry !== "flat" && config.geometry !== "disc" && (
            <Row
              label="Curve radius"
              value={config.curve_radius_mm}
              unit="mm"
              testid="row-curve"
            >
              <Slider
                data-testid="curve-slider"
                value={[config.curve_radius_mm]}
                onValueChange={([v]) => update("curve_radius_mm", v)}
                min={20}
                max={200}
                step={1}
                disabled={disabled}
              />
            </Row>
          )}

          {isDisc && (
            <Row
              label="Dome height"
              value={config.dome_mm.toFixed(1)}
              unit="mm"
              testid="row-dome"
            >
              <Slider
                data-testid="dome-slider"
                value={[config.dome_mm]}
                onValueChange={([v]) => update("dome_mm", v)}
                min={0}
                max={8}
                step={0.1}
                disabled={disabled}
              />
              <div className="font-mono text-[10px] text-zinc-600 mt-1">
                0 mm = flat disc · &gt;0 adds a gentle dome to the top face
              </div>
            </Row>
          )}
        </div>
      </div>

      <div className="border-t border-zinc-800" />

      <div>
        <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-zinc-500 mb-3 flex items-center gap-1.5">
          Print limits
          <HelpHint title="Layer height & swaps" testId="help-print-limits">
            <strong className="text-zinc-200">Layer height</strong>:
            thinner layers = better color resolution & smoother gradients
            but much longer print time.
            <br /><br />
            <strong className="text-zinc-200">Max colour swaps</strong>:
            how many times the printer changes filament during the print.
            Every swap adds purge waste; lower = faster prints but
            coarser color. Most printers cap at 8 swaps before purge
            tower height becomes a problem.
            <br /><br />
            <strong className="text-zinc-200">Relief</strong> (Painting
            mode): 0 = flat plateaus, 100 = full luminance bas-relief.
          </HelpHint>
        </div>
        <div className="space-y-4">
          <div>
            <Label className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500 mb-2 block">
              Layer height
            </Label>
            <Select
              value={String(config.layer_height_mm)}
              onValueChange={(v) => update("layer_height_mm", parseFloat(v))}
              disabled={disabled}
            >
              <SelectTrigger
                data-testid="layer-height-select"
                className="rounded-none bg-zinc-950 border-zinc-800 font-mono text-xs h-9"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="rounded-none bg-zinc-950 border-zinc-800">
                <SelectItem value="0.08" className="font-mono text-xs rounded-none">
                  0.08 mm (fine)
                </SelectItem>
                <SelectItem value="0.12" className="font-mono text-xs rounded-none">
                  0.12 mm (standard)
                </SelectItem>
                <SelectItem value="0.16" className="font-mono text-xs rounded-none">
                  0.16 mm (draft)
                </SelectItem>
                <SelectItem value="0.2" className="font-mono text-xs rounded-none">
                  0.20 mm (draft+)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Row
            label="Max colour swaps"
            value={config.max_swaps}
            unit=""
            testid="row-swaps"
          >
            <Slider
              data-testid="swaps-slider"
              value={[config.max_swaps]}
              onValueChange={([v]) => update("max_swaps", v)}
              min={1}
              max={swapsMax}
              step={1}
              disabled={disabled}
            />
            <div className="font-mono text-[10px] text-zinc-600 mt-1">
              uses {config.max_swaps + 1} filaments · {config.max_swaps} swap
              {config.max_swaps === 1 ? "" : "s"}
            </div>
          </Row>

          {isPainting && (
            <Row
              label="Relief"
              value={`${Math.round(config.relief * 100)}%`}
              unit=""
              testid="row-relief"
            >
              <Slider
                data-testid="relief-slider"
                value={[config.relief]}
                onValueChange={([v]) => update("relief", v)}
                min={0}
                max={1}
                step={0.05}
                disabled={disabled}
              />
              <div className="font-mono text-[10px] text-zinc-600 mt-1">
                0% = flat plateaus · 100% = luminance-driven bas-relief
              </div>
            </Row>
          )}

          {isPainting && (
            <Row
              label="Smoothing"
              value={`${Math.round((config.smoothing ?? 0) * 100)}%`}
              unit=""
              testid="row-smoothing"
            >
              <Slider
                data-testid="smoothing-slider"
                value={[config.smoothing ?? 0]}
                onValueChange={([v]) => update("smoothing", v)}
                min={0}
                max={1}
                step={0.05}
                disabled={disabled}
              />
              <div className="font-mono text-[10px] text-zinc-600 mt-1">
                Median pre-pass — reduces speckled boundaries on photos.
              </div>
            </Row>
          )}

          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="panel-muted p-3">
              <div className="text-[9px] uppercase tracking-[0.15em] text-zinc-500">
                Total layers
              </div>
              <div className="font-mono text-lg text-zinc-100 tabular-nums mt-1">
                {Math.max(1, Math.round(config.thickness_mm / config.layer_height_mm))}
              </div>
            </div>
            <div className="panel-muted p-3">
              <div className="text-[9px] uppercase tracking-[0.15em] text-zinc-500">
                Volume
              </div>
              <div className="font-mono text-lg text-zinc-100 tabular-nums mt-1">
                {isDisc
                  ? (Math.PI * Math.pow(Math.min(config.width_mm, config.height_mm) / 2, 2) * config.thickness_mm / 1000).toFixed(1)
                  : ((config.width_mm * config.height_mm * config.thickness_mm) / 1000).toFixed(1)}
                <span className="text-zinc-600 text-xs ml-1">cm³</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

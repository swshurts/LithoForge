import React from "react";
import { Link } from "react-router-dom";
import {
  Upload,
  Palette,
  Download,
  ArrowRight,
  ExternalLink,
  Store,
  Layers,
  Beaker,
  Library,
  Sparkles,
  Zap,
  CheckCircle2,
} from "lucide-react";
import { UserMenu } from "./UserMenu";

/* --------------------------------------------------------------------------
 * Header (landing variant)
 * Differs from the in-studio Header in that there's no Generate button,
 * no quota counter, and Sign-in / Studio are the primary calls.
 * The "Sister tool" link lives here as well as inside the studio header
 * (per user request).
 * ------------------------------------------------------------------------*/

const LandingHeader = () => (
  <header
    className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 flex items-center justify-between px-5 h-14 z-30"
    data-testid="landing-header"
  >
    <div className="flex items-center gap-4">
      <Link to="/" className="flex items-center gap-2.5 group">
        <div className="relative w-7 h-7 flex items-center justify-center">
          <div className="absolute inset-0 border border-zinc-700 group-hover:border-zinc-400 transition-colors" />
          <div className="absolute top-0 left-0 w-2 h-2 bg-cmyk-c" />
          <div className="absolute top-0 right-0 w-2 h-2 bg-cmyk-m" />
          <div className="absolute bottom-0 left-0 w-2 h-2 bg-cmyk-y" />
          <div className="absolute bottom-0 right-0 w-2 h-2 bg-cmyk-w border-l border-t border-zinc-700" />
        </div>
        <div>
          <div className="font-display text-base font-black tracking-tighter leading-none">
            LITHOFORGE
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-500 leading-none mt-0.5">
            Photo · Beer-Lambert
          </div>
        </div>
      </Link>
    </div>

    <div className="flex items-center gap-3">
      <a
        href="https://forgeslicer.com"
        target="_blank"
        rel="noopener noreferrer"
        data-testid="sister-tool-link"
        className="hidden md:flex items-center gap-1.5 pl-1 pr-2.5 py-1 border border-zinc-800 hover:border-amber-500/60 text-zinc-300 hover:text-zinc-100 font-mono text-[10px] uppercase tracking-[0.15em] transition-colors duration-150"
      >
        <img
          src="/forgeslicer-logo.webp"
          alt=""
          aria-hidden="true"
          className="w-4 h-4 object-cover border border-zinc-800"
          width={16}
          height={16}
        />
        Sister tool: ForgeSlicer.com&nbsp;→
      </a>
      <Link
        to="/marketplace"
        data-testid="landing-marketplace-link"
        className="hidden md:flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors"
      >
        <Store className="w-3.5 h-3.5" strokeWidth={1.5} />
        Marketplace
      </Link>
      <Link
        to="/pricing"
        data-testid="landing-pricing-link"
        className="hidden lg:block text-[10px] font-mono uppercase tracking-[0.15em] text-zinc-500 hover:text-zinc-200 transition-colors"
      >
        Pricing
      </Link>
      <UserMenu />
      <Link
        to="/studio"
        data-testid="landing-open-studio"
        className="flex items-center gap-2 bg-zinc-100 text-zinc-950 px-4 py-2 font-mono text-[11px] font-bold uppercase tracking-[0.2em] hover:bg-white transition-colors duration-150"
      >
        <Zap className="w-3.5 h-3.5" strokeWidth={2} />
        Open studio
      </Link>
    </div>
  </header>
);

/* --------------------------------------------------------------------------
 * Hero
 * ------------------------------------------------------------------------*/

const Hero = () => (
  <section className="relative overflow-hidden border-b border-zinc-800">
    {/* subtle CMYK accent grid behind the hero text */}
    <div
      className="absolute inset-0 opacity-[0.07] pointer-events-none"
      style={{
        backgroundImage:
          "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
        backgroundSize: "48px 48px",
      }}
    />
    <div className="absolute -top-24 -right-32 w-[480px] h-[480px] rounded-full bg-cmyk-m/[0.06] blur-3xl pointer-events-none" />
    <div className="absolute -bottom-24 -left-32 w-[420px] h-[420px] rounded-full bg-cmyk-y/[0.07] blur-3xl pointer-events-none" />

    <div className="relative max-w-6xl mx-auto px-6 py-24 lg:py-32 grid lg:grid-cols-[1.4fr_1fr] gap-12 items-center">
      <div className="space-y-7">
        <div className="inline-flex items-center gap-1.5 border border-zinc-700 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-400">
          <span className="w-1.5 h-1.5 bg-cmyk-c rounded-full" />
          CMYKW lithophanes · ΔE-Lab optimizer
        </div>
        <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.95]">
          Print photographs.
          <br />
          <span className="text-zinc-500">In</span> Multi colour.
        </h1>
        <p className="font-mono text-sm sm:text-base text-zinc-300 leading-relaxed max-w-xl">
          LithoForge turns any photo into a layered CMYKW lithophane that
          your filament printer can produce slice-by-slice — with
          colour-accurate Beer-Lambert layering, auto-injected
          M600 / tool-change pauses, and a marketplace to sell what you
          design.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/studio"
            data-testid="hero-open-studio"
            className="group flex items-center gap-2 bg-zinc-100 text-zinc-950 px-5 py-3 font-mono text-xs font-bold uppercase tracking-[0.2em] hover:bg-white transition-colors"
          >
            <Zap className="w-4 h-4" strokeWidth={2} />
            Open the studio
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </Link>
          <Link
            to="/marketplace"
            data-testid="hero-browse-marketplace"
            className="group flex items-center gap-2 border border-zinc-700 hover:border-zinc-400 text-zinc-200 hover:text-zinc-100 px-5 py-3 font-mono text-xs font-bold uppercase tracking-[0.2em] transition-colors"
          >
            <Store className="w-4 h-4" strokeWidth={1.5} />
            Browse marketplace
          </Link>
        </div>
        <div className="font-mono text-[10px] text-zinc-500 flex items-center gap-1.5">
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
          Unlimited downloads during beta · no card required to design
        </div>
      </div>

      {/* ForgeSlicer (sister-tool) anvil — above-the-fold hero visual */}
      <div className="hidden lg:block" data-testid="hero-anvil">
        <a
          href="https://forgeslicer.com"
          target="_blank"
          rel="noopener noreferrer"
          className="group block relative w-full aspect-square max-w-[420px] mx-auto border border-zinc-800 hover:border-amber-500/60 transition-colors overflow-hidden"
        >
          <img
            src="/forgeslicer-logo.webp"
            alt="ForgeSlicer.com — sister tool"
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
            width={420}
            height={420}
          />
          {/* gradient + label overlay */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/30 to-transparent" />
          <div className="absolute left-4 top-4 inline-flex items-center gap-1.5 px-2 py-1 bg-zinc-950/70 backdrop-blur-sm border border-amber-500/40 font-mono text-[10px] uppercase tracking-[0.22em] text-amber-300">
            <ExternalLink className="w-3 h-3" /> Sister tool
          </div>
          <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between font-mono text-[11px] text-zinc-100 group-hover:text-amber-100 transition-colors">
            <span className="font-bold tracking-wider">FORGESLICER.COM</span>
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </a>
        <div className="text-center font-mono text-[10px] text-zinc-600 mt-3 uppercase tracking-[0.18em]">
          Where the colour-aware slicing happens
        </div>
      </div>
    </div>
  </section>
);

/* --------------------------------------------------------------------------
 * How it works (3 steps)
 * ------------------------------------------------------------------------*/

const STEPS = [
  {
    n: "01",
    icon: Upload,
    label: "Upload a photograph",
    body: "Drag any JPG, PNG or WEBP into the studio. Crop, adjust brightness / contrast / saturation right in the viewport. Pick a shape — flat, curved, cylindrical or circular disc — and your target printer.",
  },
  {
    n: "02",
    icon: Palette,
    label: "Tune the palette",
    body: "Hit \"Suggest palette from photo\" to get an AI-picked CMYKW set, or pencil-edit each swatch. Match any colour to a real-world SKU from Bambu Lab, Polymaker, Prusament, eSun and 5 more brands by ΔE76 / ΔE2000.",
  },
  {
    n: "03",
    icon: Download,
    label: "Generate & print",
    body: "One click runs a Lab-space Beer-Lambert solve and shows you the simulated print. Download STL + 3MF with auto-pause G-code baked in for Bambu Studio, OrcaSlicer, PrusaSlicer, SuperSlicer and Cura — no manual layer edits needed.",
  },
];

const HowItWorks = () => (
  <section className="border-b border-zinc-800">
    <div className="max-w-6xl mx-auto px-6 py-20 space-y-10">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-2">
            How it works
          </div>
          <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
            From photo to printable in three steps.
          </h2>
        </div>
        <Link
          to="/studio"
          data-testid="how-it-works-cta"
          className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 hover:text-zinc-200 transition-colors flex items-center gap-1.5"
        >
          Try it now <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      <div className="grid md:grid-cols-3 gap-px bg-zinc-800 border border-zinc-800">
        {STEPS.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.n}
              data-testid={`step-${s.n}`}
              className="bg-zinc-950 p-6 sm:p-7 space-y-3 relative"
            >
              <div className="flex items-center justify-between">
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
                  Step {s.n}
                </div>
                <Icon className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
              </div>
              <div className="font-display text-xl font-black tracking-tight leading-tight">
                {s.label}
              </div>
              <p className="font-mono text-[11px] text-zinc-400 leading-relaxed">
                {s.body}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  </section>
);

/* --------------------------------------------------------------------------
 * Feature grid
 * ------------------------------------------------------------------------*/

const FEATURES = [
  {
    icon: Sparkles,
    title: "Lab-space ΔE optimizer",
    body: "Beer-Lambert transmission stack solved in CIE Lab. ΔE76 mean + p95 reported per render.",
  },
  {
    icon: Library,
    title: "9-brand filament library",
    body: "Browse ~120 manufacturer SKUs (Bambu, Polymaker, Prusament, eSun, Sunlu, Overture, Hatchbox, uJoybio3d, FlashForge). Keep a private inventory of what you own.",
  },
  {
    icon: Layers,
    title: "3MF with auto-pause",
    body: "Outputs Bambu-compatible 3MF + Prusa/Orca M600 G-code injected at the right layers. No manual filament-change scripts.",
  },
  {
    icon: Beaker,
    title: "Geometry options",
    body: "Flat panel, gentle curve, cylindrical or circular disc with dome. Disc-mode masks the print to a perfect inscribed circle.",
  },
  {
    icon: Store,
    title: "Built-in marketplace",
    body: "Publish any render to a public storefront. Buyers can purchase as guests via Stripe; creators get 94% per sale.",
  },
  {
    icon: CheckCircle2,
    title: "Library compatibility check",
    body: "Score any palette against your private filament library. ΔE-coded warnings surface SKUs that won't reproduce closely before you commit a print.",
  },
];

const FeatureGrid = () => (
  <section className="border-b border-zinc-800">
    <div className="max-w-6xl mx-auto px-6 py-20 space-y-10">
      <div className="max-w-2xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-2">
          What's inside
        </div>
        <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
          Tools that respect your printer's actual limits.
        </h2>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-zinc-800 border border-zinc-800">
        {FEATURES.map((f, i) => {
          const Icon = f.icon;
          return (
            <div
              key={i}
              data-testid={`feature-${i}`}
              className="bg-zinc-950 p-5 sm:p-6 space-y-3 hover:bg-zinc-900/60 transition-colors"
            >
              <div className="w-9 h-9 border border-zinc-800 flex items-center justify-center">
                <Icon className="w-4 h-4 text-zinc-300" strokeWidth={1.5} />
              </div>
              <div className="font-display text-base font-black tracking-tight">
                {f.title}
              </div>
              <p className="font-mono text-[11px] text-zinc-500 leading-relaxed">
                {f.body}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  </section>
);

/* --------------------------------------------------------------------------
 * Sister-tool plug
 * ------------------------------------------------------------------------*/

const SisterTool = () => (
  <section className="border-b border-zinc-800">
    <div className="max-w-6xl mx-auto px-6 py-16">
      <a
        href="https://forgeslicer.com"
        target="_blank"
        rel="noopener noreferrer"
        data-testid="sister-tool-banner"
        className="group block border border-zinc-800 hover:border-amber-500/60 transition-colors p-2 sm:p-3"
      >
        <div className="sm:flex items-stretch gap-6">
          <div
            className="relative flex-shrink-0 w-full sm:w-56 aspect-square bg-zinc-900 overflow-hidden border border-zinc-800 group-hover:border-amber-500/40 transition-colors"
            data-testid="sister-tool-logo"
          >
            <img
              src="/forgeslicer-logo.webp"
              alt="ForgeSlicer.com — anvil with hot steel and sparks"
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
              loading="lazy"
              width={448}
              height={448}
            />
            {/* radial vignette to blend the image into the dark panel */}
            <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-black/40" />
          </div>
          <div className="flex-1 flex flex-col justify-center px-4 py-5 sm:py-2 space-y-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-amber-400/70 flex items-center gap-1.5">
              <ExternalLink className="w-3 h-3" /> Sister tool
            </div>
            <div className="font-display text-2xl sm:text-3xl font-black tracking-tight leading-tight">
              ForgeSlicer.com — colour-aware slicing.
            </div>
            <p className="font-mono text-[11px] text-zinc-400 max-w-xl leading-relaxed">
              LithoForge designs lithophanes; ForgeSlicer prepares the
              G-code. Use them together for a colour-managed pipeline
              from photograph to print bed.
            </p>
            <div className="pt-2 flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.2em] text-zinc-300 group-hover:text-amber-100 transition-colors">
              Visit ForgeSlicer.com
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </div>
          </div>
        </div>
      </a>
    </div>
  </section>
);

/* --------------------------------------------------------------------------
 * Final CTA + Footer
 * ------------------------------------------------------------------------*/

const FinalCTA = () => (
  <section className="border-b border-zinc-800">
    <div className="max-w-6xl mx-auto px-6 py-20 text-center space-y-6">
      <h2 className="font-display text-4xl sm:text-5xl font-black tracking-tighter leading-[0.95]">
        Ready to print a photograph?
      </h2>
      <p className="font-mono text-sm text-zinc-400 max-w-lg mx-auto">
        Five free downloads while you experiment. No account needed to
        design. Sign in only when you want to keep a filament library
        or publish to the marketplace.
      </p>
      <div className="pt-2">
        <Link
          to="/studio"
          data-testid="final-cta"
          className="inline-flex items-center gap-2 bg-zinc-100 text-zinc-950 px-6 py-3.5 font-mono text-xs font-bold uppercase tracking-[0.22em] hover:bg-white transition-colors"
        >
          <Zap className="w-4 h-4" strokeWidth={2} />
          Open the studio
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  </section>
);

const Footer = () => (
  <footer className="bg-zinc-950" data-testid="landing-footer">
    <div className="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-3 gap-8 items-start">
      <div>
        <div className="flex items-center gap-2.5">
          <div className="relative w-6 h-6 flex items-center justify-center">
            <div className="absolute inset-0 border border-zinc-700" />
            <div className="absolute top-0 left-0 w-1.5 h-1.5 bg-cmyk-c" />
            <div className="absolute top-0 right-0 w-1.5 h-1.5 bg-cmyk-m" />
            <div className="absolute bottom-0 left-0 w-1.5 h-1.5 bg-cmyk-y" />
            <div className="absolute bottom-0 right-0 w-1.5 h-1.5 bg-cmyk-w border-l border-t border-zinc-700" />
          </div>
          <div className="font-display text-sm font-black tracking-tighter">
            LITHOFORGE
          </div>
        </div>
        <div className="font-mono text-[10px] text-zinc-600 mt-3 leading-relaxed">
          A CMYKW lithophane designer built on Beer-Lambert
          transmission modelling.
        </div>
      </div>
      <div>
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-500 mb-2">
          App
        </div>
        <ul className="space-y-1.5 font-mono text-[11px]">
          <li><Link className="text-zinc-300 hover:text-zinc-100" to="/studio">Open the studio</Link></li>
          <li><Link className="text-zinc-300 hover:text-zinc-100" to="/marketplace">Marketplace</Link></li>
          <li><Link className="text-zinc-300 hover:text-zinc-100" to="/pricing">Pricing</Link></li>
        </ul>
      </div>
      <div>
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-500 mb-2">
          Adjacent
        </div>
        <ul className="space-y-1.5 font-mono text-[11px]">
          <li>
            <a
              className="text-zinc-300 hover:text-zinc-100 inline-flex items-center gap-1"
              href="https://forgeslicer.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              ForgeSlicer.com
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </li>
        </ul>
      </div>
    </div>
    <div className="border-t border-zinc-800 py-4 px-6 max-w-6xl mx-auto font-mono text-[9px] text-zinc-600 uppercase tracking-[0.18em] flex justify-between">
      <span>LithoForge · v1.0</span>
      <span>Photo · Beer-Lambert ΔE76</span>
    </div>
  </footer>
);

export const LandingPage = () => (
  <div
    className="min-h-screen bg-zinc-950 text-zinc-100"
    data-testid="landing-page"
  >
    <LandingHeader />
    <Hero />
    <HowItWorks />
    <FeatureGrid />
    <SisterTool />
    <FinalCTA />
    <Footer />
  </div>
);

export default LandingPage;

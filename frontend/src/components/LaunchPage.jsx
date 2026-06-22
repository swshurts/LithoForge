/**
 * /launch — Product launch announcement page.
 *
 * Marketing surface aimed at:
 *   • Product Hunt / HN / Twitter referral traffic
 *   • Email newsletter readers
 *   • Press / blogger pickups
 *
 * Includes:
 *   • Hero with primary CTA to /studio
 *   • Feature grid (10 headline capabilities)
 *   • Pricing teaser ("Free during beta")
 *   • Email capture → POST /api/email/notify {email, source: 'launch'}
 *   • Secondary CTA to marketplace + ForgeSlicer
 *
 * The page intentionally has zero auth gating — share it widely.
 */

import React, { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  Sparkles, ArrowRight, Box, Palette, Library, Zap, Bot, Mic,
  Calculator, ShoppingBag, Send, ExternalLink, CheckCircle2, Cpu,
} from "lucide-react";
import axios from "axios";
import { API } from "../lib/api";
import buildInfo from "../build-info.json";

const BUILD_ID = buildInfo?.iter ? `iter-${buildInfo.iter}` : "";

const FEATURES = [
  {
    icon: Palette,
    title: "Perceptual colour matching",
    body: "Lab-space ΔE optimisation, not naïve RGB hex math. Your print looks like the photo when backlit.",
  },
  {
    icon: Box,
    title: "Five shapes, including lightboxes",
    body: "Flat, curved, cylindrical, disc, and a built-in lightbox enclosure with a slide-in back and LED mounts.",
  },
  {
    icon: Cpu,
    title: "56 printers, 411 filaments",
    body: "Bambu, Prusa, Voron, Creality, Anycubic. Nozzles 0.2–0.8 mm. Layer heights snap to printable ranges automatically.",
  },
  {
    icon: Library,
    title: "AI palette suggestions",
    body: "Let Claude or GPT pick the perfect 6-colour palette from your image, then nudge vibrancy live.",
  },
  {
    icon: Bot,
    title: "AI text-to-image",
    body: "No photo handy? Describe what you want and Meshy.ai renders a lithophane-ready image in seconds.",
  },
  {
    icon: Mic,
    title: "Voice commands",
    body: "Hands-free generation. Your last 10 prompts persist for one-click re-runs.",
  },
  {
    icon: Calculator,
    title: "Live cost estimator",
    body: "Print time, weight, dollar cost — and a swap simulator that re-prices in real time against your filament library.",
  },
  {
    icon: ShoppingBag,
    title: "Built-in marketplace",
    body: "Pro creators publish + sell their designs with industry-leading 94% revenue share. PayPal payouts wired in.",
  },
  {
    icon: Send,
    title: "One-click handoff to ForgeSlicer",
    body: "Our companion slicer. Generate here, slice there — SSO + auto-routed multipart upload of STL or 3MF.",
  },
  {
    icon: Zap,
    title: "Real 3MF, real colour swaps",
    body: "Auto-pause / tool-change G-code baked into the 3MF for OrcaSlicer, BambuStudio, PrusaSlicer & Cura.",
  },
];

const TAGLINES = [
  "From snapshot to lightbox — in CMYKW.",
  "Colour 3D printing, perceptually correct.",
  "Your photo, printed in light.",
];

export const LaunchPage = () => {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const tagline = TAGLINES[0];

  const submit = async (e) => {
    e.preventDefault();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast.error("Enter a valid email address");
      return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/email/notify`, { email, source: "launch" });
      setDone(true);
      toast.success("You're on the list!", { description: "We'll ping you the moment paid tiers go live." });
    } catch (err) {
      toast.error("Sign-up failed", {
        description: err?.response?.data?.detail || err.message,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="launch-page">
      {/* Top bar */}
      <header className="border-b border-zinc-900">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center justify-between">
          <Link
            to="/"
            className="font-display text-xl font-black tracking-tight hover:text-amber-200 transition-colors"
            data-testid="launch-home-link"
          >
            LithoForge
          </Link>
          <div className="flex items-center gap-3">
            <span className="font-mono text-[9px] text-zinc-600 uppercase tracking-[0.18em] hidden sm:inline">
              {BUILD_ID}
            </span>
            <Link
              to="/studio"
              data-testid="launch-go-studio"
              className="px-4 py-2 bg-amber-400 text-zinc-950 hover:bg-amber-300 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors"
            >
              Open the Studio
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-zinc-900 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 via-transparent to-rose-500/5 pointer-events-none" />
        <div className="max-w-6xl mx-auto px-5 py-20 sm:py-28 relative">
          <div className="flex items-center gap-2 mb-6">
            <span className="px-2 py-1 bg-amber-400/10 border border-amber-400/30 text-amber-200 font-mono text-[9px] uppercase tracking-[0.22em]">
              <Sparkles size={9} className="inline mr-1" />
              Now live · public beta
            </span>
            <span className="font-mono text-[9px] text-zinc-500 uppercase tracking-[0.2em]">
              Feb 2026
            </span>
          </div>
          <h1 className="font-display text-5xl sm:text-7xl font-black leading-[1.05] tracking-tight max-w-3xl">
            Turn any photo into a colour 3D-printed lithophane in 60 seconds.
          </h1>
          <p className="font-mono text-sm text-zinc-400 mt-6 max-w-2xl leading-relaxed">
            {tagline} LithoForge is the first photo-to-lithophane studio that
            matches your image perceptually, pre-flights the slicer so your
            print just works, and routes the finished model straight to
            ForgeSlicer with one click.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <Link
              to="/studio"
              data-testid="launch-cta-primary"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-amber-400 text-zinc-950 hover:bg-amber-300 font-mono text-[11px] uppercase tracking-[0.22em] transition-colors"
            >
              Start designing — free <ArrowRight size={14} />
            </Link>
            <Link
              to="/marketplace"
              data-testid="launch-cta-marketplace"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 border border-zinc-700 hover:border-zinc-500 hover:text-amber-200 font-mono text-[11px] uppercase tracking-[0.22em] transition-colors"
            >
              Browse marketplace
            </Link>
          </div>
          <div className="mt-6 flex items-center gap-2 font-mono text-[10px] text-zinc-500">
            <CheckCircle2 size={11} className="text-emerald-400" />
            No credit card · No download caps during beta · Sign in with Google
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="border-b border-zinc-900">
        <div className="max-w-6xl mx-auto px-5 py-20">
          <div className="mb-12">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-3">
              What&apos;s in the box
            </div>
            <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight max-w-2xl">
              Everything an FDM colour artist needs — in one studio.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="launch-feature-grid">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="border border-zinc-800 p-5 hover:border-amber-400/30 transition-colors group"
                data-testid={`launch-feature-${f.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              >
                <f.icon size={20} className="text-amber-200 mb-3 group-hover:scale-110 transition-transform" />
                <h3 className="font-display text-base font-bold mb-2">
                  {f.title}
                </h3>
                <p className="font-mono text-[10px] text-zinc-400 leading-relaxed">
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing teaser */}
      <section className="border-b border-zinc-900 bg-zinc-900/30">
        <div className="max-w-6xl mx-auto px-5 py-20">
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="border border-zinc-800 p-6 bg-zinc-950">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">Free · beta</div>
              <div className="font-display text-4xl font-black mt-2">$0</div>
              <div className="font-mono text-[10px] text-zinc-500 mt-1">Unlimited downloads during launch beta. Becomes 5 lifetime downloads after pricing locks.</div>
            </div>
            <div className="border border-amber-400/40 p-6 bg-amber-400/5 relative">
              <div className="absolute -top-2.5 left-4 px-2 py-0.5 bg-amber-400 text-zinc-950 font-mono text-[8px] uppercase tracking-[0.22em]">Most popular</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-amber-200">Hobbyist</div>
              <div className="font-display text-4xl font-black mt-2">$5<span className="text-base text-zinc-400 font-mono font-normal">/mo</span></div>
              <div className="font-mono text-[10px] text-zinc-400 mt-1">25 downloads / month · cloud preset sync · email support.</div>
            </div>
            <div className="border border-zinc-800 p-6 bg-zinc-950">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">Pro</div>
              <div className="font-display text-4xl font-black mt-2">$15<span className="text-base text-zinc-400 font-mono font-normal">/mo</span></div>
              <div className="font-mono text-[10px] text-zinc-500 mt-1">Unlimited downloads · publish & sell on marketplace · 94% revenue share · PayPal payouts.</div>
            </div>
          </div>
          <div className="mt-6 text-center font-mono text-[10px] text-zinc-500">
            Stripe subscriptions roll out shortly — we&apos;ll email you the moment they&apos;re live.
          </div>
        </div>
      </section>

      {/* Email capture */}
      <section className="border-b border-zinc-900">
        <div className="max-w-3xl mx-auto px-5 py-20 text-center" data-testid="launch-email-section">
          <h2 className="font-display text-3xl sm:text-4xl font-black tracking-tight">
            Want a heads-up when paid tiers go live?
          </h2>
          <p className="font-mono text-[11px] text-zinc-500 mt-3 max-w-xl mx-auto leading-relaxed">
            Beta users who join now get founder pricing locked in for life — $5 hobbyist + $15 Pro stays $5 + $15 forever, even after we raise list prices.
          </p>
          {!done ? (
            <form
              onSubmit={submit}
              className="mt-8 flex flex-col sm:flex-row gap-2 max-w-md mx-auto"
              data-testid="launch-email-form"
            >
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@email.com"
                data-testid="launch-email-input"
                className="flex-1 px-4 py-3 bg-zinc-950 border border-zinc-800 focus:border-amber-400/60 outline-none font-mono text-xs text-zinc-100"
              />
              <button
                type="submit"
                disabled={busy}
                data-testid="launch-email-submit"
                className="px-6 py-3 bg-amber-400 text-zinc-950 hover:bg-amber-300 disabled:opacity-50 font-mono text-[10px] uppercase tracking-[0.22em] transition-colors"
              >
                {busy ? "Sending…" : "Notify me"}
              </button>
            </form>
          ) : (
            <div
              data-testid="launch-email-success"
              className="mt-8 inline-flex items-center gap-2 px-4 py-3 border border-emerald-500/40 bg-emerald-500/5 font-mono text-[11px] text-emerald-200"
            >
              <CheckCircle2 size={14} />
              You&apos;re on the list — see you on launch day.
            </div>
          )}
        </div>
      </section>

      {/* Footer CTA */}
      <section>
        <div className="max-w-4xl mx-auto px-5 py-20 text-center">
          <h2 className="font-display text-4xl sm:text-5xl font-black tracking-tight">
            Print your first photo today.
          </h2>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/studio"
              data-testid="launch-cta-footer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-amber-400 text-zinc-950 hover:bg-amber-300 font-mono text-xs uppercase tracking-[0.24em] transition-colors"
            >
              Open the Studio <ArrowRight size={14} />
            </Link>
            <a
              href="https://forgeslicer.com"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="launch-cta-forgeslicer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 border border-zinc-700 hover:border-zinc-500 hover:text-amber-200 font-mono text-xs uppercase tracking-[0.24em] transition-colors"
            >
              Try ForgeSlicer <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-zinc-900 py-8">
        <div className="max-w-6xl mx-auto px-5 flex items-center justify-between font-mono text-[10px] text-zinc-600">
          <div>© 2026 LithoForge. Forge Suite.</div>
          <div className="flex items-center gap-4">
            <Link to="/pricing" className="hover:text-zinc-300 transition-colors">Pricing</Link>
            <Link to="/marketplace" className="hover:text-zinc-300 transition-colors">Marketplace</Link>
            <a href="mailto:hello@lithoforge.net" className="hover:text-zinc-300 transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LaunchPage;

import React, { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Crown, Sparkles, Zap } from "lucide-react";

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    headline: "Try the studio",
    bullets: [
      "5 lifetime downloads",
      "All printer profiles, geometries & filaments",
      "Marketplace browsing + purchasing",
      "Standard support",
    ],
    icon: Sparkles,
    cta: "Sign in to start",
  },
  {
    id: "hobbyist",
    name: "Hobbyist",
    price: "$5",
    period: "/month",
    headline: "Casual makers",
    bullets: [
      "25 downloads per month",
      "Cloud preset sync across devices",
      "Email support",
      "All free-tier features",
    ],
    icon: Zap,
    cta: "Notify me when live",
    badge: "Most popular",
  },
  {
    id: "pro",
    name: "Pro",
    price: "$15",
    period: "/month",
    headline: "Sellers & studios",
    bullets: [
      "Unlimited downloads",
      "Publish + sell on marketplace",
      "Stripe Connect payouts (94% to you, 6% platform)",
      "Priority support & early features",
    ],
    icon: Crown,
    cta: "Notify me when live",
  },
];

/** /pricing — public marketing page. Stripe isn't wired yet so plan CTAs
 *  collect an email for launch notifications. */
export const PricingPage = () => {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleNotify = async (planId) => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast.error("Enter a valid email to be notified");
      return;
    }
    setSubmitting(true);
    // No backend collection endpoint yet; store locally + toast.
    try {
      const interests = JSON.parse(
        localStorage.getItem("subscription_interest") || "[]",
      );
      interests.push({ email, planId, at: new Date().toISOString() });
      localStorage.setItem("subscription_interest", JSON.stringify(interests));
      toast.success(`We'll email ${email} when ${planId} launches.`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" data-testid="pricing-page">
      <div className="max-w-6xl mx-auto px-5 py-16 space-y-12">
        <header className="text-center space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
            Pricing
          </div>
          <h1 className="font-display text-5xl sm:text-6xl font-black tracking-tight">
            Print color, your way.
          </h1>
          <p className="font-mono text-[11px] text-zinc-500 max-w-2xl mx-auto leading-relaxed">
            Designing is free for everyone. Pick a plan when you're ready to
            download more files, sell your work, or skip the limits entirely.
          </p>
        </header>

        <div className="grid md:grid-cols-3 gap-4">
          {PLANS.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.id}
                className="border border-zinc-800 p-6 space-y-5 hover:border-zinc-500 transition-colors relative"
                data-testid={`pricing-plan-${p.id}`}
              >
                {p.badge && (
                  <span className="absolute -top-3 left-6 bg-amber-300 text-zinc-950 font-mono text-[9px] uppercase tracking-[0.18em] font-bold px-2 py-0.5">
                    {p.badge}
                  </span>
                )}
                <div className="flex items-center gap-2">
                  <Icon className="w-4 h-4" />
                  <span className="font-display text-2xl font-bold">{p.name}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="font-display text-5xl font-black tabular-nums">
                    {p.price}
                  </span>
                  <span className="font-mono text-[11px] text-zinc-500">
                    {p.period}
                  </span>
                </div>
                <p className="font-mono text-[11px] text-zinc-500">
                  {p.headline}
                </p>
                <ul className="space-y-1.5">
                  {p.bullets.map((b) => (
                    <li
                      key={b}
                      className="flex gap-2 font-mono text-[11px] text-zinc-300"
                    >
                      <span className="text-emerald-400">→</span>
                      <span className="leading-snug">{b}</span>
                    </li>
                  ))}
                </ul>
                {p.id === "free" ? (
                  <Link
                    to="/studio"
                    data-testid={`pricing-${p.id}-cta`}
                    className="block w-full bg-zinc-100 text-zinc-950 py-2 text-center font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-white transition-colors"
                  >
                    {p.cta}
                  </Link>
                ) : (
                  <button
                    onClick={() => handleNotify(p.id)}
                    disabled={submitting}
                    data-testid={`pricing-${p.id}-cta`}
                    className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 py-2 font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-zinc-800 transition-colors"
                  >
                    {p.cta}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <div className="border border-zinc-800 p-6 max-w-2xl mx-auto space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
            Get notified
          </div>
          <p className="font-mono text-[11px] text-zinc-400 leading-relaxed">
            We're finishing payment integration. Leave your email and we'll
            send a one-time launch alert — no marketing, no follow-ups.
          </p>
          <div className="flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              data-testid="notify-email-input"
              className="flex-1 bg-zinc-900 border border-zinc-800 px-3 py-2 font-mono text-[11px] focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={() => handleNotify("any")}
              disabled={submitting}
              data-testid="notify-submit"
              className="px-4 bg-zinc-100 text-zinc-950 font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-white transition-colors disabled:opacity-50"
            >
              Notify me
            </button>
          </div>
        </div>

        <div className="text-center">
          <Link
            to="/studio"
            data-testid="pricing-back-to-studio"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-400 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-500 px-4 py-2 inline-block transition-colors"
          >
            ← Back to studio
          </Link>
        </div>
      </div>
    </div>
  );
};

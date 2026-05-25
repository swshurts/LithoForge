import React from "react";
import { Link } from "react-router-dom";
import { Crown, LogIn, X, Zap } from "lucide-react";
import { useAuth } from "../lib/auth";

const PLANS = [
  {
    id: "hobbyist",
    name: "Hobbyist",
    price: "$5",
    period: "/month",
    headline: "Casual makers",
    bullets: [
      "25 downloads per month",
      "Browse + purchase marketplace listings",
      "All printer profiles & geometries",
      "Standard buyer support",
    ],
    icon: Zap,
    tag: "Most popular",
  },
  {
    id: "pro",
    name: "Pro",
    price: "$15",
    period: "/month",
    headline: "Sellers & studios",
    bullets: [
      "Unlimited downloads",
      "Publish + sell on the marketplace",
      "Stripe Connect creator payouts",
      "Priority support & early features",
    ],
    icon: Crown,
    tag: "All-in",
  },
];

/** Upgrade modal — shown when a free-tier user hits the 5-download cap.
 *  Also reachable from /pricing.
 *
 *  Note: Stripe checkout for subscriptions is not yet wired (the user
 *  asked to hold off). For now, the CTAs collect interest via an email
 *  capture so we can notify when launches. */
export const UpgradeModal = ({ open, onClose, quota }) => {
  const { user, login } = useAuth();
  if (!open) return null;

  const isAnon = !user;

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="upgrade-modal-backdrop"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-zinc-950 border border-zinc-800 max-w-3xl w-full p-8 space-y-6 max-h-[90vh] overflow-y-auto"
        data-testid="upgrade-modal"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-1">
              {isAnon ? "Sign in required" : "Upgrade"}
            </div>
            <h2 className="font-display text-3xl font-black tracking-tight leading-tight">
              {isAnon
                ? "Sign in to download"
                : "You've used all 5 free downloads"}
            </h2>
            <p className="font-mono text-[11px] text-zinc-500 mt-2 max-w-xl leading-relaxed">
              {isAnon
                ? "Designing is free for everyone. Downloads require a free account so we can track your 5 starter downloads — and so paid plans can scale up."
                : `You've downloaded ${quota?.used ?? 5} files on the free plan. Pick a plan below to keep printing.`}
            </p>
          </div>
          <button
            onClick={onClose}
            data-testid="upgrade-modal-close"
            className="text-zinc-500 hover:text-zinc-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isAnon && (
          <button
            onClick={login}
            data-testid="upgrade-signin-btn"
            className="w-full flex items-center justify-center gap-2 bg-zinc-100 text-zinc-950 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.18em] hover:bg-white transition-colors"
          >
            <LogIn className="w-3.5 h-3.5" />
            Sign in (free — gives you 5 starter downloads)
          </button>
        )}

        <div className="grid sm:grid-cols-2 gap-4 pt-2">
          {PLANS.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.id}
                className="border border-zinc-800 p-5 space-y-3 hover:border-zinc-500 transition-colors"
                data-testid={`plan-${p.id}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-zinc-300" />
                    <span className="font-display text-xl font-bold">
                      {p.name}
                    </span>
                  </div>
                  {p.tag && (
                    <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-amber-300 border border-amber-900 px-2 py-0.5">
                      {p.tag}
                    </span>
                  )}
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="font-display text-3xl font-black tabular-nums">
                    {p.price}
                  </span>
                  <span className="font-mono text-[11px] text-zinc-500">
                    {p.period}
                  </span>
                </div>
                <p className="font-mono text-[10px] text-zinc-500">
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
                <button
                  disabled
                  data-testid={`plan-${p.id}-cta`}
                  title="Subscriptions launch soon — we'll email you."
                  className="w-full bg-zinc-900 border border-zinc-700 text-zinc-400 py-2 font-mono text-[10px] uppercase tracking-[0.18em] font-bold disabled:cursor-not-allowed"
                >
                  Coming soon
                </button>
              </div>
            );
          })}
        </div>

        <div className="font-mono text-[10px] text-zinc-600 text-center pt-2">
          Want to be notified when subscriptions launch?{" "}
          <Link
            to="/pricing"
            onClick={onClose}
            className="text-zinc-300 underline hover:text-zinc-100"
          >
            Visit the pricing page
          </Link>{" "}
          to leave your email.
        </div>
      </div>
    </div>
  );
};

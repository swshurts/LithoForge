import React from "react";
import { Link } from "react-router-dom";
import { Crown, Infinity, Lock, Zap } from "lucide-react";
import { useQuota } from "../lib/quota";
import { useAuth } from "../lib/auth";

const TIER_BADGE = {
  free: { label: "Free", icon: Lock, cls: "text-zinc-400 border-zinc-700" },
  hobbyist: { label: "Hobbyist", icon: Zap, cls: "text-emerald-300 border-emerald-900" },
  pro: { label: "Pro", icon: Crown, cls: "text-amber-300 border-amber-900" },
  guest: { label: "Guest", icon: Lock, cls: "text-zinc-500 border-zinc-800" },
};

/** Compact quota counter for the studio header.
 *  Displays tier badge + uses-remaining + upgrade link. */
export const QuotaCounter = ({ compact = false }) => {
  const { quota, loading, showUpgrade } = useQuota();
  const { user } = useAuth();

  if (loading || !quota) return null;

  const tier = quota.tier || (user ? "free" : "guest");
  const badge = TIER_BADGE[tier] || TIER_BADGE.free;
  const Icon = badge.icon;
  const unlimited = quota.limit === null || quota.limit === undefined;
  const remaining = quota.remaining;
  // Beta: every signed-in user has unlimited downloads, so the
  // "Upgrade" CTA only makes sense for true guests (who'd be prompted
  // to sign in). Once Stripe is wired and free=5 again, switch back to
  // `tier === "free" || tier === "guest"`.
  const showUpgradeCTA = tier === "guest";

  return (
    <div
      className="flex items-center gap-2 font-mono text-[10px]"
      data-testid="quota-counter"
    >
      <span
        className={`inline-flex items-center gap-1 border px-2 py-1 uppercase tracking-[0.18em] ${badge.cls}`}
      >
        <Icon className="w-3 h-3" strokeWidth={1.5} />
        {badge.label}
      </span>
      {!compact && (
        <span className="text-zinc-500" data-testid="quota-text">
          {tier === "guest" ? (
            <span className="text-zinc-400">Sign in to download</span>
          ) : unlimited ? (
            <span className="inline-flex items-center gap-1">
              <Infinity className="w-3 h-3" />
              Unlimited during beta
            </span>
          ) : (
            <>
              <span
                className={
                  remaining === 0
                    ? "text-red-400 font-bold"
                    : remaining <= 1
                    ? "text-amber-300 font-bold"
                    : "text-zinc-300"
                }
              >
                {remaining}
              </span>
              <span className="text-zinc-600"> / {quota.limit}</span>{" "}
              downloads left
            </>
          )}
        </span>
      )}
      {showUpgradeCTA && !compact && (
        <button
          onClick={showUpgrade}
          data-testid="quota-upgrade-btn"
          className="ml-1 px-2 py-1 bg-zinc-100 text-zinc-950 uppercase tracking-[0.16em] font-bold hover:bg-white transition-colors"
        >
          Sign in
        </button>
      )}
      {showUpgradeCTA && compact && (
        <Link
          to="/pricing"
          className="text-zinc-300 underline hover:text-zinc-100 text-[10px]"
        >
          plans
        </Link>
      )}
    </div>
  );
};

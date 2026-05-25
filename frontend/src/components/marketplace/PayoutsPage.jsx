import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  HandCoins,
  Loader2,
} from "lucide-react";
import { useAuth } from "../../lib/auth";
import {
  getPayoutStatus,
  getPayoutTransactions,
  startPayoutOnboarding,
} from "../../lib/api";

/** /payouts — creator-facing payouts dashboard.
 *  Auth-required. Shows Stripe Connect onboarding state + a sales ledger. */
export const PayoutsPage = () => {
  const { user, loading: authLoading, login } = useAuth();
  const [status, setStatus] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const [s, l] = await Promise.all([
          getPayoutStatus(),
          getPayoutTransactions(),
        ]);
        if (!cancelled) {
          setStatus(s);
          setLedger(l);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const handleOnboard = async () => {
    setBusy(true);
    try {
      const { url } = await startPayoutOnboarding();
      window.location.href = url;
    } catch (e) {
      toast.error(
        e?.response?.data?.detail ||
          "Could not start payout onboarding. Try again in a minute.",
      );
      setBusy(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-500 font-mono text-xs">
        Loading…
      </div>
    );
  }

  if (!user) {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-100 p-6"
        data-testid="payouts-signin-gate"
      >
        <div className="max-w-md text-center space-y-4">
          <h1 className="font-display text-3xl font-black tracking-tight">
            Sign in to manage payouts
          </h1>
          <p className="font-mono text-[11px] text-zinc-500">
            Creator payouts require an account so we can attach your Stripe
            Connect details. Buyers can still purchase your listings —
            sign-in is only for receiving the money.
          </p>
          <button
            onClick={login}
            data-testid="payouts-signin-btn"
            className="px-4 py-2 bg-zinc-100 text-zinc-950 font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-white"
          >
            Sign in to continue
          </button>
          <Link
            to="/"
            className="block font-mono text-[10px] text-zinc-500 hover:text-zinc-200 underline mt-4"
          >
            ← Back to studio
          </Link>
        </div>
      </div>
    );
  }

  const onboarded = status?.has_account && status?.payouts_enabled;
  const partiallyOnboarded = status?.has_account && !status?.payouts_enabled;

  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100"
      data-testid="payouts-page"
    >
      <div className="max-w-5xl mx-auto px-5 py-10 space-y-10">
        <header className="flex items-center justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-1">
              Creator
            </div>
            <h1 className="font-display text-4xl font-black tracking-tight">
              Payouts
            </h1>
          </div>
          <Link
            to="/"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-400 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-500 px-3 py-2 transition-colors"
          >
            Studio →
          </Link>
        </header>

        {/* Connect status card */}
        <section
          className="border border-zinc-800 p-6 space-y-4"
          data-testid="payouts-status-card"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
                Stripe Connect status
              </div>
              <div className="flex items-center gap-2">
                {onboarded ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="font-display text-xl font-bold">
                      Payouts active
                    </span>
                  </>
                ) : partiallyOnboarded ? (
                  <>
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span className="font-display text-xl font-bold">
                      Onboarding incomplete
                    </span>
                  </>
                ) : (
                  <>
                    <HandCoins className="w-4 h-4 text-zinc-400" />
                    <span className="font-display text-xl font-bold">
                      Not yet set up
                    </span>
                  </>
                )}
              </div>
              <p className="font-mono text-[11px] text-zinc-500 max-w-xl leading-relaxed">
                {onboarded ? (
                  <>
                    Your Stripe account is connected and verified. Every
                    sale automatically transfers your 94% share within a
                    few seconds of the buyer's payment confirming.
                  </>
                ) : partiallyOnboarded ? (
                  <>
                    Stripe still needs more details (ID, bank account,
                    tax info) before they'll let us send you money. New
                    sales are held as "Owed" until you finish.
                  </>
                ) : (
                  <>
                    Set up Stripe Connect to receive automatic payouts on
                    every sale. We never see your bank details — Stripe
                    handles ID verification + transfers. The platform fee
                    stays at <strong>6%</strong>; you receive <strong>94%</strong>.
                  </>
                )}
              </p>
              {status?.account_id && (
                <div className="font-mono text-[9px] text-zinc-700">
                  Account · {status.account_id}
                </div>
              )}
            </div>
            <button
              onClick={handleOnboard}
              disabled={busy}
              data-testid="start-payout-onboarding"
              className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-950 font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-white disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <ExternalLink className="w-3.5 h-3.5" />
              )}
              {onboarded ? "Manage on Stripe" : partiallyOnboarded ? "Resume onboarding" : "Set up payouts"}
            </button>
          </div>
        </section>

        {/* Ledger summary */}
        <section className="grid grid-cols-2 gap-3">
          <div className="border border-zinc-800 p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2">
              Lifetime paid out
            </div>
            <div
              className="font-display text-3xl font-black tabular-nums text-emerald-300"
              data-testid="total-paid"
            >
              ${(ledger?.total_paid_usd ?? 0).toFixed(2)}
            </div>
          </div>
          <div className="border border-zinc-800 p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2">
              Owed (pending onboarding)
            </div>
            <div
              className="font-display text-3xl font-black tabular-nums text-amber-300"
              data-testid="total-pending"
            >
              ${(ledger?.total_pending_usd ?? 0).toFixed(2)}
            </div>
          </div>
        </section>

        {/* Transaction list */}
        <section data-testid="payouts-ledger">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-3">
            Recent sales
          </div>
          {!ledger?.transactions?.length && (
            <div className="font-mono text-[11px] text-zinc-600 border border-dashed border-zinc-800 p-8 text-center">
              No sales yet. Once a buyer purchases one of your listings,
              the transaction shows up here.
            </div>
          )}
          {ledger?.transactions?.map((t) => (
            <div
              key={t.session_id}
              className="grid grid-cols-12 gap-3 border-b border-zinc-900 py-3 font-mono text-[11px]"
              data-testid={`txn-${t.session_id}`}
            >
              <div className="col-span-3 text-zinc-500 truncate">
                {new Date(t.paid_at).toLocaleString()}
              </div>
              <div className="col-span-3 truncate text-zinc-300">
                {t.buyer_email}
              </div>
              <div className="col-span-2 text-zinc-500 tabular-nums">
                ${Number(t.amount_usd).toFixed(2)}
              </div>
              <div className="col-span-2 tabular-nums text-zinc-100">
                ${Number(t.creator_payout_usd).toFixed(2)}
              </div>
              <div className="col-span-2 text-right">
                <PayoutBadge status={t.payout_status} />
              </div>
              {t.transfer_failed_reason && (
                <div className="col-span-12 text-amber-400 text-[10px] mt-1">
                  ⚠ {t.transfer_failed_reason}
                </div>
              )}
            </div>
          ))}
        </section>
      </div>
    </div>
  );
};

const PayoutBadge = ({ status }) => {
  const map = {
    transferred: { label: "Paid", cls: "text-emerald-300 border-emerald-900" },
    owed: { label: "Owed", cls: "text-amber-300 border-amber-900" },
    pending: { label: "Pending", cls: "text-amber-300 border-amber-900" },
    failed: { label: "Failed", cls: "text-red-300 border-red-900" },
    skipped: { label: "—", cls: "text-zinc-500 border-zinc-800" },
  };
  const cfg = map[status] || map.owed;
  return (
    <span
      className={`inline-block border px-2 py-0.5 text-[9px] uppercase tracking-[0.18em] ${cfg.cls}`}
    >
      {cfg.label}
    </span>
  );
};

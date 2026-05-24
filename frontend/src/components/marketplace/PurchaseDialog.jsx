import React, { useState } from "react";
import { ShoppingBag, X } from "lucide-react";
import { createCheckoutSession, PLATFORM_FEE_PCT } from "../../lib/api";

/** Modal that collects buyer email + initiates Stripe Checkout.
 *
 *  Anonymous-friendly: no login required. Email is used so we can email
 *  the buyer their download link as backup.
 */
export const PurchaseDialog = ({ listing, onClose }) => {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const price = Number(listing.price_usd || 0);
  const fee = (price * PLATFORM_FEE_PCT) / 100;
  const creator = price - fee;
  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const submit = async (e) => {
    e.preventDefault();
    if (!validEmail) {
      setError("Please enter a valid email");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const { url } = await createCheckoutSession(listing.job_id, email);
      // Stash buyer email for the success page email-receipt UI.
      try {
        sessionStorage.setItem(`buyer_email_${listing.job_id}`, email);
      } catch {
        /* sessionStorage may be unavailable in private mode */
      }
      window.location.href = url;
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          "Could not start checkout. Please try again."
      );
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="purchase-dialog-backdrop"
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="bg-zinc-950 border border-zinc-800 max-w-md w-full p-6 space-y-5"
        data-testid="purchase-dialog"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-1">
              Checkout
            </div>
            <h2 className="font-display text-2xl font-black tracking-tight leading-tight">
              {listing.title}
            </h2>
            <div className="font-mono text-[11px] text-zinc-500 mt-1">
              by {listing.creator_name}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            data-testid="purchase-close-btn"
            className="text-zinc-500 hover:text-zinc-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="border border-zinc-800 p-3 space-y-1 font-mono text-[11px] tabular-nums">
          <div className="flex justify-between text-zinc-400">
            <span>Item price</span>
            <span>${price.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-600">
            <span>Platform fee ({PLATFORM_FEE_PCT}%)</span>
            <span>−${fee.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-600">
            <span>Creator receives</span>
            <span>${creator.toFixed(2)}</span>
          </div>
          <div className="border-t border-zinc-800 mt-2 pt-2 flex justify-between text-zinc-100 font-bold">
            <span>You pay</span>
            <span>${price.toFixed(2)} USD</span>
          </div>
        </div>

        <div>
          <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2 block">
            Email for download link
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError("");
            }}
            required
            placeholder="you@example.com"
            data-testid="purchase-email-input"
            className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 font-mono text-[12px] text-zinc-100 focus:outline-none focus:border-zinc-500"
          />
          <div className="font-mono text-[9px] text-zinc-600 mt-1 leading-relaxed">
            We'll email you the STL/3MF download link so it's safe to return
            to later. No account required.
          </div>
        </div>

        {error && (
          <div
            data-testid="purchase-error"
            className="font-mono text-[10px] text-red-400 border border-red-900 bg-red-950/40 px-2 py-1.5"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !validEmail}
          data-testid="purchase-submit-btn"
          className="w-full flex items-center justify-center gap-2 bg-zinc-100 text-zinc-950 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.2em] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white transition-colors"
        >
          <ShoppingBag className="w-3.5 h-3.5" />
          {submitting ? "Starting checkout…" : `Pay $${price.toFixed(2)}`}
        </button>

        <div className="font-mono text-[9px] text-zinc-600 text-center leading-relaxed">
          Payments by Stripe. After checkout you'll be redirected back to
          download your STL & 3MF files instantly.
        </div>
      </form>
    </div>
  );
};

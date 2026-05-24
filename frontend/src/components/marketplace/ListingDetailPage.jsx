import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Layers, ShoppingBag, User as UserIcon } from "lucide-react";
import { MarketplaceHeader } from "./MarketplaceHeader";
import { getListingDetail } from "../../lib/api";

export const ListingDetailPage = () => {
  const { jobId } = useParams();
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getListingDetail(jobId);
        if (!cancelled) setListing(data);
      } catch {
        if (!cancelled) setError("Listing not found");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  return (
    <div
      className="min-h-screen flex flex-col bg-zinc-950 text-zinc-100"
      data-testid="listing-detail-page"
    >
      <MarketplaceHeader subtitle="Listing" />
      <main className="flex-1 max-w-6xl mx-auto w-full px-5 py-10">
        {loading && (
          <div className="font-mono text-xs text-zinc-500">Loading…</div>
        )}
        {error && (
          <div className="font-mono text-xs text-red-400">{error}</div>
        )}
        {listing && (
          <div className="grid lg:grid-cols-[1.4fr_1fr] gap-10">
            {/* Preview */}
            <div className="border border-zinc-800 bg-zinc-900 overflow-hidden">
              {listing.preview_png_base64 ? (
                <img
                  src={`data:image/png;base64,${listing.preview_png_base64}`}
                  alt={listing.title}
                  className="w-full h-auto block"
                  draggable={false}
                  data-testid="listing-preview"
                />
              ) : (
                <div className="aspect-square" />
              )}
            </div>

            {/* Details */}
            <div className="space-y-6">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-2 flex items-center gap-1.5">
                  {listing.render_mode === "painting" ? "Painted" : "Lithophane"}
                  <span className="text-zinc-700">·</span>
                  {listing.total_layers} layers
                </div>
                <h1 className="font-display text-4xl font-black tracking-tight leading-none mb-1">
                  {listing.title}
                </h1>
                <Link
                  to={`/creator/${listing.creator_id}`}
                  className="inline-flex items-center gap-1.5 font-mono text-xs text-zinc-500 hover:text-zinc-200 transition-colors mt-2"
                  data-testid="listing-creator-link"
                >
                  <UserIcon className="w-3 h-3" />
                  by {listing.creator_name}
                </Link>
              </div>

              {listing.description && (
                <div className="font-mono text-[11px] leading-relaxed text-zinc-300 whitespace-pre-wrap border-l-2 border-zinc-800 pl-3">
                  {listing.description}
                </div>
              )}

              <div className="border border-zinc-800 p-5 space-y-3">
                <div className="flex items-baseline gap-2">
                  <span
                    className="font-display text-5xl font-black tabular-nums"
                    data-testid="listing-price"
                  >
                    ${listing.price_usd.toFixed(2)}
                  </span>
                  <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-[0.18em]">
                    USD
                  </span>
                </div>
                <button
                  disabled
                  data-testid="purchase-btn"
                  title="Coming soon — Stripe checkout ships in the next phase"
                  className="w-full flex items-center justify-center gap-2 bg-zinc-100 text-zinc-950 py-3 font-mono text-[11px] font-bold uppercase tracking-[0.2em] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ShoppingBag className="w-3.5 h-3.5" />
                  Buy via creator
                </button>
                <div className="font-mono text-[9px] text-zinc-600 leading-relaxed text-center">
                  Direct purchase + print fulfillment ships in the next
                  release. For now, message the creator to arrange a sale.
                </div>
              </div>

              <div className="font-mono text-[10px] text-zinc-600 flex items-center gap-1.5">
                <Layers className="w-3 h-3" />
                {listing.total_layers} layers · {listing.render_mode}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

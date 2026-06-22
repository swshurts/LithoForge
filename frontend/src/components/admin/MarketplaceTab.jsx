/**
 * Admin → Marketplace tab.
 *
 * Lists every currently-listed marketplace job (across all creators)
 * with checkbox selection so an admin can:
 *   - Unlist one with the row-level X button
 *   - Bulk unlist selected
 *   - Nuclear: Unlist EVERY listing (requires typing `UNLIST ALL`)
 *
 * Backend: GET /api/admin/marketplace/listings, POST /api/admin/marketplace/{id}/unlist,
 * POST /api/admin/marketplace/bulk-unlist.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Store, Trash2, X, AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";
import { API } from "../../lib/api";

const adminApi = axios.create({
  baseURL: `${API}/admin`,
  withCredentials: true,
});

export const MarketplaceTab = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [confirmAllText, setConfirmAllText] = useState("");
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await adminApi.get("/marketplace/listings", {
        params: { limit: 500 },
      });
      setRows(data || []);
      setSelected(new Set());
    } catch (e) {
      toast.error("Failed to load listings", { description: e?.response?.data?.detail || e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleSelected = (jobId) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(jobId)) next.delete(jobId); else next.add(jobId);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === rows.length) setSelected(new Set());
    else setSelected(new Set(rows.map((r) => r.job_id)));
  };

  const unlistOne = async (row) => {
    if (!window.confirm(`Unlist "${row.title || row.job_id}"?\n\nThe model stays in the creator's library — only the marketplace listing is removed.`)) return;
    setWorking(true);
    try {
      await adminApi.post(`/marketplace/${row.job_id}/unlist`);
      toast.success("Unlisted", { description: row.title || row.job_id });
      await load();
    } catch (e) {
      toast.error("Unlist failed", { description: e?.response?.data?.detail || e.message });
    } finally {
      setWorking(false);
    }
  };

  const unlistSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Unlist ${selected.size} listing(s)? This cannot be undone — creators can re-list later but the public marketplace will lose them now.`)) return;
    setWorking(true);
    try {
      const { data } = await adminApi.post("/marketplace/bulk-unlist", {
        job_ids: Array.from(selected),
      });
      toast.success(`Unlisted ${data.unlisted} of ${data.requested}`);
      await load();
    } catch (e) {
      toast.error("Bulk unlist failed", { description: e?.response?.data?.detail || e.message });
    } finally {
      setWorking(false);
    }
  };

  const unlistAll = async () => {
    if (confirmAllText !== "UNLIST ALL") {
      toast.error("Type UNLIST ALL to confirm");
      return;
    }
    setWorking(true);
    try {
      const { data } = await adminApi.post("/marketplace/bulk-unlist", {
        all: true,
        confirm: "UNLIST ALL",
      });
      toast.success(`Wiped ${data.unlisted} listing(s)`);
      setConfirmAllText("");
      await load();
    } catch (e) {
      toast.error("Wipe failed", { description: e?.response?.data?.detail || e.message });
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="p-6 space-y-6" data-testid="admin-marketplace-tab">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-2xl font-black flex items-center gap-2">
            <Store className="w-5 h-5" />
            Marketplace listings
          </h2>
          <p className="font-mono text-[10px] text-zinc-500 mt-1">
            {rows.length} active listing{rows.length === 1 ? "" : "s"} across all creators.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          data-testid="admin-marketplace-refresh"
          className="px-3 py-2 border border-zinc-700 hover:border-zinc-500 font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-400 hover:text-zinc-100 transition-colors flex items-center gap-2"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Reload
        </button>
      </div>

      {selected.size > 0 && (
        <div
          className="bg-amber-500/10 border border-amber-500/30 p-3 flex items-center justify-between"
          data-testid="admin-marketplace-bulk-bar"
        >
          <span className="font-mono text-[11px] text-amber-100">
            {selected.size} selected
          </span>
          <button
            onClick={unlistSelected}
            disabled={working}
            data-testid="admin-marketplace-unlist-selected"
            className="px-3 py-1.5 bg-amber-500 text-zinc-950 hover:bg-amber-400 disabled:opacity-50 font-mono text-[10px] uppercase tracking-[0.18em] flex items-center gap-1.5"
          >
            <Trash2 size={12} />
            Unlist selected
          </button>
        </div>
      )}

      <div className="border border-zinc-800 overflow-hidden">
        <table className="w-full" data-testid="admin-marketplace-table">
          <thead className="bg-zinc-900 border-b border-zinc-800">
            <tr className="text-left">
              <th className="px-3 py-2 w-8">
                <input
                  type="checkbox"
                  checked={rows.length > 0 && selected.size === rows.length}
                  onChange={toggleAll}
                  data-testid="admin-marketplace-select-all"
                  className="w-3.5 h-3.5"
                />
              </th>
              <th className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500">Title</th>
              <th className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500">Creator</th>
              <th className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500">Price</th>
              <th className="px-3 py-2 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500">Listed</th>
              <th className="px-3 py-2 w-12" />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan="6" className="px-3 py-10 text-center font-mono text-[10px] text-zinc-600">
                  No active listings.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr
                key={r.job_id}
                className="border-b border-zinc-900 hover:bg-zinc-900/50 transition-colors"
                data-testid={`admin-marketplace-row-${r.job_id}`}
              >
                <td className="px-3 py-2 align-top">
                  <input
                    type="checkbox"
                    checked={selected.has(r.job_id)}
                    onChange={() => toggleSelected(r.job_id)}
                    data-testid={`admin-marketplace-select-${r.job_id}`}
                    className="w-3.5 h-3.5"
                  />
                </td>
                <td className="px-3 py-2 align-top">
                  <div className="font-mono text-[11px] text-zinc-100 truncate max-w-[300px]" title={r.title}>
                    {r.title || <span className="text-zinc-600">(untitled)</span>}
                  </div>
                  <div className="font-mono text-[9px] text-zinc-600 truncate max-w-[300px]">
                    {r.job_id}
                  </div>
                </td>
                <td className="px-3 py-2 align-top">
                  <div className="font-mono text-[11px] text-zinc-300">
                    {r.creator_email}
                  </div>
                  {r.creator_is_admin && (
                    <div className="font-mono text-[8px] uppercase tracking-wider px-1.5 inline-block mt-0.5 border border-amber-700 text-amber-300">
                      Admin
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-[11px] text-zinc-300 align-top tabular-nums">
                  ${r.price_usd.toFixed(2)}
                </td>
                <td className="px-3 py-2 font-mono text-[10px] text-zinc-500 align-top">
                  {r.listed_at ? new Date(r.listed_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2 align-top">
                  <button
                    onClick={() => unlistOne(r)}
                    disabled={working}
                    title="Unlist this listing"
                    data-testid={`admin-marketplace-unlist-${r.job_id}`}
                    className="w-7 h-7 flex items-center justify-center border border-zinc-700 hover:border-rose-500 hover:text-rose-400 text-zinc-500 transition-colors"
                  >
                    <X size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div
        className="border border-rose-500/30 bg-rose-500/5 p-4 space-y-3"
        data-testid="admin-marketplace-danger-zone"
      >
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-rose-200">
          <AlertTriangle size={14} />
          Danger zone — wipe entire marketplace
        </div>
        <p className="font-mono text-[10px] text-zinc-400 leading-relaxed">
          Removes the <code>listing</code> field from every job in the database. Underlying models stay in creators' libraries — only the public marketplace presence is destroyed. Type <code className="text-rose-300">UNLIST ALL</code> below to enable the button.
        </p>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={confirmAllText}
            onChange={(e) => setConfirmAllText(e.target.value)}
            placeholder="Type UNLIST ALL"
            data-testid="admin-marketplace-confirm-input"
            className="flex-1 px-3 py-2 bg-zinc-950 border border-zinc-800 focus:border-rose-500/50 font-mono text-[11px] text-zinc-100 outline-none"
          />
          <button
            onClick={unlistAll}
            disabled={working || confirmAllText !== "UNLIST ALL"}
            data-testid="admin-marketplace-wipe-all"
            className="px-4 py-2 bg-rose-600 text-zinc-50 hover:bg-rose-500 disabled:opacity-30 disabled:cursor-not-allowed font-mono text-[10px] uppercase tracking-[0.18em] flex items-center gap-2"
          >
            <Trash2 size={12} />
            Wipe all
          </button>
        </div>
      </div>
    </div>
  );
};

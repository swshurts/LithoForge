/**
 * Admin moderation surface. Single-file component with three sections:
 *  - Sidebar (Users / Audit log tabs)
 *  - Users tab: debounced search + paginated table + detail panel
 *  - Audit log tab: read-only paginated stream
 *
 * Access gating: the wrapping <AdminLayout> calls /api/admin/me on
 * mount. If it 401s or 403s, we redirect to / — never render the
 * sidebar to non-admins. (Defence in depth — the server enforces it
 * anyway, but a moderation page flickering on screen before redirect
 * is a bad look.)
 *
 * All destructive actions use native window.confirm — cheap insurance
 * against fat-finger mistakes and zero dialog library overhead.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Users, ClipboardList, ShieldCheck, Ban, Trash2, HandCoins, Store } from "lucide-react";
import { toast } from "sonner";

import { API } from "../../lib/api";
import {
  adminGetPendingPayouts,
  adminListPayoutBatches,
  adminRunPayouts,
} from "../../lib/api";
import { MarketplaceTab } from "./MarketplaceTab";

const adminApi = axios.create({
  baseURL: `${API}/admin`,
  withCredentials: true,
});

const SidebarBtn = ({ active, onClick, icon: Icon, label, testid }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className={`w-full text-left px-4 py-3 flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.2em] transition-colors ${
      active
        ? "bg-zinc-900 text-zinc-100 border-l-2 border-zinc-100"
        : "text-zinc-500 hover:text-zinc-100 hover:bg-zinc-900/50 border-l-2 border-transparent"
    }`}
  >
    <Icon className="w-3.5 h-3.5" />
    {label}
  </button>
);

const UserRow = ({ user, selected, onClick }) => (
  <button
    onClick={onClick}
    data-testid={`admin-user-row-${user.user_id}`}
    className={`w-full text-left px-3 py-2 border-b border-zinc-900 transition-colors ${
      selected ? "bg-zinc-900" : "hover:bg-zinc-900/50"
    }`}
  >
    <div className="flex items-center gap-2">
      <span className="font-mono text-[11px] text-zinc-100 truncate flex-1">
        {user.email}
      </span>
      {user.is_super_admin && (
        <span className="font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 border border-amber-700 text-amber-300">
          Super
        </span>
      )}
      {user.is_admin && !user.is_super_admin && (
        <span className="font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 border border-sky-700 text-sky-300">
          Admin
        </span>
      )}
      {user.is_suspended && (
        <span className="font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 border border-red-700 text-red-300">
          Suspended
        </span>
      )}
    </div>
    <div className="font-mono text-[9px] text-zinc-600 mt-0.5">{user.user_id}</div>
  </button>
);

const UserDetail = ({ user, me, onRefresh }) => {
  // Track quotaInput as a derived value based on the user's id so when
  // a different user is selected the input resets. Using state +
  // useEffect would trip eslint's set-state-in-effect rule and risk a
  // race when the user prop changes between renders; deriving via
  // useState's lazy initializer keyed on user_id is cleaner.
  const [quotaInputs, setQuotaInputs] = useState({});
  const quotaInput =
    quotaInputs[user.user_id] ??
    (user.ai_quota_override == null ? "" : String(user.ai_quota_override));
  const setQuotaInput = (v) =>
    setQuotaInputs((m) => ({ ...m, [user.user_id]: v }));
  const [saving, setSaving] = useState(false);

  const toggleAdmin = async () => {
    if (!window.confirm(
      user.is_admin
        ? `Demote ${user.email} from admin?`
        : `Promote ${user.email} to admin?`
    )) return;
    try {
      await adminApi.post(`/users/${user.user_id}/admin`);
      toast.success(user.is_admin ? "Admin revoked" : "Admin granted");
      onRefresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  const toggleSuspend = async () => {
    if (!window.confirm(
      user.is_suspended
        ? `Lift suspension on ${user.email}?`
        : `Suspend ${user.email}? They will be signed out immediately and unable to sign in again.`
    )) return;
    try {
      await adminApi.post(`/users/${user.user_id}/suspend`);
      toast.success(user.is_suspended ? "Suspension lifted" : "User suspended");
      onRefresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
  };

  const saveQuota = async () => {
    setSaving(true);
    try {
      const payload = {
        ai_quota_override: quotaInput.trim() === "" ? null : Number(quotaInput),
      };
      if (
        payload.ai_quota_override != null &&
        (Number.isNaN(payload.ai_quota_override) || payload.ai_quota_override < 0)
      ) {
        toast.error("Quota must be a non-negative integer or blank");
        setSaving(false);
        return;
      }
      await adminApi.patch(`/users/${user.user_id}`, payload);
      toast.success("Quota override updated");
      onRefresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally {
      setSaving(false);
    }
  };

  // Block toggling a super-admin or suspending oneself.
  const isSelf = me && me.user_id === user.user_id;
  const canTouchAdmin = me?.is_super_admin && !user.is_super_admin && !isSelf;
  const canSuspend =
    !user.is_super_admin && !isSelf && (me?.is_super_admin || !user.is_admin);

  return (
    <div className="p-6 space-y-6" data-testid={`admin-user-detail-${user.user_id}`}>
      <div>
        <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-zinc-500 mb-1">
          User
        </div>
        <h2 className="font-display text-2xl font-black tracking-tight">
          {user.name || user.email}
        </h2>
        <div className="font-mono text-[11px] text-zinc-400 mt-1">{user.email}</div>
        <div className="font-mono text-[9px] text-zinc-600 mt-1">{user.user_id}</div>
      </div>

      {/* Flags */}
      <div className="grid grid-cols-3 gap-3 font-mono text-[10px]">
        <div className="border border-zinc-800 p-3">
          <div className="text-zinc-500 uppercase tracking-wider mb-1">Admin</div>
          <div className="text-zinc-100">{user.is_admin ? "Yes" : "No"}</div>
        </div>
        <div className="border border-zinc-800 p-3">
          <div className="text-zinc-500 uppercase tracking-wider mb-1">Super</div>
          <div className="text-zinc-100">{user.is_super_admin ? "Yes" : "No"}</div>
        </div>
        <div className="border border-zinc-800 p-3">
          <div className="text-zinc-500 uppercase tracking-wider mb-1">Suspended</div>
          <div className={user.is_suspended ? "text-red-400" : "text-zinc-100"}>
            {user.is_suspended ? "Yes" : "No"}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-zinc-500">
          Actions
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={toggleAdmin}
            disabled={!canTouchAdmin}
            data-testid="admin-toggle-admin-btn"
            className="flex items-center gap-2 px-3 py-2 border border-zinc-700 text-zinc-100 font-mono text-[10px] uppercase tracking-wider hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            {user.is_admin ? "Revoke admin" : "Grant admin"}
          </button>
          <button
            onClick={toggleSuspend}
            disabled={!canSuspend}
            data-testid="admin-toggle-suspend-btn"
            className={`flex items-center gap-2 px-3 py-2 border font-mono text-[10px] uppercase tracking-wider transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              user.is_suspended
                ? "border-emerald-700 text-emerald-300 hover:bg-emerald-950/30"
                : "border-red-700 text-red-300 hover:bg-red-950/30"
            }`}
          >
            <Ban className="w-3.5 h-3.5" />
            {user.is_suspended ? "Lift suspension" : "Suspend"}
          </button>
        </div>
        {!canTouchAdmin && !user.is_super_admin && (
          <div className="font-mono text-[9px] text-zinc-600">
            Only super-admins can grant/revoke admin.
          </div>
        )}
        {user.is_super_admin && (
          <div className="font-mono text-[9px] text-zinc-600">
            Super-admin status is managed via the SUPER_ADMIN_EMAILS env var,
            not from this UI.
          </div>
        )}
      </div>

      {/* AI quota override */}
      <div className="space-y-2">
        <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-zinc-500">
          AI quota override
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={quotaInput}
            onChange={(e) => setQuotaInput(e.target.value)}
            placeholder="(blank = use tier default)"
            data-testid="admin-quota-input"
            min={0}
            className="flex-1 bg-zinc-900 border border-zinc-800 px-3 py-2 font-mono text-[11px] text-zinc-100 focus:outline-none focus:border-zinc-500"
          />
          <button
            onClick={saveQuota}
            disabled={saving}
            data-testid="admin-quota-save-btn"
            className="px-3 py-2 border border-zinc-700 text-zinc-100 font-mono text-[10px] uppercase tracking-wider hover:bg-zinc-800 disabled:opacity-50"
          >
            Save
          </button>
        </div>
        <div className="font-mono text-[9px] text-zinc-600">
          Reserved field — bypasses per-tier AI generation cap when wired up.
        </div>
      </div>
    </div>
  );
};

const UsersTab = ({ me }) => {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [users, setUsers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);

  // 300ms debounce
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebounced(query.trim()), 300);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [query]);

  const [reloadTick, setReloadTick] = useState(0);
  const fetchUsers = useCallback(() => setReloadTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: "100" });
        if (debounced) params.set("q", debounced);
        const r = await adminApi.get(`/users?${params}`);
        if (!cancelled) setUsers(r.data);
      } catch {
        if (!cancelled) toast.error("Failed to load users");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [debounced, reloadTick]);

  const selected = users.find((u) => u.user_id === selectedId) || null;

  return (
    <div className="grid grid-cols-[360px_1fr] h-full overflow-hidden">
      <div className="border-r border-zinc-800 flex flex-col overflow-hidden">
        <div className="p-3 border-b border-zinc-800">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search email or name…"
            data-testid="admin-user-search-input"
            className="w-full bg-zinc-900 border border-zinc-800 px-3 py-2 font-mono text-[11px] text-zinc-100 focus:outline-none focus:border-zinc-500"
          />
          <div className="font-mono text-[9px] text-zinc-600 mt-1">
            {loading ? "Loading…" : `${users.length} result${users.length === 1 ? "" : "s"}`}
          </div>
        </div>
        <div className="overflow-y-auto flex-1" data-testid="admin-user-list">
          {users.map((u) => (
            <UserRow
              key={u.user_id}
              user={u}
              selected={u.user_id === selectedId}
              onClick={() => setSelectedId(u.user_id)}
            />
          ))}
          {users.length === 0 && !loading && (
            <div className="font-mono text-[10px] text-zinc-600 p-4 text-center">
              No users match
            </div>
          )}
        </div>
      </div>
      <div className="overflow-y-auto">
        {selected ? (
          <UserDetail user={selected} me={me} onRefresh={fetchUsers} />
        ) : (
          <div className="h-full flex items-center justify-center font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-600">
            Select a user
          </div>
        )}
      </div>
    </div>
  );
};

const AuditTab = () => {
  const [entries, setEntries] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: "200" });
        if (filter) params.set("action", filter);
        const r = await adminApi.get(`/audit?${params}`);
        if (!cancelled) setEntries(r.data);
      } catch {
        if (!cancelled) toast.error("Failed to load audit log");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filter]);

  return (
    <div className="p-6 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-xl font-black tracking-tight">
          Audit log
        </h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          data-testid="admin-audit-filter"
          className="bg-zinc-900 border border-zinc-800 px-2 py-1 font-mono text-[10px] text-zinc-100 focus:outline-none"
        >
          <option value="">All actions</option>
          <option value="toggle_admin">Toggle admin</option>
          <option value="toggle_suspend">Toggle suspend</option>
          <option value="patch_user">Patch user</option>
        </select>
      </div>
      <div className="border border-zinc-800" data-testid="admin-audit-list">
        <div className="grid grid-cols-[160px_140px_220px_1fr] gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-900 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500">
          <span>When</span>
          <span>Action</span>
          <span>Actor</span>
          <span>Payload</span>
        </div>
        {entries.map((e) => (
          <div
            key={`${e.created_at}-${e.action}-${e.actor_user_id}-${e.target_user_id || ""}`}
            className="grid grid-cols-[160px_140px_220px_1fr] gap-2 px-3 py-2 border-b border-zinc-900 font-mono text-[10px] text-zinc-300"
          >
            <span className="text-zinc-500">
              {new Date(e.created_at).toLocaleString(undefined, {
                month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit",
              })}
            </span>
            <span>{e.action}</span>
            <span className="text-zinc-400 truncate">{e.actor_email}</span>
            <span className="text-zinc-500 truncate">
              {e.target_user_id ? `→ ${e.target_user_id} ` : ""}
              {Object.keys(e.payload).length > 0 ? JSON.stringify(e.payload) : ""}
            </span>
          </div>
        ))}
        {entries.length === 0 && !loading && (
          <div className="font-mono text-[10px] text-zinc-600 p-6 text-center">
            No audit entries match
          </div>
        )}
      </div>
    </div>
  );
};

const PayoutsTab = () => {
  const [pending, setPending] = useState(null);
  const [batches, setBatches] = useState([]);
  const [running, setRunning] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [p, b] = await Promise.all([
        adminGetPendingPayouts(),
        adminListPayoutBatches(),
      ]);
      setPending(p);
      setBatches(b.batches || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not load payouts");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleRun = async () => {
    if (!window.confirm(
      `Trigger a manual PayPal payout batch now? This will charge real funds in live mode.`,
    )) return;
    setRunning(true);
    try {
      const r = await adminRunPayouts();
      if (r.ok) {
        toast.success(
          `Batch ${r.batch_id || "—"}: ${r.creators} creator(s), $${(r.total_usd || 0).toFixed(2)}`,
        );
      } else {
        toast.error(`Payout failed: ${r.error || "unknown error"}`);
      }
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Trigger failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div
      className="h-full overflow-auto px-6 py-6 space-y-8"
      data-testid="admin-payouts-tab"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display text-2xl font-black tracking-tight">
            PayPal Payouts
          </h2>
          <p className="font-mono text-[11px] text-zinc-500 mt-2 max-w-2xl">
            Weekly batch dispatches every Monday 00:00 UTC. Threshold:{" "}
            <strong className="text-zinc-300">
              ${pending?.threshold_usd?.toFixed?.(2) ?? "—"}
            </strong>
            {" · "}Mode:{" "}
            <strong className={pending?.mode === "live" ? "text-emerald-300" : "text-amber-300"}>
              {pending?.mode || "—"}
            </strong>
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running || (pending?.eligible_count ?? 0) === 0}
          data-testid="admin-run-payouts"
          className="px-4 py-2 bg-amber-200 text-zinc-950 font-mono text-[10px] uppercase tracking-[0.18em] font-bold hover:bg-amber-100 disabled:opacity-50"
        >
          {running ? "Running…" : "Run payouts now"}
        </button>
      </div>

      <section className="grid grid-cols-3 gap-3">
        <div className="border border-zinc-800 p-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2">
            Total pending
          </div>
          <div
            className="font-display text-3xl font-black tabular-nums text-zinc-100"
            data-testid="admin-total-pending"
          >
            ${(pending?.total_pending_usd ?? 0).toFixed(2)}
          </div>
        </div>
        <div className="border border-zinc-800 p-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2">
            Eligible creators
          </div>
          <div
            className="font-display text-3xl font-black tabular-nums text-emerald-300"
            data-testid="admin-eligible-count"
          >
            {pending?.eligible_count ?? 0}
          </div>
        </div>
        <div className="border border-zinc-800 p-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-2">
            Below threshold
          </div>
          <div className="font-display text-3xl font-black tabular-nums text-zinc-500">
            {pending?.below_threshold_count ?? 0}
          </div>
        </div>
      </section>

      <section>
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-3">
          Pending creators
        </div>
        <div className="border border-zinc-800">
          {(pending?.creators || []).length === 0 ? (
            <div className="p-4 font-mono text-[11px] text-zinc-600 text-center">
              No creators with pending balance.
            </div>
          ) : (
            pending.creators.map((c) => (
              <div
                key={c.user_id}
                className="grid grid-cols-12 gap-3 border-b border-zinc-900 py-2 px-3 font-mono text-[11px]"
                data-testid={`admin-pending-${c.user_id}`}
              >
                <div className="col-span-7 text-zinc-300 truncate">
                  {c.paypal_email}
                </div>
                <div className="col-span-3 text-zinc-500 truncate">
                  {c.user_id}
                </div>
                <div className="col-span-2 text-right tabular-nums text-zinc-100">
                  ${Number(c.pending_balance_usd).toFixed(2)}
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section>
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500 mb-3">
          Recent batches
        </div>
        <div className="border border-zinc-800">
          {batches.length === 0 ? (
            <div className="p-4 font-mono text-[11px] text-zinc-600 text-center">
              No batches yet.
            </div>
          ) : (
            batches.map((b) => (
              <div
                key={b.batch_id}
                className="grid grid-cols-12 gap-3 border-b border-zinc-900 py-2 px-3 font-mono text-[11px]"
                data-testid={`admin-batch-${b.batch_id}`}
              >
                <div className="col-span-3 text-zinc-500">
                  {b.created_at && new Date(b.created_at).toLocaleString()}
                </div>
                <div className="col-span-3 text-zinc-300 truncate">
                  {b.batch_id}
                </div>
                <div className="col-span-2 text-zinc-500 uppercase">
                  {b.mode}
                </div>
                <div className="col-span-2 text-zinc-100">{b.status}</div>
                <div className="col-span-2 text-right tabular-nums text-zinc-100">
                  ${Number(b.total_usd ?? 0).toFixed(2)}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};

export const AdminPage = () => {
  const [me, setMe] = useState(null);
  const [authStatus, setAuthStatus] = useState("checking"); // checking | ok | denied
  const [tab, setTab] = useState("users");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await adminApi.get("/me");
        if (!cancelled) {
          setMe(r.data);
          setAuthStatus("ok");
        }
      } catch {
        if (!cancelled) setAuthStatus("denied");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (authStatus === "checking") {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center font-mono text-[10px] uppercase tracking-[0.22em] text-zinc-500">
        Checking admin access…
      </div>
    );
  }
  if (authStatus === "denied") {
    return (
      <div
        className="min-h-screen bg-zinc-950 flex items-center justify-center"
        data-testid="admin-access-denied"
      >
        <div className="text-center space-y-3 max-w-md p-8 border border-zinc-800">
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-red-400">
            Access denied
          </div>
          <p className="font-mono text-[11px] text-zinc-400">
            You don&apos;t have admin permissions on this account.
          </p>
          <a
            href="/"
            className="inline-block font-mono text-[10px] uppercase tracking-wider text-zinc-500 hover:text-zinc-100 transition-colors"
          >
            ← Back to home
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      className="h-screen bg-zinc-950 text-zinc-100 grid grid-cols-[180px_1fr] overflow-hidden"
      data-testid="admin-page"
    >
      <aside className="border-r border-zinc-800 flex flex-col">
        <div className="px-4 py-4 border-b border-zinc-800">
          <div className="font-display text-base font-black tracking-tight">
            Admin
          </div>
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-zinc-500 mt-1">
            {me.is_super_admin ? "Super-admin" : "Admin"}
          </div>
          <div className="font-mono text-[9px] text-zinc-600 mt-1 truncate">
            {me.email}
          </div>
        </div>
        <SidebarBtn
          active={tab === "users"}
          onClick={() => setTab("users")}
          icon={Users}
          label="Users"
          testid="admin-tab-users"
        />
        <SidebarBtn
          active={tab === "audit"}
          onClick={() => setTab("audit")}
          icon={ClipboardList}
          label="Audit log"
          testid="admin-tab-audit"
        />
        <SidebarBtn
          active={tab === "payouts"}
          onClick={() => setTab("payouts")}
          icon={HandCoins}
          label="Payouts"
          testid="admin-tab-payouts"
        />
        <SidebarBtn
          active={tab === "marketplace"}
          onClick={() => setTab("marketplace")}
          icon={Store}
          label="Marketplace"
          testid="admin-tab-marketplace"
        />
        <a
          href="/"
          className="mt-auto px-4 py-3 font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500 hover:text-zinc-100 transition-colors border-t border-zinc-800"
        >
          ← Exit
        </a>
      </aside>
      <main className="overflow-hidden">
        {tab === "users" && <UsersTab me={me} />}
        {tab === "audit" && <AuditTab />}
        {tab === "payouts" && <PayoutsTab />}
        {tab === "marketplace" && <MarketplaceTab />}
      </main>
    </div>
  );
};

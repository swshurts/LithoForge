import React, { useEffect, useRef, useState } from "react";
import { LogIn, LogOut, User as UserIcon, Cloud } from "lucide-react";
import { useAuth } from "../lib/auth";

export const UserMenu = () => {
  const { user, loading, login, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (!menuRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", onClick);
    return () => document.removeEventListener("pointerdown", onClick);
  }, [open]);

  if (loading) {
    return (
      <div
        className="w-7 h-7 border border-zinc-800 animate-pulse bg-zinc-900"
        data-testid="user-menu-loading"
      />
    );
  }

  if (!user) {
    return (
      <button
        onClick={login}
        data-testid="login-btn"
        className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 hover:border-zinc-400 hover:bg-zinc-900 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-200 transition-colors"
      >
        <LogIn className="w-3 h-3" strokeWidth={1.5} />
        Sign in
      </button>
    );
  }

  const initial = (user.name || user.email || "?").trim()[0].toUpperCase();

  return (
    <div className="relative" ref={menuRef} data-testid="user-menu">
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="user-menu-toggle"
        className="flex items-center gap-2 px-2 py-1 border border-zinc-800 hover:border-zinc-500 transition-colors"
      >
        {user.picture ? (
          <img
            src={user.picture}
            alt=""
            className="w-6 h-6 object-cover border border-zinc-700"
            draggable={false}
          />
        ) : (
          <div className="w-6 h-6 bg-zinc-100 text-zinc-950 flex items-center justify-center font-mono text-[10px] font-bold">
            {initial}
          </div>
        )}
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-zinc-200 hidden md:inline max-w-[120px] truncate">
          {user.name || user.email}
        </span>
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-50 min-w-[220px] panel bg-zinc-950 border border-zinc-800"
          data-testid="user-menu-dropdown"
        >
          <div className="p-3 border-b border-zinc-800">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 mb-1 flex items-center gap-1.5">
              <UserIcon className="w-3 h-3" />
              Signed in
            </div>
            <div className="font-mono text-[11px] text-zinc-100 truncate">
              {user.name || "—"}
            </div>
            <div className="font-mono text-[10px] text-zinc-500 truncate">
              {user.email}
            </div>
          </div>
          <div className="p-2 border-b border-zinc-800 font-mono text-[9px] uppercase tracking-[0.18em] text-zinc-500 flex items-center gap-1.5">
            <Cloud className="w-3 h-3" />
            Presets synced to cloud
          </div>
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            data-testid="logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.15em] text-zinc-300 hover:bg-zinc-900 hover:text-red-300 transition-colors"
          >
            <LogOut className="w-3 h-3" strokeWidth={1.5} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
};

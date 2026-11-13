"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2, MoreHorizontal, type LucideIcon } from "lucide-react";

export interface MoreMenuItem {
  key: string;
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  href?: string;
  disabled?: boolean;
  busy?: boolean;
  hint?: string;
}

/** A labelled "More" button that opens a short menu of secondary actions. */
export default function MoreMenu({ items, label = "More" }: { items: MoreMenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (items.length === 0) return null;
  const row =
    "flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 dark:text-neutral-200 dark:hover:bg-neutral-800";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-neutral-100 hover:text-neutral-800 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
      >
        <MoreHorizontal className="h-3.5 w-3.5" /> {label}
      </button>
      {open && (
        <div role="menu" className="absolute left-0 top-8 z-30 w-60 overflow-hidden rounded-xl border border-neutral-200 bg-white py-1 shadow-xl dark:border-neutral-700 dark:bg-neutral-900">
          {items.map((it) => {
            const Icon = it.busy ? Loader2 : it.icon;
            const content = (
              <>
                <Icon className={`h-4 w-4 shrink-0 ${it.busy ? "animate-spin" : ""}`} />
                <span className="min-w-0 flex-1">
                  {it.label}
                  {it.hint && <span className="block text-[11px] text-neutral-500">{it.hint}</span>}
                </span>
              </>
            );
            return it.href ? (
              <Link key={it.key} role="menuitem" href={it.href} className={row} onClick={() => setOpen(false)}>
                {content}
              </Link>
            ) : (
              <button
                key={it.key}
                role="menuitem"
                disabled={it.disabled}
                className={row}
                onClick={() => {
                  setOpen(false);
                  it.onClick?.();
                }}
              >
                {content}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

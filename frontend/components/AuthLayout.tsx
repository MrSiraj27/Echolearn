"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

function Mark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="28" height="28" rx="7" fill="currentColor" />
      <path
        d="M8 10.5C8 9.11929 9.11929 8 10.5 8H17.5C18.8807 8 20 9.11929 20 10.5V15.5C20 16.8807 18.8807 18 17.5 18H12L9 20.5V18H10.5C9.11929 18 8 16.8807 8 15.5V10.5Z"
        fill="white"
        fillOpacity="0.92"
      />
    </svg>
  );
}

export default function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="auth-light min-h-screen grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] bg-white text-neutral-900">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between bg-neutral-950 text-neutral-50 px-16 py-12 relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.05] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:48px_48px]"
        />
        <Link href="/" className="relative flex items-center gap-2.5 text-neutral-50">
          <Mark />
          <span className="text-[15px] font-semibold tracking-tight">EchoLearn</span>
        </Link>

        <div className="relative max-w-md">
          <p className="text-2xl font-medium leading-snug tracking-tight text-neutral-50">
            &ldquo;Answer only from what&apos;s in the document. If it isn&apos;t there, say so.&rdquo;
          </p>
          <p className="mt-4 text-sm text-neutral-500">
            EchoLearn grounds every answer in your uploaded files — page numbers and sources included.
          </p>
        </div>

        <p className="relative text-xs text-neutral-600">© {new Date().getFullYear()} EchoLearn</p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center px-6 py-12">
        <motion.div
          className="w-full max-w-sm"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
        >
          <Link href="/" className="flex lg:hidden items-center gap-2 mb-10 text-neutral-900">
            <Mark />
            <span className="text-[15px] font-semibold tracking-tight">EchoLearn</span>
          </Link>

          <h1 className="text-xl font-semibold tracking-tight text-neutral-900">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-neutral-500">{subtitle}</p>}

          <div className="mt-8">{children}</div>
        </motion.div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import AuthLayout from "@/components/AuthLayout";
import { api, ApiError } from "@/lib/api";

function Spinner() {
  return (
    <motion.div
      className="h-7 w-7 rounded-full border-2 border-neutral-200 border-t-neutral-900 mx-auto"
      animate={{ rotate: 360 }}
      transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
    />
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }
    api
      .get<{ message: string }>(`/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then((data) => {
        setStatus("success");
        setMessage(data.message);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.detail : "Verification failed.");
      });
  }, [token]);

  const titles = {
    loading: "Verifying your email",
    success: "Email verified",
    error: "Verification failed",
  } as const;

  return (
    <AuthLayout title={titles[status]}>
      <AnimatePresence mode="wait">
        <motion.div
          key={status}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="space-y-4"
        >
          {status === "loading" && (
            <div className="flex flex-col items-center gap-3 py-2">
              <Spinner />
              <p className="text-sm text-neutral-500">Please wait while we verify your email...</p>
            </div>
          )}
          {status === "success" && (
            <div className="flex flex-col items-center gap-3 py-2">
              <div className="h-10 w-10 rounded-full bg-neutral-900 flex items-center justify-center text-white text-base">
                ✓
              </div>
              <p className="text-sm text-neutral-600 text-center">{message}</p>
            </div>
          )}
          {status === "error" && (
            <div className="flex flex-col items-center gap-3 py-2">
              <div className="h-10 w-10 rounded-full bg-red-50 flex items-center justify-center text-red-600 text-base">
                ✕
              </div>
              <p className="text-sm text-red-600 text-center">{message}</p>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
      {status !== "loading" && (
        <Link
          href="/login"
          className="text-sm font-medium underline underline-offset-4 mt-6 block text-center text-neutral-900"
        >
          Back to login
        </Link>
      )}
    </AuthLayout>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  );
}

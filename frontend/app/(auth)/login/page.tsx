"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import AuthLayout from "@/components/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Field, MotionForm, SubmitButton } from "@/components/motion-form";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNeedsVerification(false);
    setResendMessage(null);
    setLoading(true);
    try {
      const data = await api.post<{ access_token: string }>("/auth/login", { email, password });
      login(data.access_token);
      router.push("/chat");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setNeedsVerification(true);
        setError(err.detail);
      } else {
        setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setResendLoading(true);
    setResendMessage(null);
    try {
      await api.post("/auth/resend-verification", { email });
      setResendMessage("If that account exists and isn't verified, we've sent a new link.");
    } finally {
      setResendLoading(false);
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to continue chatting with your documents.">
      <MotionForm onSubmit={handleSubmit} className="space-y-4">
        <Field>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field>
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs font-medium underline underline-offset-4 text-neutral-900">
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key={error}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="text-sm text-red-600 space-y-2"
            >
              <p>{error}</p>
              {needsVerification && (
                <Button type="button" variant="outline" size="sm" onClick={handleResend} disabled={resendLoading}>
                  {resendLoading ? "Sending..." : "Resend verification email"}
                </Button>
              )}
              {resendMessage && <p className="text-neutral-500">{resendMessage}</p>}
            </motion.div>
          )}
        </AnimatePresence>
        <SubmitButton loading={loading} loadingText="Logging in...">
          Log in
        </SubmitButton>
      </MotionForm>
      <p className="text-sm text-neutral-500 mt-6 text-center">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="font-medium underline underline-offset-4 text-neutral-900">
          Sign up
        </Link>
      </p>
    </AuthLayout>
  );
}

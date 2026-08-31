"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import AuthLayout from "@/components/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { Field, MotionForm, AnimatedError, SubmitButton } from "@/components/motion-form";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      await api.post("/auth/signup", { name, email, password });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <AuthLayout title="Check your email" subtitle="We've sent you a verification link.">
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <p className="text-sm text-neutral-600">
            Click the link in the email we sent to{" "}
            <span className="font-medium text-neutral-900">{email}</span> to activate your account, then come back
            and log in.
          </p>
          <Link href="/login" className="text-sm font-medium underline underline-offset-4 mt-4 inline-block text-neutral-900">
            Back to login
          </Link>
        </motion.div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create your account" subtitle="Chat with your documents in seconds.">
      <MotionForm onSubmit={handleSubmit} className="space-y-4">
        <Field>
          <Label htmlFor="name">Name</Label>
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </Field>
        <AnimatePresence mode="wait">{error && <AnimatedError key={error}>{error}</AnimatedError>}</AnimatePresence>
        <SubmitButton loading={loading} loadingText="Creating account...">
          Create account
        </SubmitButton>
      </MotionForm>
      <p className="text-sm text-neutral-500 mt-6 text-center">
        Already have an account?{" "}
        <Link href="/login" className="font-medium underline underline-offset-4 text-neutral-900">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}

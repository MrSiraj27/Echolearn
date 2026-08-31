"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import AuthLayout from "@/components/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { Field, MotionForm, SubmitButton } from "@/components/motion-form";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  }

  if (submitted) {
    return (
      <AuthLayout title="Check your email">
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <p className="text-sm text-neutral-600">
            If that email exists, we&apos;ve sent a reset link to{" "}
            <span className="font-medium text-neutral-900">{email}</span>.
          </p>
          <Link href="/login" className="text-sm font-medium underline underline-offset-4 mt-4 inline-block text-neutral-900">
            Back to login
          </Link>
        </motion.div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Forgot password" subtitle="We'll email you a link to reset it.">
      <MotionForm onSubmit={handleSubmit} className="space-y-4">
        <Field>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <SubmitButton loading={loading} loadingText="Sending...">
          Send reset link
        </SubmitButton>
      </MotionForm>
      <p className="text-sm text-neutral-500 mt-6 text-center">
        <Link href="/login" className="font-medium underline underline-offset-4 text-neutral-900">
          Back to login
        </Link>
      </p>
    </AuthLayout>
  );
}

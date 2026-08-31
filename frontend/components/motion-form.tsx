"use client";

import { motion, type Variants } from "framer-motion";
import { ReactNode } from "react";
import { Button } from "@/components/ui/button";

export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.07, delayChildren: 0.15 },
  },
};

export const fieldVariant: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

export function MotionForm({
  onSubmit,
  children,
  className,
}: {
  onSubmit: (e: React.FormEvent) => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.form
      onSubmit={onSubmit}
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      {children}
    </motion.form>
  );
}

export function Field({ children }: { children: ReactNode }) {
  return (
    <motion.div variants={fieldVariant} className="space-y-2">
      {children}
    </motion.div>
  );
}

export function AnimatedError({ children }: { children: ReactNode }) {
  return (
    <motion.p
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="text-sm text-red-600"
    >
      {children}
    </motion.p>
  );
}

export function SubmitButton({
  loading,
  loadingText,
  children,
}: {
  loading: boolean;
  loadingText: string;
  children: ReactNode;
}) {
  return (
    <motion.div variants={fieldVariant} whileHover={{ scale: loading ? 1 : 1.015 }} whileTap={{ scale: loading ? 1 : 0.98 }}>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? loadingText : children}
      </Button>
    </motion.div>
  );
}

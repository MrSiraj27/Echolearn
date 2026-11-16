"use client";

import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";

// Landing-page motion helpers. Everything here respects the visitor's "reduce motion" setting
// through the <MotionConfig reducedMotion="user"> wrapper in LandingPage.

const EASE = [0.22, 1, 0.36, 1] as const; // soft "ease-out-quint"

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE } },
};

export const stagger = (gap = 0.08, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});

/** Fades and lifts its content in the first time it scrolls into view. */
export function Reveal({
  children,
  className,
  delay = 0,
  x = 0,
  y = 28,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  x?: number;
  y?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, x, y }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.8, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** A list whose children (StaggerItem) appear one after another when it scrolls into view. */
export function Stagger({
  children,
  className,
  gap = 0.08,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  gap?: number;
  as?: "div" | "ul" | "ol";
}) {
  const Tag = motion[as];
  return (
    <Tag className={className} variants={stagger(gap)} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }}>
      {children}
    </Tag>
  );
}

export function StaggerItem({
  children,
  className,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "li" | "figure";
}) {
  const Tag = motion[as];
  return (
    <Tag className={className} variants={fadeUp}>
      {children}
    </Tag>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { TodayReviewResponse } from "@/lib/types";

const SECONDS_PER_CARD = 30;

/** Non-blocking "Daily Review: N cards, ~M min" nudge shown near the top of the
 * sidebar. Gated on GET /users/me/usage's has_pending_reviews flag (true only when
 * cards are due AND none reviewed yet today) rather than a separate notification
 * system — this component only fetches /review/today (once that flag is true) to get
 * the actual count/estimate to display. */
export default function DailyReviewCard() {
  const router = useRouter();
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    api
      .get<{ has_pending_reviews: boolean }>("/users/me/usage", { auth: true })
      .then((usage) => {
        if (!usage.has_pending_reviews) return;
        return api
          .get<TodayReviewResponse>("/review/today", { auth: true })
          .then((data) => setCount(Math.min(data.cards.length, data.capped_at)));
      })
      .catch(() => setCount(null));
  }, []);

  if (!count) return null;

  const minutes = Math.max(1, Math.round((count * SECONDS_PER_CARD) / 60));

  return (
    <motion.button
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={() => router.push("/review")}
      className="w-full flex items-center gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 px-3 py-2 text-left hover:bg-amber-100 dark:hover:bg-amber-950/50 transition-colors mb-2"
    >
      <Sparkles className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
      <span className="text-xs text-amber-800 dark:text-amber-300 min-w-0">
        <span className="font-semibold">Daily Review:</span> {count} card{count === 1 ? "" : "s"}, ~{minutes} min
      </span>
    </motion.button>
  );
}

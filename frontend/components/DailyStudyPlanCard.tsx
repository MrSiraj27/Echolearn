"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { CalendarClock } from "lucide-react";
import { api } from "@/lib/api";
import { TodaySessionItem } from "@/lib/types";

const SESSION_TYPE_LABEL: Record<string, string> = {
  learn: "Learn",
  review: "Review",
  quiz: "Checkpoint quiz",
  checkpoint: "Cumulative checkpoint",
};

/** Dashboard "Today's Study Session" card, aggregating across all active plans
 * (GET /study-plans/today doesn't scope to one plan). Shows the first pending
 * session due today, if any. */
export default function DailyStudyPlanCard() {
  const router = useRouter();
  const [item, setItem] = useState<TodaySessionItem | null>(null);

  useEffect(() => {
    api
      .get<TodaySessionItem[]>("/study-plans/today", { auth: true })
      .then((items) => setItem(items[0] || null))
      .catch(() => setItem(null));
  }, []);

  if (!item) return null;

  return (
    <motion.button
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={() => router.push(`/study-plans/${item.plan_id}/sessions/${item.session.id}`)}
      className="w-full flex items-center gap-2 rounded-lg bg-neutral-100 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 px-3 py-2 text-left hover:bg-neutral-200/70 dark:hover:bg-neutral-800 transition-colors mb-2"
    >
      <CalendarClock className="h-4 w-4 text-neutral-500 dark:text-neutral-400 shrink-0" />
      <span className="text-xs text-neutral-700 dark:text-neutral-300 min-w-0 flex-1 truncate">
        <span className="font-semibold">Today&apos;s Study Session:</span> {item.session.topic_title}
        <span className="text-neutral-400 dark:text-neutral-500"> ({SESSION_TYPE_LABEL[item.session.session_type]})</span>
      </span>
    </motion.button>
  );
}

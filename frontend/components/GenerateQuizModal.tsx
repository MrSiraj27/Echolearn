"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { DocumentItem, QuizDetail } from "@/lib/types";

export default function GenerateQuizModal({
  documents,
  preselectedDocumentIds,
  onClose,
}: {
  documents: DocumentItem[];
  preselectedDocumentIds: string[];
  onClose: () => void;
}) {
  const router = useRouter();
  const readyDocs = documents.filter((d) => d.status === "embedded" || d.status === "ready");
  const [selectedIds, setSelectedIds] = useState<string[]>(
    preselectedDocumentIds.filter((id) => readyDocs.some((d) => d.id === id))
  );
  const [numQuestions, setNumQuestions] = useState(10);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [questionType, setQuestionType] = useState<"mixed" | "multiple_choice" | "short_answer">("mixed");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleDoc(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  async function handleGenerate() {
    if (selectedIds.length === 0) {
      setError("Select at least one document.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const quiz = await api.post<QuizDetail>(
        "/quizzes/generate",
        { document_ids: selectedIds, num_questions: numQuestions, difficulty, question_type: questionType },
        { auth: true }
      );
      router.push(`/quiz/${quiz.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't generate a quiz. Please try again.");
      setLoading(false);
    }
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-md bg-white dark:bg-neutral-900 rounded-xl shadow-2xl border border-neutral-200 dark:border-neutral-800 overflow-hidden"
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }}
        transition={{ duration: 0.18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-neutral-100 dark:border-neutral-800">
          <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Generate a quiz</h2>
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-2">Documents</p>
            {readyDocs.length === 0 && (
              <p className="text-xs text-neutral-400 dark:text-neutral-500">No ready documents yet.</p>
            )}
            <div className="space-y-1.5">
              {readyDocs.map((doc) => (
                <label
                  key={doc.id}
                  className="flex items-center gap-2 text-sm text-neutral-700 dark:text-neutral-300 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(doc.id)}
                    onChange={() => toggleDoc(doc.id)}
                    className="accent-neutral-900 dark:accent-neutral-100"
                  />
                  <span className="truncate">{doc.filename}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Number of questions</p>
            <input
              type="number"
              min={1}
              max={25}
              value={numQuestions}
              onChange={(e) => setNumQuestions(Math.max(1, Math.min(25, Number(e.target.value) || 1)))}
              className="w-24 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2.5 py-1.5 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
            />
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Difficulty</p>
            <div className="flex gap-1.5">
              {(["easy", "medium", "hard"] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    difficulty === d
                      ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                      : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-neutral-600 dark:text-neutral-400 mb-1.5">Question types</p>
            <div className="flex gap-1.5">
              {(["mixed", "multiple_choice", "short_answer"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setQuestionType(t)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    questionType === t
                      ? "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 border-neutral-900 dark:border-neutral-100"
                      : "border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                  }`}
                >
                  {t === "mixed" ? "Mixed" : t === "multiple_choice" ? "Multiple choice" : "Short answer"}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-neutral-100 dark:border-neutral-800 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="text-xs font-medium text-neutral-600 dark:text-neutral-400 px-3 py-1.5 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="text-xs font-medium text-white dark:text-neutral-900 bg-neutral-900 dark:bg-neutral-100 px-3.5 py-1.5 rounded-lg hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {loading ? "Generating..." : "Generate quiz"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

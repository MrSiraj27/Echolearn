"use client";

import { use, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Send, FileText, Workflow, Loader2, LayoutPanelTop } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import ChatBubble from "@/components/ChatBubble";
import MicButton from "@/components/MicButton";
import MediaPlayer, { MediaPlayerHandle } from "@/components/MediaPlayer";
import { useChatStore } from "@/lib/chat-store";
import { AUDIO_VIDEO_EXTENSIONS, ChatMessage } from "@/lib/types";
import { api } from "@/lib/api";
import ExportMenu from "@/components/ExportMenu";
import GenerateQuizModal from "@/components/GenerateQuizModal";
import { AnimatePresence } from "framer-motion";

export default function ChatPage({ params }: { params: Promise<{ chatId: string }> }) {
  const { chatId } = use(params);
  const searchParams = useSearchParams();
  const prefill = searchParams.get("q") || "";

  const {
    messages,
    documents,
    loadMessages,
    loadDocuments,
    sendMessage,
    isStreaming,
    streamingContent,
    generateDiagram,
    generateInfographic,
    deleteMessage,
  } = useChatStore();
  const [input, setInput] = useState(prefill);
  const [sendError, setSendError] = useState<string | null>(null);
  const [chatDocumentIds, setChatDocumentIds] = useState<string[]>([]);
  const [chatTitle, setChatTitle] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState<string | null>(null);
  const [showQuizModal, setShowQuizModal] = useState(false);
  const [showDiagramInput, setShowDiagramInput] = useState(false);
  const [diagramInstruction, setDiagramInstruction] = useState("");
  const [diagramSubmitting, setDiagramSubmitting] = useState(false);
  const [diagramError, setDiagramError] = useState<string | null>(null);
  const [showInfographicInput, setShowInfographicInput] = useState(false);
  const [infographicInstruction, setInfographicInstruction] = useState("");
  const [infographicTemplate, setInfographicTemplate] = useState("auto");
  const [infographicSubmitting, setInfographicSubmitting] = useState(false);
  const [infographicError, setInfographicError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaPlayerRef = useRef<MediaPlayerHandle>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hasSentPrefill = useRef(false);

  async function handleSend(overrideText?: string) {
    const content = (overrideText ?? input).trim();
    if (!content || isStreaming) return;
    setInput("");
    setSendError(null);
    try {
      await sendMessage(chatId, content);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Couldn't reach EchoLearn. Check your connection and try again.");
    }
  }

  async function handleGenerateDiagram() {
    const instruction = diagramInstruction.trim();
    if (!instruction) return;
    setDiagramSubmitting(true);
    setDiagramError(null);
    try {
      const result = await generateDiagram(chatId, instruction);
      if (result.possible) {
        setDiagramInstruction("");
        setShowDiagramInput(false);
      } else {
        setDiagramError(result.error || "Couldn't generate a diagram for this.");
      }
    } catch (err) {
      setDiagramError(err instanceof Error ? err.message : "Couldn't generate a diagram. Please try again.");
    } finally {
      setDiagramSubmitting(false);
    }
  }

  async function handleGenerateInfographic() {
    setInfographicSubmitting(true);
    setInfographicError(null);
    try {
      const result = await generateInfographic(chatId, infographicInstruction.trim(), infographicTemplate);
      if (result.possible) {
        setInfographicInstruction("");
        setShowInfographicInput(false);
      } else {
        setInfographicError(result.error || "Couldn't generate an infographic for this.");
      }
    } catch (err) {
      setInfographicError(err instanceof Error ? err.message : "Couldn't generate an infographic. Please try again.");
    } finally {
      setInfographicSubmitting(false);
    }
  }

  useEffect(() => {
    // Skip fetching history for a brand-new chat opened with a prefilled question — it
    // has no history yet, and the fetch could otherwise resolve after sendMessage has
    // already populated the store, wiping the just-sent exchange back to empty.
    if (prefill) return;
    loadMessages(chatId);
  }, [chatId, loadMessages, prefill]);

  useEffect(() => {
    loadDocuments();
    api
      .get<{ title: string | null; document_ids: string[]; workspace_name: string | null }>(
        `/chats/${chatId}`,
        { auth: true }
      )
      .then((detail) => {
        setChatDocumentIds(detail.document_ids);
        setChatTitle(detail.title);
        setWorkspaceName(detail.workspace_name);
      })
      .catch(() => setChatDocumentIds([]));
  }, [chatId, loadDocuments]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingContent]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  useEffect(() => {
    if (prefill && !hasSentPrefill.current) {
      hasSentPrefill.current = true;
      setInput("");
      sendMessage(chatId, prefill).catch(() =>
        setSendError("Couldn't reach EchoLearn. Check your connection and try again.")
      );
    }
  }, [prefill, chatId, sendMessage]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const streamingMessage: ChatMessage | null = isStreaming
    ? { id: "streaming", role: "assistant", content: streamingContent, citations: null, created_at: "" }
    : null;

  const primaryDoc = documents.find((d) => chatDocumentIds.includes(d.id) && d.status === "ready" && d.summary);
  const showWelcomeCard = messages.length === 0 && !isStreaming && !prefill && primaryDoc;
  const mediaDoc =
    chatDocumentIds.length === 1 ? documents.find((d) => d.id === chatDocumentIds[0]) : undefined;
  const isMediaDoc = mediaDoc && AUDIO_VIDEO_EXTENSIONS.has(mediaDoc.file_type);

  function handleSeek(seconds: number) {
    mediaPlayerRef.current?.seekTo(seconds);
  }

  return (
    <>
      <Sidebar activeChatId={chatId} />
      <main className="flex-1 min-w-0 flex flex-col h-screen bg-white dark:bg-neutral-950">
        <div className="flex items-center justify-between gap-2 border-b border-neutral-200 dark:border-neutral-800 pl-14 pr-3 py-3 lg:px-6 overflow-hidden">
          <div className="min-w-0 flex items-center gap-2">
            <h1 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">
              {chatTitle || "Untitled chat"}
            </h1>
            {workspaceName ? (
              <span
                className="shrink-0 text-[11px] font-medium text-neutral-500 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 rounded-full px-2 py-0.5"
                title={`${chatDocumentIds.length} document${chatDocumentIds.length === 1 ? "" : "s"} in this workspace`}
              >
                📁 {workspaceName} ({chatDocumentIds.length} docs)
              </span>
            ) : (
              chatDocumentIds.length > 0 && (
                <span className="shrink-0 text-[11px] font-medium text-neutral-500 dark:text-neutral-400 bg-neutral-100 dark:bg-neutral-800 rounded-full px-2 py-0.5">
                  {chatDocumentIds.length === 1 ? "1 document" : `${chatDocumentIds.length} documents`}
                </span>
              )
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {chatDocumentIds.length > 0 && (
              <button
                onClick={() => setShowQuizModal(true)}
                className="flex items-center gap-1.5 text-xs font-medium text-neutral-600 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700 rounded-lg px-3 py-1.5 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
              >
                <FileText className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Generate Quiz</span>
              </button>
            )}
            {messages.length > 0 && <ExportMenu chatId={chatId} chatTitle={chatTitle} />}
          </div>
        </div>
        {isMediaDoc && mediaDoc && (
          <MediaPlayer ref={mediaPlayerRef} documentId={mediaDoc.id} fileType={mediaDoc.file_type} />
        )}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
            {showWelcomeCard && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 p-5"
              >
                <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">
                  About {primaryDoc.filename}
                </p>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed">{primaryDoc.summary}</p>
                {primaryDoc.suggested_questions && primaryDoc.suggested_questions.length > 0 && (
                  <div className="mt-4">
                    <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-wide mb-2">
                      Try asking
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {primaryDoc.suggested_questions.map((q, i) => (
                        <button
                          key={i}
                          onClick={() => handleSend(q)}
                          className="text-xs text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-full px-3 py-1.5 hover:bg-neutral-100 dark:hover:bg-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
            {messages.length === 0 && !isStreaming && !showWelcomeCard && (
              <p className="text-sm text-neutral-400 dark:text-neutral-500 text-center mt-20">
                Ask a question about your documents.
              </p>
            )}
            {messages.map((m, i) => (
              <ChatBubble
                key={m.id}
                message={m}
                chatId={chatId}
                onFollowUp={
                  i === messages.length - 1 && m.role === "assistant" && !isStreaming
                    ? (q) => handleSend(q)
                    : undefined
                }
                onSeek={isMediaDoc ? handleSeek : undefined}
                onDeleteMessage={(messageId) => deleteMessage(chatId, messageId)}
              />
            ))}
            {streamingMessage && streamingMessage.content && <ChatBubble message={streamingMessage} />}
            {isStreaming && !streamingContent && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-1 px-1"
              >
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </motion.div>
            )}
          </div>
        </div>

        <div className="border-t border-neutral-200 dark:border-neutral-800 px-6 py-4">
          {sendError && <p className="max-w-2xl mx-auto text-xs text-red-600 dark:text-red-400 mb-2">{sendError}</p>}

          {showDiagramInput && (
            <div className="max-w-2xl mx-auto mb-2 space-y-1.5">
              <div className="flex gap-1.5">
                <input
                  autoFocus
                  value={diagramInstruction}
                  onChange={(e) => setDiagramInstruction(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGenerateDiagram()}
                  placeholder="e.g. Draw the setup process as a flowchart"
                  className="flex-1 min-w-0 text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3.5 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                />
                <button
                  onClick={handleGenerateDiagram}
                  disabled={diagramSubmitting || !diagramInstruction.trim()}
                  className="shrink-0 flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-xl px-3.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
                >
                  {diagramSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Generate
                </button>
                <button
                  onClick={() => {
                    setShowDiagramInput(false);
                    setDiagramError(null);
                  }}
                  className="shrink-0 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 px-1"
                  aria-label="Cancel"
                >
                  <span className="text-lg leading-none">&times;</span>
                </button>
              </div>
              {diagramError && <p className="text-xs text-red-600 dark:text-red-400">{diagramError}</p>}
            </div>
          )}

          {showInfographicInput && (
            <div className="max-w-2xl mx-auto mb-2 space-y-1.5">
              <div className="flex gap-1.5">
                <select
                  value={infographicTemplate}
                  onChange={(e) => setInfographicTemplate(e.target.value)}
                  className="shrink-0 text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-2 text-neutral-700 dark:text-neutral-300 focus:outline-none"
                >
                  <option value="auto">Auto</option>
                  <option value="stats">Stats</option>
                  <option value="timeline">Timeline</option>
                  <option value="comparison">Comparison</option>
                  <option value="summary">Summary</option>
                </select>
                <input
                  autoFocus
                  value={infographicInstruction}
                  onChange={(e) => setInfographicInstruction(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGenerateInfographic()}
                  placeholder="e.g. Summarize the key findings (optional)"
                  className="flex-1 min-w-0 text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3.5 py-2 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
                />
                <button
                  onClick={handleGenerateInfographic}
                  disabled={infographicSubmitting}
                  className="shrink-0 flex items-center gap-1.5 text-sm font-medium bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 rounded-xl px-3.5 hover:bg-neutral-800 dark:hover:bg-white transition-colors disabled:opacity-50"
                >
                  {infographicSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Generate
                </button>
                <button
                  onClick={() => {
                    setShowInfographicInput(false);
                    setInfographicError(null);
                  }}
                  className="shrink-0 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 px-1"
                  aria-label="Cancel"
                >
                  <span className="text-lg leading-none">&times;</span>
                </button>
              </div>
              {infographicError && (
                <p className="text-xs text-red-600 dark:text-red-400">
                  {infographicError}
                  {infographicError.includes("summary instead") && (
                    <button
                      onClick={() => {
                        setInfographicTemplate("summary");
                        handleGenerateInfographic();
                      }}
                      className="ml-2 underline underline-offset-2 hover:text-red-800 dark:hover:text-red-300"
                    >
                      Try a plain summary
                    </button>
                  )}
                </p>
              )}
            </div>
          )}

          <div className="max-w-2xl mx-auto flex items-end gap-2">
            {chatDocumentIds.length > 0 && (
              <button
                onClick={() => setShowDiagramInput((v) => !v)}
                disabled={isStreaming}
                aria-label="Generate diagram"
                title="Generate a diagram from this document"
                className={`shrink-0 h-11 w-11 rounded-xl border flex items-center justify-center transition-colors disabled:opacity-40 ${
                  showDiagramInput
                    ? "bg-neutral-100 dark:bg-neutral-800 border-neutral-300 dark:border-neutral-600 text-neutral-900 dark:text-neutral-100"
                    : "border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                }`}
              >
                <Workflow className="h-4 w-4" />
              </button>
            )}
            {chatDocumentIds.length > 0 && (
              <button
                onClick={() => setShowInfographicInput((v) => !v)}
                disabled={isStreaming}
                aria-label="Generate infographic"
                title="Generate an infographic from this document"
                className={`shrink-0 h-11 w-11 rounded-xl border flex items-center justify-center transition-colors disabled:opacity-40 ${
                  showInfographicInput
                    ? "bg-neutral-100 dark:bg-neutral-800 border-neutral-300 dark:border-neutral-600 text-neutral-900 dark:text-neutral-100"
                    : "border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800"
                }`}
              >
                <LayoutPanelTop className="h-4 w-4" />
              </button>
            )}
            <MicButton
              disabled={isStreaming}
              onInterimResult={(text) => setInput(text)}
              onFinalResult={(text) => {
                setInput(text);
                textareaRef.current?.focus();
              }}
            />
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              rows={1}
              className="flex-1 min-w-0 resize-none overflow-y-auto rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3.5 py-2.5 text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 dark:placeholder:text-neutral-500 focus:outline-none focus:ring-1 focus:ring-neutral-900 dark:focus:ring-neutral-100"
              style={{ minHeight: "44px", maxHeight: "160px" }}
            />
            <button
              onClick={() => handleSend()}
              disabled={isStreaming || !input.trim()}
              className="shrink-0 h-11 px-4 rounded-xl bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 text-sm font-medium disabled:opacity-40 hover:bg-neutral-800 dark:hover:bg-white transition-colors flex items-center justify-center"
            >
              {isStreaming ? (
                <span className="h-3.5 w-3.5 rounded-full border-2 border-white/40 dark:border-neutral-900/40 border-t-white dark:border-t-neutral-900 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </main>

      <AnimatePresence>
        {showQuizModal && (
          <GenerateQuizModal
            documents={documents}
            preselectedDocumentIds={chatDocumentIds}
            onClose={() => setShowQuizModal(false)}
          />
        )}
      </AnimatePresence>
    </>
  );
}

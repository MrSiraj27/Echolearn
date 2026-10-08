import { create } from "zustand";
import {
  AppLanguage,
  ChatItem,
  ChatMessage,
  DocumentItem,
  ExplainLanguage,
  ExplainMode,
  Folder,
  MessageTranslation,
  Workspace,
} from "./types";
import { api } from "./api";

const LANGUAGE_TAB_STORAGE_KEY = "echolearn_language_tabs";

// The tab (English / Urdu / Roman Urdu) the user last picked in each chat, remembered across
// reloads. localStorage can be unavailable (private mode), so every access is guarded.
function loadLanguageTabs(): Record<string, AppLanguage> {
  try {
    return JSON.parse(localStorage.getItem(LANGUAGE_TAB_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveLanguageTabs(tabs: Record<string, AppLanguage>) {
  try {
    localStorage.setItem(LANGUAGE_TAB_STORAGE_KEY, JSON.stringify(tabs));
  } catch {
    // ignore
  }
}

// Adds/replaces one translation on a message (a message has at most one per language+mode).
function withTranslation(message: ChatMessage, translation: MessageTranslation): ChatMessage {
  const others = (message.translations || []).filter(
    (t) => !(t.language === translation.language && t.mode === translation.mode)
  );
  return { ...message, translations: [...others, translation] };
}

interface ChatState {
  chats: ChatItem[];
  documents: DocumentItem[];
  folders: Folder[];
  workspaces: Workspace[];
  activeChatId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;

  // Urdu / Roman Urdu explanations
  preferredLanguage: AppLanguage;
  languageTabByChat: Record<string, AppLanguage>;
  // messageId -> language being auto-generated right now (shows a "preparing" hint)
  pendingTranslations: Record<string, ExplainLanguage>;
  // messageId -> why an explanation couldn't be produced (e.g. daily quota reached)
  translationNotices: Record<string, string>;
  loadPreferences: () => Promise<void>;
  setPreferredLanguage: (language: AppLanguage) => Promise<void>;
  setLanguageTab: (chatId: string, language: AppLanguage) => void;
  explainMessage: (
    chatId: string,
    messageId: string,
    language: ExplainLanguage,
    mode?: ExplainMode
  ) => Promise<MessageTranslation>;

  loadChats: () => Promise<void>;
  loadDocuments: () => Promise<void>;
  loadFolders: () => Promise<void>;
  createFolder: (name: string) => Promise<Folder>;
  deleteFolder: (folderId: string) => Promise<void>;
  moveDocumentToFolder: (documentId: string, folderId: string | null) => Promise<void>;
  loadWorkspaces: () => Promise<void>;
  createWorkspace: (name: string, documentIds: string[]) => Promise<Workspace>;
  deleteWorkspace: (workspaceId: string) => Promise<void>;
  addDocumentToWorkspace: (workspaceId: string, documentId: string) => Promise<void>;
  removeDocumentFromWorkspace: (workspaceId: string, documentId: string) => Promise<void>;
  loadMessages: (chatId: string) => Promise<void>;
  setActiveChatId: (chatId: string | null) => void;
  createChat: (documentIds: string[], title?: string) => Promise<string>;
  createWorkspaceChat: (workspaceId: string) => Promise<string>;
  sendMessage: (chatId: string, content: string) => Promise<void>;
  deleteChat: (chatId: string) => Promise<void>;
  deleteDocument: (documentId: string) => Promise<void>;
  pollDocumentStatus: (documentId: string) => void;
  addDocumentFromUrl: (url: string, folderId?: string | null) => Promise<string>;
  generateDiagram: (chatId: string, instruction: string) => Promise<{ possible: boolean; error?: string }>;
  generateInfographic: (
    chatId: string,
    instruction: string,
    template: string
  ) => Promise<{ possible: boolean; error?: string }>;
  deleteMessage: (chatId: string, messageId: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  chats: [],
  documents: [],
  folders: [],
  workspaces: [],
  activeChatId: null,
  messages: [],
  isStreaming: false,
  streamingContent: "",

  preferredLanguage: "en",
  languageTabByChat: {},
  pendingTranslations: {},
  translationNotices: {},

  loadPreferences: async () => {
    const usage = await api.get<{ preferred_language?: AppLanguage }>("/users/me/usage", { auth: true });
    set({ preferredLanguage: usage.preferred_language || "en", languageTabByChat: loadLanguageTabs() });
  },

  setPreferredLanguage: async (language: AppLanguage) => {
    const previous = get().preferredLanguage;
    set({ preferredLanguage: language }); // optimistic; rolled back below if the save fails
    try {
      await api.patch("/users/me/preferences", { preferred_language: language }, { auth: true });
    } catch (err) {
      set({ preferredLanguage: previous });
      throw err;
    }
  },

  setLanguageTab: (chatId: string, language: AppLanguage) => {
    const tabs = { ...get().languageTabByChat, [chatId]: language };
    saveLanguageTabs(tabs);
    set({ languageTabByChat: tabs });
  },

  explainMessage: async (chatId, messageId, language, mode = "translate") => {
    const result = await api.post<{ text: string; fidelity_warning: boolean }>(
      `/chats/${chatId}/messages/${messageId}/explain`,
      { language, mode },
      { auth: true }
    );
    const translation: MessageTranslation = {
      language,
      mode,
      text: result.text,
      fidelity_warning: result.fidelity_warning,
    };
    set((state) => ({
      messages: state.messages.map((m) => (m.id === messageId ? withTranslation(m, translation) : m)),
    }));
    return translation;
  },

  loadChats: async () => {
    const chats = await api.get<ChatItem[]>("/chats/", { auth: true });
    set({ chats });
  },

  loadDocuments: async () => {
    const documents = await api.get<DocumentItem[]>("/documents/", { auth: true });
    set({ documents });
  },

  loadFolders: async () => {
    const folders = await api.get<Folder[]>("/folders/", { auth: true });
    set({ folders });
  },

  createFolder: async (name: string) => {
    const folder = await api.post<Folder>("/folders/", { name }, { auth: true });
    set((state) => ({ folders: [...state.folders, folder] }));
    return folder;
  },

  deleteFolder: async (folderId: string) => {
    await api.delete(`/folders/${folderId}`, { auth: true });
    set((state) => ({
      folders: state.folders.filter((f) => f.id !== folderId),
      documents: state.documents.map((d) => (d.folder_id === folderId ? { ...d, folder_id: null } : d)),
    }));
  },

  moveDocumentToFolder: async (documentId: string, folderId: string | null) => {
    const updated = await api.patch<DocumentItem>(
      `/documents/${documentId}/folder`,
      { folder_id: folderId },
      { auth: true }
    );
    set((state) => ({
      documents: state.documents.map((d) => (d.id === documentId ? { ...d, folder_id: updated.folder_id } : d)),
    }));
    get().loadFolders();
  },

  loadWorkspaces: async () => {
    const workspaces = await api.get<Workspace[]>("/workspaces/", { auth: true });
    set({ workspaces });
  },

  createWorkspace: async (name: string, documentIds: string[]) => {
    const workspace = await api.post<Workspace>(
      "/workspaces/",
      { name, document_ids: documentIds },
      { auth: true }
    );
    set((state) => ({ workspaces: [...state.workspaces, workspace] }));
    return workspace;
  },

  deleteWorkspace: async (workspaceId: string) => {
    await api.delete(`/workspaces/${workspaceId}`, { auth: true });
    set((state) => ({ workspaces: state.workspaces.filter((w) => w.id !== workspaceId) }));
  },

  addDocumentToWorkspace: async (workspaceId: string, documentId: string) => {
    await api.post(`/workspaces/${workspaceId}/documents`, { document_id: documentId }, { auth: true });
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspaceId ? { ...w, document_count: w.document_count + 1 } : w
      ),
    }));
  },

  removeDocumentFromWorkspace: async (workspaceId: string, documentId: string) => {
    await api.delete(`/workspaces/${workspaceId}/documents/${documentId}`, { auth: true });
    set((state) => ({
      workspaces: state.workspaces.map((w) =>
        w.id === workspaceId ? { ...w, document_count: Math.max(0, w.document_count - 1) } : w
      ),
    }));
  },

  loadMessages: async (chatId: string) => {
    const messages = await api.get<ChatMessage[]>(`/chats/${chatId}/messages`, { auth: true });
    set({ messages });
  },

  setActiveChatId: (chatId: string | null) => set({ activeChatId: chatId }),

  createChat: async (documentIds: string[], title?: string) => {
    const chat = await api.post<ChatItem>("/chats/", { document_ids: documentIds, title }, { auth: true });
    set((state) => ({ chats: [chat, ...state.chats] }));
    return chat.id;
  },

  createWorkspaceChat: async (workspaceId: string) => {
    const chat = await api.post<ChatItem>("/chats/", { workspace_id: workspaceId }, { auth: true });
    set((state) => ({ chats: [chat, ...state.chats] }));
    return chat.id;
  },

  sendMessage: async (chatId: string, content: string) => {
    const tempUserMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      citations: null,
      created_at: new Date().toISOString(),
    };
    set((state) => ({
      messages: [...state.messages, tempUserMessage],
      isStreaming: true,
      streamingContent: "",
    }));

    const { getAccessToken } = await import("./api");
    const token = getAccessToken();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const response = await fetch(`${apiUrl}/chats/${chatId}/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: "include",
      body: JSON.stringify({ content }),
    });

    if (!response.ok || !response.body) {
      set((state) => ({
        isStreaming: false,
        messages: state.messages.filter((m) => m.id !== tempUserMessage.id),
      }));
      const detail = await response
        .json()
        .then((d) => d.detail)
        .catch(() => null);
      throw new Error(detail || "Failed to send message");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let accumulated = "";
    let finalized = false;

    // The English answer is shown the moment the server says it is complete, NOT when the
    // stream closes: with auto-explain on, the stream stays open a few seconds longer for the
    // Urdu/Roman Urdu text, and that must never hold up the English answer.
    const finalizeAnswer = (
      serverMessageId: string | null,
      citations: ChatMessage["citations"],
      followUps: string[]
    ) => {
      finalized = true;
      const assistantMessage: ChatMessage = {
        id: serverMessageId || `assistant-${Date.now()}`,
        role: "assistant",
        content: accumulated,
        citations,
        created_at: new Date().toISOString(),
        followUps,
      };
      const preferred = get().preferredLanguage;
      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isStreaming: false,
        streamingContent: "",
        pendingTranslations:
          preferred !== "en" && serverMessageId
            ? { ...state.pendingTranslations, [serverMessageId]: preferred }
            : state.pendingTranslations,
      }));
      get().loadChats();
    };

    const clearPending = (messageId: string) =>
      set((state) => {
        const rest = { ...state.pendingTranslations };
        delete rest[messageId];
        return { pendingTranslations: rest };
      });

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const rawEvent of events) {
        const lines = rawEvent.split("\n");
        let eventType = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          if (line.startsWith("data:")) data = line.slice(5).trim();
        }
        if (!data) continue;

        try {
          const parsed = JSON.parse(data);
          if (eventType === "token") {
            accumulated += parsed.content;
            set({ streamingContent: accumulated });
          } else if (eventType === "done") {
            finalizeAnswer(parsed.message_id || null, parsed.citations, parsed.follow_ups || []);
          } else if (eventType === "translation") {
            const translation: MessageTranslation = {
              language: parsed.language,
              mode: parsed.mode,
              text: parsed.text,
              fidelity_warning: !!parsed.fidelity_warning,
            };
            clearPending(parsed.message_id);
            // Show the user's preferred language as soon as it arrives.
            const tabs = { ...get().languageTabByChat, [chatId]: translation.language as AppLanguage };
            saveLanguageTabs(tabs);
            set((state) => ({
              languageTabByChat: tabs,
              messages: state.messages.map((m) => (m.id === parsed.message_id ? withTranslation(m, translation) : m)),
            }));
          } else if (eventType === "quota_reached") {
            clearPending(parsed.message_id);
            set((state) => ({
              translationNotices: { ...state.translationNotices, [parsed.message_id]: parsed.detail },
            }));
          } else if (eventType === "translation_error") {
            clearPending(parsed.message_id);
            set((state) => ({
              translationNotices: {
                ...state.translationNotices,
                [parsed.message_id]: "Couldn't prepare the explanation. Use the language buttons to try again.",
              },
            }));
          }
        } catch {
          // ignore malformed SSE chunk
        }
      }
    }

    // Safety net: the stream ended without a "done" event (e.g. the connection dropped).
    if (!finalized) finalizeAnswer(null, null, []);
  },

  deleteChat: async (chatId: string) => {
    await api.delete(`/chats/${chatId}`, { auth: true });
    set((state) => ({
      chats: state.chats.filter((c) => c.id !== chatId),
      activeChatId: state.activeChatId === chatId ? null : state.activeChatId,
    }));
  },

  deleteDocument: async (documentId: string) => {
    await api.delete(`/documents/${documentId}`, { auth: true });
    set((state) => ({ documents: state.documents.filter((d) => d.id !== documentId) }));
  },

  pollDocumentStatus: (documentId: string) => {
    // A failed poll (backend restarting, cold start, brief 503) must not end polling —
    // that left the document showing "processing" forever even after it finished.
    let errors = 0;
    const startedAt = Date.now();
    const interval = setInterval(async () => {
      if (Date.now() - startedAt > 15 * 60 * 1000) {
        clearInterval(interval);
        set((state) => ({
          documents: state.documents.map((d) => (d.id === documentId ? { ...d, status: "failed" } : d)),
        }));
        return;
      }
      try {
        const status = await api.get<DocumentItem & { page_count: number | null }>(
          `/documents/${documentId}/status`,
          { auth: true }
        );
        set((state) => ({
          documents: state.documents.map((d) => (d.id === documentId ? { ...d, status: status.status } : d)),
        }));
        if (status.status === "ready" || status.status === "failed") {
          clearInterval(interval);
          if (status.status === "ready") {
            // Re-fetch the full list so the newly generated summary/suggested
            // questions (not present on the lightweight status response) land in the store.
            get().loadDocuments();
          }
        }
        errors = 0;
      } catch {
        errors += 1;
        if (errors >= 30) clearInterval(interval);
      }
    }, 2000);
  },

  generateDiagram: async (chatId: string, instruction: string) => {
    const data = await api.post<{ possible: boolean; message: ChatMessage | null; error: string | null }>(
      `/chats/${chatId}/diagram`,
      { instruction },
      { auth: true }
    );
    if (data.possible && data.message) {
      set((state) => ({ messages: [...state.messages, data.message as ChatMessage] }));
      return { possible: true };
    }
    return { possible: false, error: data.error || "Couldn't generate a diagram for this." };
  },

  generateInfographic: async (chatId: string, instruction: string, template: string) => {
    const data = await api.post<{ possible: boolean; message: ChatMessage | null; error: string | null }>(
      `/chats/${chatId}/infographic`,
      { instruction, template },
      { auth: true }
    );
    if (data.possible && data.message) {
      set((state) => ({ messages: [...state.messages, data.message as ChatMessage] }));
      return { possible: true };
    }
    return { possible: false, error: data.error || "Couldn't generate an infographic for this." };
  },

  deleteMessage: async (chatId: string, messageId: string) => {
    await api.delete(`/chats/${chatId}/messages/${messageId}`, { auth: true });
    set((state) => ({ messages: state.messages.filter((m) => m.id !== messageId) }));
  },

  addDocumentFromUrl: async (url: string, folderId?: string | null) => {
    const data = await api.post<{ document_id: string; status: string }>(
      "/documents/from-url",
      { url, folder_id: folderId || null },
      { auth: true }
    );
    await get().loadDocuments();
    await get().loadFolders();
    get().pollDocumentStatus(data.document_id);
    return data.document_id;
  },
}));

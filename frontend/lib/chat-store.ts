import { create } from "zustand";
import { ChatItem, ChatMessage, DocumentItem, Folder, Workspace } from "./types";
import { api } from "./api";

interface ChatState {
  chats: ChatItem[];
  documents: DocumentItem[];
  folders: Folder[];
  workspaces: Workspace[];
  activeChatId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;

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
    let citations = null;
    let followUps: string[] = [];

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
            citations = parsed.citations;
            followUps = parsed.follow_ups || [];
          }
        } catch {
          // ignore malformed SSE chunk
        }
      }
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: accumulated,
      citations,
      created_at: new Date().toISOString(),
      followUps,
    };

    set((state) => ({
      messages: [...state.messages, assistantMessage],
      isStreaming: false,
      streamingContent: "",
    }));

    get().loadChats();
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
    const interval = setInterval(async () => {
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
      } catch {
        clearInterval(interval);
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

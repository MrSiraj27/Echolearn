"use client";

import { getAccessToken } from "@/lib/api";
import { useChatStore } from "@/lib/chat-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const UPLOAD_ACCEPT =
  ".pdf,.docx,.pptx,.txt,.csv,.png,.jpg,.jpeg,.mp3,.wav,.m4a,.mp4,.mov";

/** Upload one file, refresh the library and start polling its processing status.
 *  Throws an Error whose message is safe to show to the user. */
export async function uploadDocument(file: File, folderId?: string | null): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  if (folderId) formData.append("folder_id", folderId);
  const token = getAccessToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/documents/upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: "include",
      body: formData,
    });
  } catch {
    throw new Error("Couldn't reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed. Please try again.");
  }
  const data = (await res.json()) as { document_id: string };
  const store = useChatStore.getState();
  await Promise.all([store.loadDocuments(), store.loadFolders()]);
  store.pollDocumentStatus(data.document_id);
  return data.document_id;
}

import { SheetLanguage } from "./types";

export const LANGUAGE_NAMES: Record<SheetLanguage, string> = {
  en: "English",
  ur: "اردو",
  roman_ur: "Roman Urdu",
  bilingual: "English + اردو",
};

/**
 * Download a sheet's PDF. The download endpoint needs the login token, so a plain link
 * won't work: fetch it with the token, then hand the bytes to the browser as a file.
 */
export async function downloadSheetPdf(sheetId: string, title: string): Promise<void> {
  const { getAccessToken } = await import("./api");
  const token = getAccessToken();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/revision-sheets/${sheetId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail)
      .catch(() => null);
    throw new Error(detail || "Couldn't download the PDF.");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 60) || "revision_sheet"}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

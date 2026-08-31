import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { SpeechProvider } from "@/lib/speech-context";
import { ThemeProvider } from "@/lib/theme-provider";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EchoLearn",
  description: "Chat with your documents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans bg-white dark:bg-neutral-950">
        <ThemeProvider>
          <AuthProvider>
            <SpeechProvider>{children}</SpeechProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

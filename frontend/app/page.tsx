import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "EchoLearn — Study Smarter. Learn Better.",
  description:
    "Upload your study material, ask questions, and get instant AI-powered explanations from your own documents.",
};

export default function Home() {
  return <LandingPage />;
}

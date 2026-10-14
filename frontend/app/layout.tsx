import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "AI Knowledge Hub",
  description: "Ask questions about your organization's documents, with cited sources.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <a href="#main" className="sr-only-skip">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

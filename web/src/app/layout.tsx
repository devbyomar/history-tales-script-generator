import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "History Tales — AI Documentary Script Generator",
  description:
    "Generate high-retention, emotionally resonant, evidence-led history documentary scripts with AI.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <div className="min-h-screen bg-background">
          <header className="border-b border-border/40 bg-card/50 backdrop-blur-sm sticky top-0 z-50">
            <div className="container flex h-14 items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xl">🎬</span>
                <h1 className="text-lg font-bold tracking-tight">
                  <span className="text-primary">History Tales</span>
                  <span className="text-muted-foreground font-normal ml-2 text-sm">
                    Script Generator
                  </span>
                </h1>
              </div>
              <div className="flex items-center gap-4">
                <a
                  href="/docs"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  API Docs
                </a>
              </div>
            </div>
          </header>
          <main className="container py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}

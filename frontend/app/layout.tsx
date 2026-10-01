import type { Metadata, Viewport } from "next";

import { ServerGate } from "@/components/ServerGate";

import "./globals.css";

export const metadata: Metadata = {
  title: "RepoGrill — get grilled on your own code",
  description:
    "A voice mock interviewer that reads your GitHub repo, asks the hard questions and catches your bluffs.",
};

export const viewport: Viewport = {
  themeColor: "#0b0d12",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <ServerGate>{children}</ServerGate>
      </body>
    </html>
  );
}

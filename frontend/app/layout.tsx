import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoGrill — get grilled on your own code",
  description:
    "A voice mock interviewer that reads your GitHub repo and asks you the hard questions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

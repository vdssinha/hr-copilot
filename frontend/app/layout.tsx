import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NovaWorks HR Copilot",
  description: "AI-powered HR assistant with role-based access control",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

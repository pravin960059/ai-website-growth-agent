import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signal / Website Growth Agent",
  description: "Evidence-first SEO, GEO, and AEO workflows.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

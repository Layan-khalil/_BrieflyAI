import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BrieflyAI — YouTube Video Summarizer",
  description: "Summarize any YouTube video in seconds — summary, key insights, and timestamps.",
  icons: {
    icon: [
      {
        url: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%238b5cf6'/><text x='16' y='22.5' text-anchor='middle' fill='white' font-family='system-ui' font-weight='800' font-size='20'>B</text></svg>",
        type: "image/svg+xml",
      },
    ],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" dir="ltr">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap" />
      </head>
      <body>{children}</body>
    </html>
  );
}
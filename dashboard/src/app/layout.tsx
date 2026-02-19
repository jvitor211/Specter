import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Specter — See What Others Can't",
  description:
    "AI-powered detection of malicious and typosquatted packages in npm and PyPI supply chains.",
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "Specter — See What Others Can't",
    description:
      "Detect poisoned dependencies before they reach production. IDE, CI, API.",
    images: [{ url: "/og-image.svg", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Specter — See What Others Can't",
    description:
      "Detect poisoned dependencies before they reach production.",
    images: ["/og-image.svg"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}

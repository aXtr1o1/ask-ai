import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ApiPreconnect } from "./components/ApiPreconnect";
import { ThemeScript } from "./components/ThemeScript";
import Script from "next/script";

const sometypeMono = localFont({
  variable: "--font-sometype-mono",
  display: "swap",
  src: [
    { path: "../fonts/SometypeMono-Regular.ttf", weight: "400", style: "normal" },
    { path: "../fonts/SometypeMono-Medium.ttf", weight: "500", style: "normal" },
    { path: "../fonts/SometypeMono-SemiBold.ttf", weight: "600", style: "normal" },
    { path: "../fonts/SometypeMono-Italic.ttf", weight: "400", style: "italic" },
    { path: "../fonts/SometypeMono-MediumItalic.ttf", weight: "500", style: "italic" },
    { path: "../fonts/SometypeMono-BoldItalic.ttf", weight: "700", style: "italic" },
  ],
});

// 👇 UPDATE THIS SECTION
export const metadata: Metadata = {
  title: "Nanosoft Ask AI",  // Changes the browser tab name
  description: "Internal AI Assistant powered by Gemini",
  icons: {
    icon: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script
          id="theme-inline-script"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  const stored = localStorage.getItem('theme');
                  if (stored && (stored === 'light' || stored === 'dark')) {
                    document.documentElement.setAttribute('data-theme', stored);
                  } else {
                    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    const theme = prefersDark ? 'dark' : 'light';
                    document.documentElement.setAttribute('data-theme', theme);
                  }
                } catch (e) {
                  document.documentElement.setAttribute('data-theme', 'dark');
                }
              })();
            `,
          }}
        />
      </head>
      <body
        className={`${sometypeMono.variable} antialiased`}
      >
        <ThemeScript />
        <ApiPreconnect />
        {children}
      </body>
    </html>
  );
}
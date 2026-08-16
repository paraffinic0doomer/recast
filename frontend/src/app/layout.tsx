import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";
import { AppSidebar } from "@/components/app-sidebar";
import { AccessGate } from "@/components/access-gate";
import "./globals.css";

/**
 * One UI face, one mono face. Inter carries the whole interface — hierarchy
 * comes from size, weight and tracking rather than from a second typeface,
 * which is what makes precision-tooling UIs feel engineered instead of styled.
 */
const sans = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

/** Timecodes, chapters and counts, where digits must line up. */
const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

const DESCRIPTION =
  "An AI creative studio that turns one video into a full social-media campaign: transcript, Content DNA, vertical shorts, and native copy for six platforms.";

export const metadata: Metadata = {
  title: "RECAST — One piece of content. An entire campaign.",
  description: DESCRIPTION,
  // icon.png / apple-icon.png in this directory are picked up automatically.
  openGraph: {
    title: "RECAST — One piece of content. An entire campaign.",
    description: DESCRIPTION,
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "RECAST",
    description: DESCRIPTION,
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: next-themes sets the class on <html> client-side.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <ThemeProvider>
          <TooltipProvider>
            {/* Nothing renders until the key is accepted on a gated backend. */}
            <AccessGate>
              <AppSidebar />
              {/* The rail is fixed, so the workspace is inset by its width. */}
              <div className="flex min-h-dvh flex-col lg:pl-64">{children}</div>
            </AccessGate>
          </TooltipProvider>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}

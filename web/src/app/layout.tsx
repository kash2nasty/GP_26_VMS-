import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

/**
 * Type pairing: a transitional serif for headings against a neutral grotesque
 * for body copy. The serif carries the "formal" register without reaching for
 * anything decorative, and Source Serif was designed for screen text so it holds
 * up at the card-title sizes used here.
 *
 * The CSS variable names line up with the `--font-sans` / `--font-serif` /
 * `--font-mono` that globals.css consumes in its @theme block.
 */
const sans = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const serif = Source_Serif_4({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "VMS Screening Results",
  description:
    "Read-only dashboard for VOMS visual-motion screening sessions. Screening data only, not a clinical determination.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${serif.variable} ${mono.variable} h-full antialiased`}
    >
      {/* TooltipProvider is required by the shadcn sidebar's collapsed-state
          tooltips; the CLI flags this when adding the tooltip component. */}
      <body className="min-h-full flex flex-col">
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

/**
 * Type pairing: a transitional serif for headings against a neutral grotesque for
 * body copy. The serif carries the "formal" register without reaching for anything
 * decorative, and Source Serif was designed for screen text so it holds up at the
 * card-title sizes used here.
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
  title: "Oculomotor Screening",
  description:
    "Head, eye, eyelid and facial screening signals from one webcam capture. Screening data only, not a clinical determination.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      // Required by next-themes: it writes the theme class onto <html> before
      // React hydrates, so server and client markup differ here by design.
      suppressHydrationWarning
      className={`${sans.variable} ${serif.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider>
          {/* TooltipProvider is required by the shadcn sidebar's collapsed-state
              tooltips; the CLI flags this when adding the tooltip component. */}
          <TooltipProvider>{children}</TooltipProvider>
          <Toaster position="bottom-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}

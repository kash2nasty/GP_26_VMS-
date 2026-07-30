"use client"

import { ThemeProvider as NextThemeProvider } from "next-themes"

/**
 * Dark mode.
 *
 * next-themes was already a dependency and globals.css already defined a full
 * `.dark` palette, but nothing ever applied the class, so every one of those
 * values was dead code and the app was light-only. This is the missing piece.
 *
 * `attribute="class"` matches the `@custom-variant dark (&:is(.dark *))` in
 * globals.css. `disableTransitionOnChange` stops every coloured surface animating
 * its own background separately during a switch, which looks like a fault.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  )
}

"use client"

import { useTheme } from "next-themes"
import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react"

import { useIsHydrated } from "@/hooks/use-hydrated"
import { Button } from "@/components/ui/button"

const ORDER = ["system", "light", "dark"] as const
type Mode = (typeof ORDER)[number]

const META: Record<Mode, { icon: typeof SunIcon; label: string }> = {
  system: { icon: MonitorIcon, label: "Match system" },
  light: { icon: SunIcon, label: "Light" },
  dark: { icon: MoonIcon, label: "Dark" },
}

/**
 * Cycles system, light, dark.
 *
 * A three-state cycle rather than a two-state switch, because "match system" is a
 * real preference and a plain toggle silently discards it the first time it is
 * pressed.
 *
 * No icon renders until hydration. The server does not know the resolved theme, so
 * rendering one during SSR means showing the wrong icon and then swapping it, which
 * reads as a glitch. The placeholder keeps the button the same size either way, so
 * nothing beside it shifts.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()
  const hydrated = useIsHydrated()

  const current = (ORDER.includes(theme as Mode) ? theme : "system") as Mode
  const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length]
  const Icon = META[current].icon

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className={className}
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${META[current].label}. Switch to ${META[next].label}.`}
      title={`Theme: ${META[current].label}`}
    >
      {hydrated ? <Icon className="size-4" /> : <span className="size-4" />}
    </Button>
  )
}

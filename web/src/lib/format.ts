/**
 * Display helpers.
 *
 * The guiding rule: a missing value must never render as a confident-looking
 * number. Everything funnels through helpers that show an em-dash for
 * null/undefined rather than "0", because 0 is a real measurement here (a
 * symptom score of 0 means "no symptoms") and must be distinguishable from
 * "not recorded".
 */

import type { Finding, SeverityTier, Strength, Urgency } from "@/lib/api"

/**
 * Placeholder for values that were not recorded.
 *
 * Deliberately the string "n/a" rather than a dash character: this codebase keeps
 * em dashes and en dashes out of all user-facing copy, and a bare dash also reads
 * ambiguously next to signed numbers like "-43°".
 */
const MISSING = "n/a"

export function isPresent(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

export function num(value: number | null | undefined, digits = 2): string {
  return isPresent(value) ? value.toFixed(digits) : MISSING
}

export function int(value: number | null | undefined): string {
  return isPresent(value) ? String(Math.round(value)) : MISSING
}

export function percent(value: number | null | undefined, digits = 0): string {
  return isPresent(value) ? `${(value * 100).toFixed(digits)}%` : MISSING
}

export function ratio(value: number | null | undefined): string {
  return isPresent(value) ? `${(value * 100).toFixed(0)}%` : MISSING
}

export function degrees(value: number | null | undefined, digits = 1): string {
  return isPresent(value) ? `${value.toFixed(digits)}°` : MISSING
}

export function seconds(value: number | null | undefined, digits = 1): string {
  return isPresent(value) ? `${value.toFixed(digits)}s` : MISSING
}

/** Formats the API's ISO-8601 UTC timestamps. */
export function formatDateTime(iso: string | null): string {
  if (!iso) return MISSING
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return MISSING
  return new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)
}

export function formatDateOnly(iso: string | null): string {
  if (!iso) return MISSING
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return MISSING
  return new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(date)
}

/**
 * Tier colours.
 *
 * Deliberately not a red/green "good vs bad" scale. These are screening bands,
 * not pass/fail results, and a green "minimal" badge would read as an
 * all-clear that this tool cannot support. Sequential slate-to-amber intensity
 * instead: it conveys ordering without implying a verdict.
 */
export const TIER_STYLES: Record<SeverityTier, string> = {
  minimal:
    "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
  mild: "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-300",
  moderate:
    "border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
  pronounced:
    "border-orange-400 bg-orange-100 text-orange-900 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-300",
}

export const TIER_ORDER: SeverityTier[] = [
  "minimal",
  "mild",
  "moderate",
  "pronounced",
]

export function tierRank(tier: SeverityTier | null | undefined): number {
  if (!tier) return -1
  return TIER_ORDER.indexOf(tier)
}

/** Turns "amplitude_below_protocol" into "amplitude below protocol". */
export function humanizeFlag(flag: string): string {
  return flag.replace(/^protocol:/, "").replace(/_/g, " ")
}

/**
 * Turns a measured-field key into a readable label.
 *
 * The indications panel reports whatever fields each check used, so the keys are
 * not known ahead of time and cannot be mapped by hand. Unit suffixes are the part
 * worth special-casing: "residual rms offset units" reads as four unrelated words,
 * whereas moving the unit into parentheses makes the quantity and its unit obvious.
 */
const UNIT_SUFFIXES: Array<[RegExp, string]> = [
  [/_offset_units$/, " (socket units)"],
  [/_per_min$/, " (per minute)"],
  [/_per_s$/, " (per second)"],
  [/_hz$/, " (Hz)"],
  [/_deg$/, " (degrees)"],
  [/_dps$/, " (deg/s)"],
  [/_s$/, " (seconds)"],
]

export function humanizeKey(key: string): string {
  let unit = ""
  let stem = key
  for (const [pattern, suffix] of UNIT_SUFFIXES) {
    if (pattern.test(stem)) {
      unit = suffix
      stem = stem.replace(pattern, "")
      break
    }
  }
  const words = stem.replace(/_/g, " ").trim()
  return words.charAt(0).toUpperCase() + words.slice(1) + unit
}

/** Renders any value out of a `measured` or `thresholds` map. */
export function formatMeasured(
  value: number | string | number[] | null | undefined
): string {
  if (value === null || value === undefined) return MISSING
  if (Array.isArray(value)) return value.join(" to ")
  if (typeof value === "string") return value.replace(/_/g, " ")
  if (!Number.isFinite(value)) return MISSING
  if (Number.isInteger(value)) return String(value)
  // Small magnitudes here are socket-normalised units, where the interesting
  // digits are the fourth and fifth. Rounding them to two would erase the value.
  if (Math.abs(value) < 0.01) return value.toPrecision(2)
  if (Math.abs(value) < 1) return value.toFixed(3)
  return value.toFixed(2)
}

/**
 * Indication colours.
 *
 * Same reasoning as the tier scale: no green anywhere. A green "not indicated"
 * chip would read as an all-clear, and scoring/indications.py is explicit that a
 * negative result means one measurement did not cross one provisional threshold in
 * one session. Slate for that, amber and rose for flagged, and a distinctly
 * different treatment (dashed, muted) for "could not be assessed" so it never
 * looks like a quiet pass.
 */
export const FINDING_STYLES: Record<Finding, string> = {
  indicated:
    "border-amber-400/70 bg-amber-100/70 text-amber-950 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-100",
  not_indicated:
    "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
  not_assessable:
    "border-dashed border-muted-foreground/40 bg-transparent text-muted-foreground",
}

export const FINDING_LABELS: Record<Finding, string> = {
  indicated: "Signal flagged",
  not_indicated: "Nothing flagged",
  not_assessable: "Not assessable",
}

export const STRENGTH_LABELS: Record<Strength, string> = {
  borderline: "Borderline",
  present: "Present",
  marked: "Marked",
}

export const URGENCY_LABELS: Record<Urgency, string> = {
  routine: "Routine review",
  prompt: "Worth prompt review",
  emergency_if_new: "Emergency if new",
}

export const URGENCY_STYLES: Record<Urgency, string> = {
  routine: "border-border bg-muted text-muted-foreground",
  prompt:
    "border-amber-400 bg-amber-100 text-amber-950 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100",
  emergency_if_new:
    "border-rose-400 bg-rose-100 text-rose-950 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-100",
}

export const EVIDENCE_LABELS: Record<string, string> = {
  published_sign_provisional_threshold: "Published sign, provisional threshold",
  bespoke_metric_arbitrary_threshold: "Bespoke metric, arbitrary threshold",
}

/** Ordering for the panel: flagged first, then unassessable, then negative. */
export const FINDING_ORDER: Finding[] = [
  "indicated",
  "not_assessable",
  "not_indicated",
]

/** Plain-language explanation of the scoring status values. */
export const STATUS_LABELS: Record<string, string> = {
  scored: "Symptom report and objective tracking both used",
  symptom_only: "Symptom report only, objective tracking unusable",
  objective_only: "Objective tracking only, no symptom report",
  insufficient_data: "Insufficient data, no tier assigned",
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Unknown"
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ")
}

export { MISSING }

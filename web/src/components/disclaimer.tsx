/**
 * Disclaimer surfaces.
 *
 * The text always comes from the API, which reads it from the Python scoring
 * modules. That was a deliberate constraint: the Python side bakes a `disclaimer`
 * field into its output schema specifically so a later UI cannot silently drop it,
 * and duplicating the wording in TypeScript would defeat that by letting the two
 * drift apart.
 *
 * `ScreeningDisclaimer` is required on every page that shows results, and
 * `ExerciseDisclaimer` on every page that shows exercises.
 */

import { InfoIcon, ShieldAlertIcon } from "lucide-react"

function Notice({
  icon,
  title,
  children,
  tone = "neutral",
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
  tone?: "neutral" | "warning"
}) {
  const toneClasses =
    tone === "warning"
      ? "border-amber-300/80 bg-amber-50/80 text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100"
      : "border-border/70 bg-muted/40 text-muted-foreground"

  return (
    <div className={`rounded-lg border px-4 py-3 ${toneClasses}`}>
      <div className="flex gap-3">
        <span className="mt-0.5 shrink-0" aria-hidden="true">
          {icon}
        </span>
        <div className="space-y-1.5 text-xs leading-relaxed">
          <p className="text-[0.7rem] font-semibold uppercase tracking-wider">
            {title}
          </p>
          {children}
        </div>
      </div>
    </div>
  )
}

export function ScreeningDisclaimer({ text }: { text: string }) {
  if (!text) return null
  return (
    <Notice icon={<InfoIcon className="size-4" />} title="Screening only">
      <p>{text}</p>
    </Notice>
  )
}

export function ExerciseDisclaimer({
  text,
  safetyNote,
}: {
  text: string
  safetyNote?: string
}) {
  if (!text && !safetyNote) return null
  return (
    <Notice
      icon={<ShieldAlertIcon className="size-4" />}
      title="Before starting any exercise"
      tone="warning"
    >
      {text ? <p>{text}</p> : null}
      {safetyNote ? <p>{safetyNote}</p> : null}
    </Notice>
  )
}

/** The disclaimer stored inside the session file itself. */
export function SessionDisclaimer({ text }: { text?: string }) {
  if (!text) return null
  return (
    <details className="group rounded-lg border border-border/70 bg-muted/30 px-4 py-3">
      <summary className="cursor-pointer text-[0.7rem] font-semibold uppercase tracking-wider text-muted-foreground">
        Disclaimer recorded with this session
      </summary>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{text}</p>
    </details>
  )
}

/**
 * Footer restatement. Long notices at the top get scrolled past, so the key
 * sentence is repeated where the reader finishes.
 */
export function DisclaimerFooter() {
  return (
    <footer className="border-t">
      <p className="mx-auto max-w-[1360px] px-5 py-6 text-center text-xs leading-relaxed text-muted-foreground lg:px-8">
        Screening data only. Not a clinical determination, and not a diagnosis of
        any condition. Review with a qualified clinician before acting on anything
        shown here.
      </p>
    </footer>
  )
}

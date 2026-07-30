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
      ? "border border-amber-300/80 bg-amber-50/80 text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100"
      : "inset-panel text-muted-foreground"

  return (
    <div className={`rounded-lg px-4 py-3 ${toneClasses}`}>
      <div className="flex gap-3">
        <span className="mt-0.5 shrink-0" aria-hidden="true">
          {icon}
        </span>
        <div className="max-w-[76ch] space-y-1.5 text-xs leading-relaxed">
          <p className="text-[0.68rem] font-semibold tracking-[0.08em] uppercase">
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
    <details className="group inset-panel px-4 py-3">
      <summary className="eyebrow cursor-pointer">
        Disclaimer recorded with this session
      </summary>
      <p className="mt-2 max-w-[76ch] text-xs leading-relaxed text-muted-foreground">
        {text}
      </p>
    </details>
  )
}

/**
 * Footer restatement. Long notices at the top get scrolled past, so the key
 * sentence is repeated where the reader finishes.
 */
export function DisclaimerFooter() {
  return (
    <footer className="mt-10 border-t">
      <p className="mx-auto max-w-[1180px] px-5 py-6 text-center text-xs leading-relaxed text-muted-foreground lg:px-8">
        Screening data only. Not a clinical determination, and not a diagnosis of any
        condition. A screening check that flags nothing is not a clearance. Review
        with a qualified clinician before acting on anything shown here.
      </p>
    </footer>
  )
}

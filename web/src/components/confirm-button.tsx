"use client"

/**
 * Destructive action with an explicit confirmation step.
 *
 * Hand-rolled rather than pulling in another dependency, and modal rather than a
 * two-click inline toggle: the confirmation needs room to say what will actually
 * happen to the files, which a button label cannot.
 */

import * as React from "react"
import { LoaderCircleIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

export function ConfirmButton({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
  variant = "destructive",
  size = "default",
}: {
  trigger: React.ReactNode
  title: string
  description: React.ReactNode
  confirmLabel?: string
  onConfirm: () => Promise<void> | void
  variant?: "destructive" | "outline" | "ghost" | "default"
  size?: "default" | "sm" | "xs"
}) {
  const [open, setOpen] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const cancelRef = React.useRef<HTMLButtonElement | null>(null)
  const dialogRef = React.useRef<HTMLDivElement | null>(null)
  const restoreFocusTo = React.useRef<HTMLElement | null>(null)

  React.useEffect(() => {
    if (!open) return

    // Focus lands on the safe choice, not the destructive one, so a stray Enter
    // cannot delete anything.
    restoreFocusTo.current = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()

    // The page behind a modal must not scroll, and Tab must not walk out of the
    // dialog into it. Without the trap, tabbing past Delete lands on the table
    // underneath while the overlay still covers it, which is unusable with a
    // keyboard and invisible with a mouse.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        setOpen(false)
        return
      }
      if (event.key !== "Tab" || !dialogRef.current) return

      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = previousOverflow
      restoreFocusTo.current?.focus()
    }
  }, [open, busy])

  const confirm = async () => {
    setBusy(true)
    try {
      await onConfirm()
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <span onClick={() => setOpen(true)} className="contents">
        {trigger}
      </span>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label={title}
        >
          <div
            className="absolute inset-0 bg-foreground/25 backdrop-blur-[2px]"
            onClick={() => (busy ? null : setOpen(false))}
          />
          <div
            ref={dialogRef}
            className="animate-pop relative w-full max-w-md rounded-xl bg-card p-5 shadow-xl ring-1 ring-foreground/10"
          >
            <h2 className="font-heading text-lg font-semibold">{title}</h2>
            <div className="mt-2 space-y-2 text-sm leading-relaxed text-muted-foreground">
              {description}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                ref={cancelRef}
                variant="outline"
                size={size}
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button variant={variant} size={size} disabled={busy} onClick={confirm}>
                {busy ? (
                  <LoaderCircleIcon className="size-4 animate-spin" />
                ) : null}
                {confirmLabel}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}

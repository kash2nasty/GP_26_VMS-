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

  // Escape closes, and focus lands on the safe choice rather than the destructive
  // one so a stray Enter cannot delete anything.
  React.useEffect(() => {
    if (!open) return
    cancelRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
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
          <div className="relative w-full max-w-md rounded-xl border bg-card p-5 shadow-xl">
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

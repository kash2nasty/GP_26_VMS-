"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Trash2Icon } from "lucide-react"

import { ConfirmButton } from "@/components/confirm-button"
import { Button } from "@/components/ui/button"
import { deleteSession } from "@/lib/actions"

export function DeleteSessionButton({
  id,
  label,
  capturedAt,
  redirectTo,
  size = "sm",
  variant = "outline",
}: {
  id: string
  label?: string
  capturedAt?: string
  /** Where to go after a successful delete. Omit to just refresh in place. */
  redirectTo?: string
  size?: "default" | "sm" | "xs"
  variant?: "outline" | "ghost" | "destructive"
}) {
  const router = useRouter()
  const [error, setError] = React.useState<string | null>(null)

  const remove = async () => {
    setError(null)
    const result = await deleteSession(id)
    if (!result.ok) {
      setError(result.error)
      return
    }
    if (redirectTo) {
      router.push(redirectTo)
    } else {
      router.refresh()
    }
  }

  return (
    <div className="inline-flex flex-col items-end gap-1">
      <ConfirmButton
        trigger={
          <Button variant={variant} size={size} aria-label={`Delete session ${id}`}>
            <Trash2Icon className="size-4" />
            {label}
          </Button>
        }
        title="Delete this session?"
        description={
          <>
            <p>
              {capturedAt
                ? `The session recorded on ${capturedAt} will be removed from the dashboard.`
                : "This session will be removed from the dashboard."}
            </p>
            <p>
              The files are moved into{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                sessions/_deleted/
              </code>{" "}
              rather than erased, so you can recover them by hand if this was a
              mistake. A capture cannot be regenerated from anything else on disk.
            </p>
          </>
        }
        confirmLabel="Delete session"
        onConfirm={remove}
        size={size}
      />
      {error ? (
        <p className="max-w-xs text-right text-xs text-destructive">{error}</p>
      ) : null}
    </div>
  )
}

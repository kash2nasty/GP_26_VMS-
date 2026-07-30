"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { Trash2Icon } from "lucide-react"

import { ConfirmButton } from "@/components/confirm-button"
import { Button } from "@/components/ui/button"
import { deleteSession } from "@/lib/actions"

/**
 * Delete one session.
 *
 * Outcomes go to a toast rather than to inline text under the button. In the table
 * this button lives in a 40px cell where an error message had nowhere to render,
 * and on success the row it was anchored to disappears, taking any inline
 * confirmation with it.
 */
export function DeleteSessionButton({
  id,
  label,
  capturedAt,
  redirectTo,
  size = "sm",
  variant = "ghost",
}: {
  id: string
  label?: string
  capturedAt?: string
  /** Where to go after a successful delete. Omit to refresh in place. */
  redirectTo?: string
  size?: "default" | "sm" | "xs"
  variant?: "outline" | "ghost" | "destructive"
}) {
  const router = useRouter()

  const remove = async () => {
    const result = await deleteSession(id)
    if (!result.ok) {
      toast.error("Could not delete the session", {
        description: result.error,
      })
      return
    }

    toast.success("Session deleted", {
      description: `${result.deleted.length} file${
        result.deleted.length === 1 ? "" : "s"
      } moved to ${result.movedTo}`,
    })

    if (redirectTo) router.push(redirectTo)
    else router.refresh()
  }

  return (
    <ConfirmButton
      trigger={
        <Button
          variant={variant}
          size={size}
          aria-label={`Delete session ${id}`}
          className="text-muted-foreground hover:text-destructive"
        >
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
            The files move into{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">
              sessions/_deleted/
            </code>{" "}
            rather than being erased, so you can recover them by hand if this was a
            mistake. A capture cannot be regenerated from anything else on disk.
          </p>
        </>
      }
      confirmLabel="Delete session"
      onConfirm={remove}
      size={size === "xs" ? "sm" : size}
    />
  )
}

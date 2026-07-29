"use client"

/**
 * Route-level error boundary.
 *
 * Without this, an unexpected throw in a Server Component shows Next's default
 * error screen, which in production is a bare "something went wrong" with no way
 * forward. This at least names the failure and offers a retry.
 */

import { RotateCcwIcon, TriangleAlertIcon } from "lucide-react"

import { DashboardShell } from "@/components/dashboard-shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <DashboardShell title="Something went wrong">
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TriangleAlertIcon className="size-4 text-destructive" />
            This page could not be rendered
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-muted-foreground">
            {error.message || "No further detail was reported."}
          </p>
          {error.digest ? (
            <p className="text-xs text-muted-foreground">
              Error reference {error.digest}
            </p>
          ) : null}
          <Button onClick={reset} size="sm">
            <RotateCcwIcon className="size-4" />
            Try again
          </Button>
        </CardContent>
      </Card>
    </DashboardShell>
  )
}

/**
 * Shown when the Python API cannot be reached.
 *
 * This is the most likely failure in local use: the frontend and backend are two
 * processes and one is easy to forget. So it renders the actual command to start
 * it rather than a generic "something went wrong", which would send the reader
 * looking for a bug that is not there.
 */

import { PlugZapIcon } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function ApiError({ message }: { message: string }) {
  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <PlugZapIcon className="size-4 text-destructive" />
          Cannot reach the screening API
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-muted-foreground">{message}</p>
        <div className="space-y-2">
          <p className="font-medium">Start the backend in a second terminal:</p>
          {/* Relative to the project root, so this does not go stale if the
              checkout moves. */}
          <pre className="overflow-x-auto rounded-lg border bg-muted p-3 text-xs">
            <code>{`.venv\\Scripts\\activate
uvicorn api.main:app --reload --port 8000`}</code>
          </pre>
          <p className="text-xs text-muted-foreground">
            Run it from the project root, the folder containing{" "}
            <code className="rounded bg-muted px-1 py-0.5">run_session.py</code>.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

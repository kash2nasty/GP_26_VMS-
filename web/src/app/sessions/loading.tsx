import { DashboardShell } from "@/components/dashboard-shell"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Streamed while the sessions list loads. Both pages hit a local API so this is
 * usually brief, but without it a slow first compile shows a blank frame.
 */
export default function Loading() {
  return (
    <DashboardShell title="Sessions">
      <div className="space-y-3">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid grid-cols-2 gap-3 @3xl/main:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-14 rounded-lg" />
      <Skeleton className="h-64 rounded-xl" />
    </DashboardShell>
  )
}

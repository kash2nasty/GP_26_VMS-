import { DashboardShell } from "@/components/dashboard-shell"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Streamed while the sessions list loads.
 *
 * The shapes mirror the real page: one wide hero stat, three narrow ones, a chart,
 * then a table. A skeleton whose blocks land somewhere other than the content that
 * replaces them produces a visible jump, which is worse than no skeleton.
 */
export default function Loading() {
  return (
    <DashboardShell title="Sessions">
      <div className="space-y-2.5">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-7 w-72" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="grid gap-3 @2xl/main:grid-cols-2 @4xl/main:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
    </DashboardShell>
  )
}

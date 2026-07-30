"use client"

/**
 * Sessions list table.
 *
 * WHY THIS IS HAND-ROLLED RATHER THAN TANSTACK TABLE
 *     It used TanStack, matching the dashboard-01 block it came from. Two reasons
 *     it does not any more. The React Compiler refuses to memoize any component
 *     calling useReactTable, because the hook returns functions that cannot be
 *     memoized safely, so this file was the one compiler bailout in the app and it
 *     showed up as a lint error on every run. And the library was earning almost
 *     nothing: no pagination, no filtering through the table, no column visibility,
 *     no grouping. Sorting seven columns of a list that is already fully loaded in
 *     memory is about twenty lines of code.
 *
 *     What is kept from the block: sorting, because comparing sessions genuinely
 *     needs it. What was dropped: drag-to-reorder, which is an affordance this app
 *     cannot honour on immutable capture records.
 *
 * SELECTION EXISTS TO SERVE DELETION
 *     The demo block shipped checkboxes with nothing to act on. These have
 *     something: a session is a file on disk, captures accumulate fast while
 *     testing, and removing them one confirmation dialog at a time is tedious
 *     enough that people stop doing it and the list stops being useful.
 */

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import {
  ArrowDownIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  ChevronRightIcon,
  Trash2Icon,
} from "lucide-react"

import { ConfirmButton } from "@/components/confirm-button"
import { DeleteSessionButton } from "@/components/delete-session-button"
import { IndicationChips } from "@/components/indication-chips"
import { ObjectiveSignalBadge, ProtocolBadge, TierBadge } from "@/components/tier-badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { deleteSessions } from "@/lib/actions"
import type { SessionSummary, SeverityTier } from "@/lib/api"
import {
  TIER_ORDER,
  formatDateTime,
  int,
  isPresent,
  percent,
  tierRank,
} from "@/lib/format"

type SortKey = "captured_at" | "symptom_score" | "severity_tier" | "indications"
type Direction = "asc" | "desc"

const HEAD_CLASS = "eyebrow whitespace-nowrap"

/** Comparators. Each returns "a before b" ordering for the ascending case. */
const COMPARATORS: Record<
  SortKey,
  (a: SessionSummary, b: SessionSummary) => number
> = {
  captured_at: (a, b) => (a.captured_at ?? "").localeCompare(b.captured_at ?? ""),
  // A session with no score sorts to one end rather than being treated as 0,
  // because 0 is a real result here and must not mix in with "not reported".
  symptom_score: (a, b) => {
    const x = a.symptom_score
    const y = b.symptom_score
    if (!isPresent(x)) return isPresent(y) ? -1 : 0
    if (!isPresent(y)) return 1
    return x - y
  },
  // Clinical ordering, not alphabetical: "mild before moderate" alphabetically is
  // luck, whereas minimal < mild < moderate < pronounced is meaning.
  severity_tier: (a, b) => tierRank(a.severity_tier) - tierRank(b.severity_tier),
  indications: (a, b) =>
    (a.indications_indicated?.length ?? 0) -
    (b.indications_indicated?.length ?? 0),
}

function SortHeader({
  label,
  active,
  direction,
  onToggle,
  align = "start",
}: {
  label: string
  active: boolean
  direction: Direction
  onToggle: () => void
  align?: "start" | "end"
}) {
  const Icon = !active
    ? ArrowUpDownIcon
    : direction === "asc"
      ? ArrowUpIcon
      : ArrowDownIcon
  return (
    <Button
      variant="ghost"
      size="xs"
      onClick={onToggle}
      className={`eyebrow -mx-1.5 gap-1 ${
        align === "end" ? "ml-auto" : ""
      } ${active ? "text-foreground" : ""}`}
      aria-label={`Sort by ${label}`}
    >
      {label}
      <Icon className="size-3 opacity-60" />
    </Button>
  )
}

export function SessionsTable({ sessions }: { sessions: SessionSummary[] }) {
  const router = useRouter()
  const [sortKey, setSortKey] = React.useState<SortKey>("captured_at")
  const [direction, setDirection] = React.useState<Direction>("desc")
  const [tierFilter, setTierFilter] = React.useState<SeverityTier | null>(null)
  const [flaggedOnly, setFlaggedOnly] = React.useState(false)
  const [selected, setSelected] = React.useState<ReadonlySet<string>>(new Set())

  const tierCounts = React.useMemo(() => {
    const counts = new Map<SeverityTier, number>()
    for (const session of sessions) {
      if (session.severity_tier) {
        counts.set(
          session.severity_tier,
          (counts.get(session.severity_tier) ?? 0) + 1
        )
      }
    }
    return counts
  }, [sessions])

  const flaggedCount = React.useMemo(
    () =>
      sessions.filter((s) => (s.indications_indicated?.length ?? 0) > 0).length,
    [sessions]
  )

  const rows = React.useMemo(() => {
    const filtered = sessions.filter((session) => {
      if (tierFilter && session.severity_tier !== tierFilter) return false
      if (flaggedOnly && (session.indications_indicated?.length ?? 0) === 0) {
        return false
      }
      return true
    })
    const sign = direction === "asc" ? 1 : -1
    return [...filtered].sort((a, b) => sign * COMPARATORS[sortKey](a, b))
  }, [sessions, tierFilter, flaggedOnly, sortKey, direction])

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"))
    } else {
      setSortKey(key)
      // Dates and counts are most useful highest-first; the tier scale reads
      // better ascending, matching how the bands are written down.
      setDirection(key === "severity_tier" ? "asc" : "desc")
    }
  }

  const toggleRow = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Selection is scoped to what is on screen: selecting all, then filtering, then
  // deleting must not remove rows the user can no longer see.
  const visibleSelected = rows.filter((row) => selected.has(row.id))
  const allVisibleSelected =
    rows.length > 0 && visibleSelected.length === rows.length

  const deleteSelected = async () => {
    const ids = visibleSelected.map((row) => row.id)
    const result = await deleteSessions(ids)
    setSelected(new Set())

    if (result.failed.length === 0) {
      toast.success(
        `Deleted ${result.deleted.length} session${
          result.deleted.length === 1 ? "" : "s"
        }`,
        { description: "The files were moved to sessions/_deleted/." }
      )
    } else {
      toast.error(
        `Deleted ${result.deleted.length} of ${ids.length}`,
        { description: result.failed[0].error }
      )
    }
    router.refresh()
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
        {tierCounts.size > 1 ? (
          <>
            <FilterChip
              label={`All ${sessions.length}`}
              active={tierFilter === null}
              onClick={() => setTierFilter(null)}
            />
            {TIER_ORDER.filter((tier) => tierCounts.has(tier)).map((tier) => (
              <FilterChip
                key={tier}
                label={`${tier} ${tierCounts.get(tier)}`}
                active={tierFilter === tier}
                onClick={() => setTierFilter(tierFilter === tier ? null : tier)}
                className="capitalize"
              />
            ))}
          </>
        ) : null}

        {flaggedCount > 0 ? (
          <FilterChip
            label={`Flagged ${flaggedCount}`}
            active={flaggedOnly}
            onClick={() => setFlaggedOnly((on) => !on)}
            className="border border-amber-400/60 text-amber-950 dark:text-amber-100"
          />
        ) : null}

        {visibleSelected.length > 0 ? (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-muted-foreground tabular-nums">
              {visibleSelected.length} selected
            </span>
            <ConfirmButton
              trigger={
                <Button variant="destructive" size="xs">
                  <Trash2Icon className="size-3" />
                  Delete selected
                </Button>
              }
              title={`Delete ${visibleSelected.length} session${
                visibleSelected.length === 1 ? "" : "s"
              }?`}
              description={
                <>
                  <p>
                    These sessions will be removed from the dashboard. Their files
                    move into{" "}
                    <code className="rounded bg-muted px-1 py-0.5 text-xs">
                      sessions/_deleted/
                    </code>{" "}
                    rather than being erased, so they can be recovered by hand.
                  </p>
                  <p>
                    A capture records something a person physically did and cannot
                    be regenerated from anything else on disk.
                  </p>
                </>
              }
              confirmLabel={`Delete ${visibleSelected.length}`}
              onConfirm={deleteSelected}
              size="sm"
            />
          </div>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-xl ring-1 ring-foreground/10">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-surface">
              <TableRow className="hover:bg-transparent">
                <TableHead className="h-10 w-9 pl-3">
                  <Checkbox
                    checked={allVisibleSelected}
                    onCheckedChange={(checked) =>
                      setSelected(
                        checked ? new Set(rows.map((row) => row.id)) : new Set()
                      )
                    }
                    aria-label="Select all visible sessions"
                  />
                </TableHead>
                <TableHead className="h-10">
                  <SortHeader
                    label="Recorded"
                    active={sortKey === "captured_at"}
                    direction={direction}
                    onToggle={() => toggleSort("captured_at")}
                  />
                </TableHead>
                <TableHead className="h-10">
                  <SortHeader
                    label="Symptoms"
                    active={sortKey === "symptom_score"}
                    direction={direction}
                    onToggle={() => toggleSort("symptom_score")}
                  />
                </TableHead>
                <TableHead className="h-10">
                  <SortHeader
                    label="Tier"
                    active={sortKey === "severity_tier"}
                    direction={direction}
                    onToggle={() => toggleSort("severity_tier")}
                  />
                </TableHead>
                <TableHead className="h-10">
                  <SortHeader
                    label="Indications"
                    active={sortKey === "indications"}
                    direction={direction}
                    onToggle={() => toggleSort("indications")}
                  />
                </TableHead>
                <TableHead className={`h-10 ${HEAD_CLASS}`}>Camera</TableHead>
                <TableHead className={`h-10 ${HEAD_CLASS}`}>Protocol</TableHead>
                <TableHead className={`h-10 text-right ${HEAD_CLASS}`}>
                  Reps
                </TableHead>
                <TableHead className={`h-10 text-right ${HEAD_CLASS}`}>
                  Tracked
                </TableHead>
                <TableHead className="h-10 w-10">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={10}
                    className="h-20 text-center text-sm text-muted-foreground"
                  >
                    {tierFilter
                      ? `No sessions in the ${tierFilter} band.`
                      : flaggedOnly
                        ? "No sessions have a flagged indication."
                        : "No sessions yet."}
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((session) => (
                  <TableRow
                    key={session.id}
                    data-selected={selected.has(session.id) || undefined}
                    className="transition-colors hover:bg-surface data-selected:bg-accent/40"
                  >
                    <TableCell className="pl-3">
                      <Checkbox
                        checked={selected.has(session.id)}
                        onCheckedChange={() => toggleRow(session.id)}
                        aria-label={`Select session ${session.id}`}
                      />
                    </TableCell>
                    <TableCell className="py-2.5 whitespace-nowrap">
                      <Link
                        href={`/sessions/${session.id}`}
                        className="group inline-flex items-center gap-1.5 font-medium underline-offset-4 hover:underline"
                      >
                        {formatDateTime(session.captured_at)}
                        <ChevronRightIcon className="size-3.5 opacity-0 transition-opacity group-hover:opacity-60" />
                      </Link>
                    </TableCell>
                    <TableCell className="py-2.5 whitespace-nowrap">
                      {isPresent(session.symptom_score) ? (
                        <span className="font-mono text-sm tabular-nums">
                          {session.symptom_score}
                          <span className="text-muted-foreground"> / 10</span>
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Not reported
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="py-2.5">
                      <TierBadge tier={session.severity_tier} />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <IndicationChips
                        indicated={session.indications_indicated}
                        notAssessable={session.indications_not_assessable}
                        checksRun={session.indications_checks_run}
                      />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <ObjectiveSignalBadge
                        usable={session.objective_signal_usable}
                      />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <ProtocolBadge
                        comparable={session.comparable_to_clinical_protocol}
                      />
                    </TableCell>
                    <TableCell className="py-2.5 text-right font-mono text-sm tabular-nums">
                      {int(session.completed_reps)}
                    </TableCell>
                    <TableCell className="py-2.5 text-right font-mono text-sm tabular-nums">
                      {percent(session.face_detection_rate)}
                    </TableCell>
                    <TableCell className="py-2.5">
                      <DeleteSessionButton
                        id={session.id}
                        capturedAt={formatDateTime(session.captured_at)}
                        size="xs"
                        variant="ghost"
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

function FilterChip({
  label,
  active,
  onClick,
  className = "",
}: {
  label: string
  active: boolean
  onClick: () => void
  className?: string
}) {
  return (
    <Button
      variant={active ? "secondary" : "ghost"}
      size="xs"
      onClick={onClick}
      className={className}
    >
      {label}
    </Button>
  )
}

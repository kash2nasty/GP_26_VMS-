"use client"

/**
 * Sessions list table.
 *
 * Built on the same TanStack Table + shadcn primitives the dashboard-01 block
 * uses, so it matches visually. What it drops from that block: drag-to-reorder
 * rows and selection checkboxes. Reordering immutable capture records is an
 * affordance the app cannot honour, and bulk selection has nothing to act on.
 *
 * Sorting is kept, because it genuinely helps compare sessions and changes nothing
 * on the server. Tier sorting follows clinical order rather than alphabetical.
 *
 * A tier filter lives above the table; it is client-side because the whole list is
 * already loaded and a round trip would make it feel slower for no benefit.
 */

import * as React from "react"
import Link from "next/link"
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  ArrowDownIcon,
  ArrowUpDownIcon,
  ArrowUpIcon,
  ChevronRightIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { DeleteSessionButton } from "@/components/delete-session-button"
import { ObjectiveSignalBadge, ProtocolBadge, TierBadge } from "@/components/tier-badge"
import type { SessionSummary, SeverityTier } from "@/lib/api"
import {
  TIER_ORDER,
  formatDateTime,
  int,
  isPresent,
  percent,
  tierRank,
} from "@/lib/format"

function SortHeader({
  label,
  sorted,
  onToggle,
}: {
  label: string
  sorted: false | "asc" | "desc"
  onToggle: () => void
}) {
  const Icon =
    sorted === "asc"
      ? ArrowUpIcon
      : sorted === "desc"
        ? ArrowDownIcon
        : ArrowUpDownIcon
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onToggle}
      className="-ml-2 h-7 gap-1 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
    >
      {label}
      <Icon className="size-3 opacity-60" />
    </Button>
  )
}

const HEAD_CLASS =
  "text-xs font-semibold uppercase tracking-wider text-muted-foreground"

function buildColumns(): ColumnDef<SessionSummary>[] {
  return [
    {
      accessorKey: "captured_at",
      header: ({ column }) => (
        <SortHeader
          label="Recorded"
          sorted={column.getIsSorted()}
          onToggle={() => column.toggleSorting(column.getIsSorted() === "asc")}
        />
      ),
      cell: ({ row }) => (
        <Link
          href={`/sessions/${row.original.id}`}
          className="group inline-flex items-center gap-1.5 font-medium underline-offset-4 hover:underline"
        >
          {formatDateTime(row.original.captured_at)}
          <ChevronRightIcon className="size-3.5 opacity-0 transition-opacity group-hover:opacity-60" />
        </Link>
      ),
    },
    {
      accessorKey: "symptom_score",
      header: ({ column }) => (
        <SortHeader
          label="Symptoms"
          sorted={column.getIsSorted()}
          onToggle={() => column.toggleSorting(column.getIsSorted() === "asc")}
        />
      ),
      cell: ({ row }) => {
        const score = row.original.symptom_score
        // 0 is a real result ("no symptoms"), so it must not render like a value
        // the patient never gave.
        if (!isPresent(score)) {
          return (
            <span className="text-xs text-muted-foreground">Not reported</span>
          )
        }
        return (
          <span className="font-mono text-sm tabular-nums">
            {score}
            <span className="text-muted-foreground"> / 10</span>
          </span>
        )
      },
      sortingFn: (a, b) => {
        const x = a.original.symptom_score
        const y = b.original.symptom_score
        if (!isPresent(x)) return isPresent(y) ? -1 : 0
        if (!isPresent(y)) return 1
        return x - y
      },
    },
    {
      accessorKey: "severity_tier",
      header: ({ column }) => (
        <SortHeader
          label="Tier"
          sorted={column.getIsSorted()}
          onToggle={() => column.toggleSorting(column.getIsSorted() === "asc")}
        />
      ),
      cell: ({ row }) => <TierBadge tier={row.original.severity_tier} />,
      // Clinical ordering, not alphabetical: "mild before moderate" alphabetically
      // is luck, whereas minimal < mild < moderate < pronounced is meaning.
      sortingFn: (a, b) =>
        tierRank(a.original.severity_tier) - tierRank(b.original.severity_tier),
    },
    {
      id: "objective",
      header: () => <span className={HEAD_CLASS}>Camera</span>,
      cell: ({ row }) => (
        <ObjectiveSignalBadge usable={row.original.objective_signal_usable} />
      ),
      enableSorting: false,
    },
    {
      id: "protocol",
      header: () => <span className={HEAD_CLASS}>Protocol</span>,
      cell: ({ row }) => (
        <ProtocolBadge comparable={row.original.comparable_to_clinical_protocol} />
      ),
      enableSorting: false,
    },
    {
      accessorKey: "completed_reps",
      header: () => <span className={`${HEAD_CLASS} block text-right`}>Reps</span>,
      cell: ({ row }) => (
        <div className="font-mono text-sm text-right tabular-nums">
          {int(row.original.completed_reps)}
        </div>
      ),
      enableSorting: false,
    },
    {
      accessorKey: "face_detection_rate",
      header: () => (
        <span className={`${HEAD_CLASS} block text-right`}>Tracked</span>
      ),
      cell: ({ row }) => (
        <div className="font-mono text-sm text-right tabular-nums">
          {percent(row.original.face_detection_rate)}
        </div>
      ),
      enableSorting: false,
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <DeleteSessionButton
            id={row.original.id}
            capturedAt={formatDateTime(row.original.captured_at)}
            size="xs"
            variant="ghost"
          />
        </div>
      ),
      enableSorting: false,
    },
  ]
}

export function SessionsTable({ sessions }: { sessions: SessionSummary[] }) {
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: "captured_at", desc: true },
  ])
  const [tierFilter, setTierFilter] = React.useState<SeverityTier | null>(null)

  const columns = React.useMemo(buildColumns, [])

  const present = React.useMemo(() => {
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

  const filtered = React.useMemo(
    () =>
      tierFilter
        ? sessions.filter((session) => session.severity_tier === tierFilter)
        : sessions,
    [sessions, tierFilter]
  )

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="space-y-3">
      {present.size > 1 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            variant={tierFilter === null ? "secondary" : "ghost"}
            size="xs"
            onClick={() => setTierFilter(null)}
          >
            All {sessions.length}
          </Button>
          {TIER_ORDER.filter((tier) => present.has(tier)).map((tier) => (
            <Button
              key={tier}
              variant={tierFilter === tier ? "secondary" : "ghost"}
              size="xs"
              onClick={() => setTierFilter(tierFilter === tier ? null : tier)}
              className="capitalize"
            >
              {tier} {present.get(tier)}
            </Button>
          ))}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="hover:bg-transparent">
                  {headerGroup.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      className="h-10 whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="transition-colors hover:bg-accent/40"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id} className="whitespace-nowrap py-2.5">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={columns.length}
                    className="h-20 text-center text-sm text-muted-foreground"
                  >
                    {tierFilter
                      ? `No sessions in the ${tierFilter} band.`
                      : "No sessions yet."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

import { Badge } from "@/components/ui/badge"
import type { SeverityTier } from "@/lib/api"
import { TIER_STYLES } from "@/lib/format"

export function TierBadge({
  tier,
  className = "",
}: {
  tier: SeverityTier | null | undefined
  className?: string
}) {
  if (!tier) {
    return (
      <Badge variant="outline" className={`text-muted-foreground ${className}`}>
        No tier
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      className={`capitalize ${TIER_STYLES[tier]} ${className}`}
    >
      {tier}
    </Badge>
  )
}

/**
 * Whether the objective (camera-derived) signal contributed to the tier.
 *
 * This matters more than it looks: when the gaze fit fails its quality gates the
 * tier rests on the self-reported score alone. Showing the tier without this
 * would imply the camera measurement backed it up when it did not.
 */
export function ObjectiveSignalBadge({
  usable,
}: {
  usable: boolean | null | undefined
}) {
  if (usable === null || usable === undefined) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Unknown
      </Badge>
    )
  }
  return usable ? (
    <Badge
      variant="outline"
      className="border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
    >
      Used
    </Badge>
  ) : (
    <Badge
      variant="outline"
      className="border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
    >
      Not used
    </Badge>
  )
}

/**
 * Protocol comparability. Three states, not two -- `null` means the session was
 * scored before fidelity assessment existed, which is different from failing it.
 */
export function ProtocolBadge({
  comparable,
}: {
  comparable: boolean | null | undefined
}) {
  if (comparable === null || comparable === undefined) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Not assessed
      </Badge>
    )
  }
  return comparable ? (
    <Badge
      variant="outline"
      className="border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
    >
      Protocol match
    </Badge>
  ) : (
    <Badge
      variant="outline"
      className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300"
    >
      Off protocol
    </Badge>
  )
}

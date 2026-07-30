import * as React from "react"

const MOBILE_BREAKPOINT = 768
const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

/**
 * Viewport-width check for the sidebar's mobile behaviour.
 *
 * Written with useSyncExternalStore rather than useState plus useEffect. The
 * effect version had to call setState in the effect body to pick up the initial
 * width, which React flags as a cascading render: the first paint used a stale
 * value and was thrown away immediately. useSyncExternalStore reads the real value
 * during render on the client and takes a separate server snapshot for SSR, so the
 * sidebar never renders the wrong variant first.
 */
function subscribe(onStoreChange: () => void) {
  const query = window.matchMedia(QUERY)
  query.addEventListener("change", onStoreChange)
  return () => query.removeEventListener("change", onStoreChange)
}

function getSnapshot() {
  return window.matchMedia(QUERY).matches
}

/** Rendered on the server, where there is no viewport: assume desktop. */
function getServerSnapshot() {
  return false
}

export function useIsMobile() {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}

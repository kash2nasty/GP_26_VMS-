import * as React from "react"

/**
 * True once the component has hydrated on the client, false during SSR.
 *
 * The usual `useState(false)` plus `useEffect(() => setMounted(true))` does the
 * same job, but React flags it as a cascading render: the first paint uses a value
 * that is immediately replaced. useSyncExternalStore expresses the same thing
 * without a state update, because it takes a separate server snapshot by design.
 *
 * The subscribe callback never fires. There is no external store here, only two
 * different constant answers depending on where the render happened.
 */
const neverChanges = () => () => {}
const onClient = () => true
const onServer = () => false

export function useIsHydrated(): boolean {
  return React.useSyncExternalStore(neverChanges, onClient, onServer)
}

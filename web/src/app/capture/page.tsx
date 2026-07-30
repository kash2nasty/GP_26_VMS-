import { ApiError } from "@/components/api-error"
import { CaptureClient } from "@/components/capture-client"
import { DashboardShell, SectionHeader } from "@/components/dashboard-shell"
import { ApiUnreachableError, fetchSessions } from "@/lib/api"

/**
 * Capture page. The disclaimer text is fetched server-side from the API for the
 * same reason every other page does it: the wording lives in the Python scoring
 * modules so a frontend change cannot quietly reword or drop it.
 *
 * The camera work itself is in a Client Component, because getUserMedia and
 * WebSockets only exist in the browser.
 */
export default async function CapturePage() {
  let disclaimers
  try {
    disclaimers = (await fetchSessions()).disclaimers
  } catch (error) {
    if (error instanceof ApiUnreachableError) {
      return (
        <DashboardShell title="New session" backHref="/sessions" backLabel="Sessions">
          <ApiError message={error.message} />
        </DashboardShell>
      )
    }
    throw error
  }

  return (
    <DashboardShell title="New session" backHref="/sessions" backLabel="Sessions">
      <SectionHeader
        as="h1"
        eyebrow="New capture"
        title="Record a session"
        description="Your browser captures the video and sends frames to the local Python service, which does all of the tracking and scoring. Nothing leaves this machine."
      />
      <CaptureClient disclaimers={disclaimers} targetReps={5} />
    </DashboardShell>
  )
}

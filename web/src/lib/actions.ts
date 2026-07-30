"use server"

/**
 * Server Actions for mutations.
 *
 * Deletion runs here rather than as a browser fetch for two reasons: the API base
 * URL stays server-side, and the DELETE never leaves this machine's server
 * process, so the Python CORS policy can stay GET-only.
 */

import { revalidatePath } from "next/cache"

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000"

export type DeleteResult =
  | { ok: true; deleted: string[]; movedTo: string }
  | { ok: false; error: string }

export async function deleteSession(id: string): Promise<DeleteResult> {
  let response: Response
  try {
    response = await fetch(
      `${API_BASE_URL}/sessions/${encodeURIComponent(id)}`,
      { method: "DELETE", cache: "no-store" }
    )
  } catch {
    return {
      ok: false,
      error:
        "Could not reach the screening API. Check that it is running, then try again.",
    }
  }

  if (response.status === 404) {
    return { ok: false, error: "That session no longer exists." }
  }
  if (!response.ok) {
    return {
      ok: false,
      error: `The API refused the delete (${response.status}).`,
    }
  }

  const body = (await response.json()) as {
    deleted?: string[]
    moved_to?: string
  }

  // Both views read the session list, so both need refreshing.
  revalidatePath("/sessions")
  revalidatePath(`/sessions/${id}`)

  return {
    ok: true,
    deleted: body.deleted ?? [],
    movedTo: body.moved_to ?? "_deleted/",
  }
}

export type BulkDeleteResult = {
  deleted: string[]
  failed: Array<{ id: string; error: string }>
}

/**
 * Delete several sessions.
 *
 * Sequential rather than concurrent, and it keeps going after a failure. Both
 * choices are about the report it returns: the caller needs to know exactly which
 * ids were removed, and firing a dozen concurrent DELETEs at a single-worker uvicorn
 * process while it may also be servicing a capture buys nothing here.
 */
export async function deleteSessions(ids: string[]): Promise<BulkDeleteResult> {
  const result: BulkDeleteResult = { deleted: [], failed: [] }
  for (const id of ids) {
    const outcome = await deleteSession(id)
    if (outcome.ok) {
      result.deleted.push(id)
    } else {
      result.failed.push({ id, error: outcome.error })
    }
  }
  return result
}

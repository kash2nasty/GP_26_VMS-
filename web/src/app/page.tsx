import { redirect } from "next/navigation"

/** The sessions list is the only meaningful entry point, so send the root there. */
export default function Home() {
  redirect("/sessions")
}

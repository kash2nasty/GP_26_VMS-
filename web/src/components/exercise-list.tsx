/**
 * Recommended exercises.
 *
 * Two things are load-bearing here:
 *
 * 1. The exercise disclaimer and safety note render BEFORE the exercises, not
 *    after. This is the one screen that tells someone to do physical activity,
 *    so the caution has to arrive before the instructions rather than as a
 *    footnote below them.
 *
 * 2. An empty exercise list is rendered as an explicit explanation, never as an
 *    empty section. The Python layer returns zero exercises when the session data
 *    was too poor to assign a tier, and that refusal is a deliberate safety
 *    behaviour -- a blank panel would read as a rendering bug and invite someone
 *    to go looking for the "real" list.
 */

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ExerciseDisclaimer } from "@/components/disclaimer"
import type { Disclaimers, RecommendedExercises } from "@/lib/api"

export function ExerciseList({
  recommendations,
  disclaimers,
}: {
  recommendations?: RecommendedExercises
  disclaimers: Disclaimers
}) {
  const exercises = recommendations?.exercises ?? []

  return (
    <section className="space-y-4" aria-labelledby="exercises-heading">
      <div className="space-y-1">
        {recommendations?.protocol ? (
          <p className="eyebrow">From the {recommendations.protocol}</p>
        ) : null}
        <h2 id="exercises-heading" className="text-lg leading-snug font-semibold">
          Suggested exercises
        </h2>
      </div>

      <ExerciseDisclaimer
        text={recommendations?.disclaimer || disclaimers.exercises}
        safetyNote={recommendations?.safety_note || disclaimers.safety_note}
      />

      {recommendations?.summary ? (
        <p className="max-w-[70ch] text-sm leading-relaxed">
          {recommendations.summary}
        </p>
      ) : null}

      {exercises.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No exercises suggested</CardTitle>
            <CardDescription className="leading-relaxed">
              {recommendations?.summary ??
                "This session did not produce a severity tier, so no exercises " +
                  "are suggested. That is deliberate rather than a gap: " +
                  "suggesting physical exercises from data that could not be " +
                  "interpreted would not be safe."}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-3 @3xl/main:grid-cols-2">
          {exercises.map((exercise, index) => (
            <Card key={exercise.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-base">
                    <span className="mr-2 text-muted-foreground tabular-nums">
                      {index + 1}.
                    </span>
                    {exercise.name}
                  </CardTitle>
                  {exercise.protocol_stage ? (
                    <Badge variant="secondary" className="shrink-0 text-xs">
                      {exercise.protocol_stage}
                    </Badge>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="flex-1 space-y-3 text-sm">
                {exercise.description ? (
                  <p className="leading-relaxed">{exercise.description}</p>
                ) : null}
                {exercise.suggested_frequency ? (
                  <div>
                    <p className="eyebrow">How often</p>
                    <p className="leading-relaxed">
                      {exercise.suggested_frequency}
                    </p>
                  </div>
                ) : null}
                {exercise.rationale ? (
                  <div>
                    <p className="eyebrow">Why this one</p>
                    <p className="leading-relaxed text-muted-foreground">
                      {exercise.rationale}
                    </p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {recommendations?.progression ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Progressing from here</CardTitle>
            <CardDescription className="leading-relaxed">
              {recommendations.progression}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {recommendations?.typical_course ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {recommendations.typical_course}
        </p>
      ) : null}

      {recommendations?.protocol_references?.length ? (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium">
            Protocol sources
          </summary>
          <ul className="mt-2 space-y-1 pl-4">
            {recommendations.protocol_references.map((reference) => (
              <li key={reference} className="list-disc break-words">
                {reference}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}

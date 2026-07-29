"""General vestibular habituation exercise suggestions, mapped from severity tier.

SOURCE OF THE EXERCISES
    The catalogue below follows the published Cawthorne-Cooksey habituation
    protocol (Cawthorne 1946; Cooksey 1946), which is organised in graded sets
    progressing from head-still eye movements, through seated head and shoulder
    movements, to standing and then walking/dynamic activity. Descriptions and
    frequency norms are drawn from published patient-facing renderings of that
    protocol -- see PROTOCOL_REFERENCES. They are general exercises, not a
    program tailored to any individual.

WHY HIGHER SEVERITY GETS FEWER AND GENTLER EXERCISES
    This is the load-bearing design decision here, and it inverts the naive
    mapping. Habituation works by repeated exposure at an intensity the person
    can actually tolerate; provocation beyond that is counter-productive and can
    set someone back. So a more-provoked screening result yields a SHORTER, more
    conservative starting set -- seated, eyes open, brief -- while a
    less-provoked result can begin nearer the dynamic end of the protocol.
    A tier -> difficulty mapping that handed the most provoked person the most
    aggressive exercises would be backwards and potentially harmful.

    At the 'pronounced' tier, sustained head rotation -- the very movement the
    subtest uses to provoke symptoms -- is deliberately withheld from the
    starting set until a clinician has reviewed the result. See TIER_PLANS.

NO TIER MEANS NO EXERCISES
    When the session data was insufficient to assign a tier, recommend() returns
    an empty exercise list. Suggesting physical exercises off data we could not
    interpret is not a defensible default.
"""
from __future__ import annotations

from .severity import (
    STATUS_INSUFFICIENT,
    TIER_MILD,
    TIER_MINIMAL,
    TIER_MODERATE,
    TIER_PRONOUNCED,
)

EXERCISES_SCHEMA_VERSION = "0.1.0"

PROTOCOL_NAME = "Cawthorne-Cooksey habituation exercises"

PROTOCOL_REFERENCES = [
    "Cawthorne T. Vestibular injuries. Proc R Soc Med. 1946;39:270-273.",
    "Cooksey FS. Rehabilitation in vestibular injuries. Proc R Soc Med. "
    "1946;39:273-278.",
    "Balance & Dizziness Canada. Cawthorne-Cooksey habituation exercises. "
    "https://balanceanddizziness.org/diagnosis-and-treatment/"
    "vestibular-rehabilitation/cawthorne-cooksey-habituation-exercises/",
]

# Protocol frequency norm, applied unless an exercise overrides it. Published
# renderings converge on 2-3 sessions daily, roughly 5 repetitions per exercise,
# building duration gradually; a typical course runs 6-8 weeks.
DEFAULT_FREQUENCY = (
    "2 to 3 times a day, about 5 repetitions each. Build up from a few seconds "
    "to 1-2 minutes per exercise as tolerated."
)

TYPICAL_COURSE = (
    "Published renderings of the protocol describe a typical course of 6 to 8 "
    "weeks, with progression paced by individual tolerance rather than a fixed "
    "schedule."
)

SAFETY_NOTE = (
    "Mild, short-lived symptoms during these exercises are expected -- that "
    "controlled provocation is how habituation is thought to work. Stop and seek "
    "advice if symptoms are severe, do not settle after finishing, or worsen over "
    "several days. Have someone nearby for anything done with the eyes closed or "
    "while standing or walking, and use a handrail on stairs or slopes."
)

DISCLAIMER = (
    "These are general published exercises shown for information only. They are "
    "not personalized medical advice, not a program tailored to this individual, "
    "and they do not identify, confirm, or rule out any medical condition. "
    "Consult a qualified clinician -- a physician, physiotherapist, or "
    "audiologist -- before beginning any exercise program, particularly if there "
    "is any history of neck injury, fainting, or falls."
)

# ---- exercise catalogue --------------------------------------------------
# Defined once here and referenced by key from TIER_PLANS, so descriptions stay
# single-sourced and the tier mapping below stays reviewable at a glance.

EXERCISE_CATALOGUE = {
    "eye_movements_slow_then_fast": {
        "name": "Eye movements, slow then faster",
        "protocol_stage": "Seated or lying, head still",
        "description": (
            "Keeping your head completely still, look up and then down, then from "
            "side to side. Do it slowly at first, then a little faster once slow "
            "movements are comfortable."
        ),
    },
    "thumb_focus_near_far": {
        "name": "Near-far thumb focus",
        "protocol_stage": "Seated or lying, head still",
        "description": (
            "Hold your thumb up at arm's length and focus on it. Slowly bring it "
            "in toward your face to about 30 cm (12 inches) and back out again, "
            "keeping it in focus the whole time."
        ),
    },
    "head_bend_forward_backward": {
        "name": "Head bending forward and backward",
        "protocol_stage": "Seated",
        "description": (
            "Sitting upright, bend your head slowly forward to bring your chin "
            "toward your chest, then slowly back as far as is comfortable. Start "
            "with your eyes open."
        ),
    },
    "head_turn_side_to_side": {
        "name": "Head turning side to side",
        "protocol_stage": "Seated",
        "description": (
            "Sitting upright, turn your head slowly from side to side as far as is "
            "comfortable. Start with your eyes open, and only progress to eyes "
            "closed once the eyes-open version stops provoking much."
        ),
    },
    "shoulder_shrugs_and_circles": {
        "name": "Shoulder shrugs and circles",
        "protocol_stage": "Seated",
        "description": (
            "Shrug your shoulders up and down, then circle them forward and "
            "backward."
        ),
    },
    "seated_forward_bend_pickup": {
        "name": "Bending forward to pick up objects",
        "protocol_stage": "Seated",
        "description": (
            "From sitting, bend forward as if picking an object up off the floor in "
            "front of you, then return to sitting upright."
        ),
    },
    "sit_to_stand": {
        "name": "Sit to stand",
        "protocol_stage": "Standing",
        "description": (
            "Stand up from sitting and sit back down again, repeatedly. Start with "
            "your eyes open; progress to eyes closed only with someone beside you."
        ),
    },
    "ball_toss_hand_to_hand": {
        "name": "Ball passing, hand to hand",
        "protocol_stage": "Standing",
        "description": (
            "Throw a small ball from hand to hand above eye level, then pass it "
            "from hand to hand under one knee while bending forward."
        ),
    },
    "standing_turn_circle": {
        "name": "Turning in a full circle",
        "protocol_stage": "Standing",
        "description": (
            "From standing, turn all the way around in a full circle, pause, then "
            "repeat in the other direction."
        ),
    },
    "walk_across_room": {
        "name": "Walking across the room",
        "protocol_stage": "Moving about",
        "description": (
            "Walk across the room with your eyes open, and later with your eyes "
            "closed while someone walks beside you."
        ),
    },
    "walk_with_head_turns": {
        "name": "Walking while turning the head",
        "protocol_stage": "Moving about",
        "description": (
            "Walk in a straight line while turning your head from side to side, "
            "keeping your walking pace steady."
        ),
    },
    "slope_or_stairs": {
        "name": "Walking up and down a slope or stairs",
        "protocol_stage": "Moving about",
        "description": (
            "Walk up and down a gentle slope or a flight of stairs with your eyes "
            "open, using a handrail."
        ),
    },
}

# ---- tier -> plan --------------------------------------------------------
# Each entry pairs an exercise key with the rationale for THAT tier, so the same
# exercise can be justified differently depending on where the person is starting.

TIER_PLANS = {
    TIER_PRONOUNCED: {
        "summary": (
            "A deliberately minimal, seated starting set. The aim at this tier is "
            "to find a level that provokes very little, not to push through "
            "symptoms."
        ),
        "progression": (
            "Sustained head rotation -- the movement this subtest uses to provoke "
            "symptoms -- is intentionally left out of this starting set. Adding it, "
            "and any standing or walking work, should follow a clinician's review "
            "rather than a fixed timetable."
        ),
        "exercises": [
            ("eye_movements_slow_then_fast",
             "Head-still eye movements are the gentlest entry point in the "
             "protocol, so they let habituation begin without reproducing the "
             "head rotation that provoked symptoms during the test."),
            ("thumb_focus_near_far",
             "Trains the eyes to hold a target independently of head movement, "
             "which is the same fixation demand the subtest measured -- but here "
             "with the head kept still."),
            ("shoulder_shrugs_and_circles",
             "Included to release neck and shoulder guarding, which is common when "
             "someone has been bracing against provoking head movements."),
        ],
    },
    TIER_MODERATE: {
        "summary": (
            "A seated set that begins reintroducing the provoking movement itself, "
            "slowly and with the eyes open."
        ),
        "progression": (
            "Keep the eyes open until the seated head movements stop provoking "
            "much, then progress to eyes closed, and only then to standing work."
        ),
        "exercises": [
            ("eye_movements_slow_then_fast",
             "Establishes the head-still baseline before head movement is added."),
            ("thumb_focus_near_far",
             "Rehearses holding fixation on a near target, the same demand the "
             "subtest scored."),
            ("head_turn_side_to_side",
             "This is the direct habituation counterpart of the provoking movement "
             "in the visual-motion subtest, reintroduced slowly and seated."),
            ("head_bend_forward_backward",
             "Broadens habituation to a second head axis, so tolerance is not "
             "limited to side-to-side motion alone."),
            ("shoulder_shrugs_and_circles",
             "Reduces neck and shoulder tension that can otherwise limit how far "
             "the head movements can comfortably go."),
        ],
    },
    TIER_MILD: {
        "summary": (
            "The seated set plus early standing work, reflecting a screening result "
            "that suggests reasonable tolerance already."
        ),
        "progression": (
            "Add the eyes-closed variants once the eyes-open versions are "
            "comfortable, then move toward the walking exercises listed for the "
            "minimal tier."
        ),
        "exercises": [
            ("eye_movements_slow_then_fast",
             "Quick warm-up that also lets you gauge how provoked you are on a "
             "given day before doing more."),
            ("thumb_focus_near_far",
             "Maintains the fixation-during-movement skill the subtest measures."),
            ("head_turn_side_to_side",
             "The habituation counterpart of the provoking movement; at this tier "
             "it can usually be built toward the full comfortable range."),
            ("head_bend_forward_backward",
             "Extends habituation to a second head axis."),
            ("seated_forward_bend_pickup",
             "Introduces whole-body movement and a changing head position while "
             "still seated and supported."),
            ("sit_to_stand",
             "First standing exercise in the protocol, adding a vertical position "
             "change to the movements already tolerated."),
            ("ball_toss_hand_to_hand",
             "Requires the eyes to track a moving target while standing, combining "
             "gaze and postural demands."),
        ],
    },
    TIER_MINIMAL: {
        "summary": (
            "A screening result in this band may not call for a structured program "
            "at all. What follows is optional maintenance and general conditioning "
            "work from the more dynamic end of the protocol."
        ),
        "progression": (
            "These are already near the dynamic end of the protocol. If none of "
            "them provoke symptoms, there may be nothing further to habituate, and "
            "whether to continue is a conversation for a clinician."
        ),
        "exercises": [
            ("head_turn_side_to_side",
             "Retained as a periodic self-check: this is the movement the subtest "
             "probes, so it is a useful way to notice any change over time."),
            ("sit_to_stand",
             "General postural conditioning with a vertical position change."),
            ("standing_turn_circle",
             "Whole-body rotation, a step beyond isolated head rotation."),
            ("walk_across_room",
             "Adds locomotion, where balance relies on vestibular input more than "
             "it does when standing still."),
            ("walk_with_head_turns",
             "Combines head rotation with walking -- the closest everyday "
             "equivalent of the demand the subtest measures."),
            ("slope_or_stairs",
             "Adds a changing surface and visual scene, near the dynamic end of "
             "the protocol."),
        ],
    },
}


def _build_exercise(key: str, rationale: str) -> dict:
    entry = EXERCISE_CATALOGUE[key]
    return {
        "id": key,
        "name": entry["name"],
        "protocol_stage": entry["protocol_stage"],
        "description": entry["description"],
        "suggested_frequency": entry.get("frequency", DEFAULT_FREQUENCY),
        "rationale": rationale,
    }


def recommend(severity_tier: str | None, status: str | None = None) -> dict:
    """Build the recommended_exercises block for a severity tier.

    A tier of None -- or an unrecognised tier -- yields an empty exercise list
    with an explanation, never a fallback set. Suggesting physical exercises off
    data we could not interpret is not a safe default.
    """
    plan = TIER_PLANS.get(severity_tier) if severity_tier else None

    if plan is None:
        reason = (
            "No exercises are suggested because the session did not produce a "
            "severity tier."
        )
        if status == STATUS_INSUFFICIENT:
            reason += (
                " The session data was insufficient -- re-run the session and "
                "score it again."
            )
        elif severity_tier is not None:
            reason += f" Unrecognised severity tier: {severity_tier!r}."
        return {
            "exercises_schema_version": EXERCISES_SCHEMA_VERSION,
            "protocol": PROTOCOL_NAME,
            "severity_tier": severity_tier,
            "summary": reason,
            "progression": None,
            "exercises": [],
            "typical_course": None,
            "safety_note": SAFETY_NOTE,
            "protocol_references": PROTOCOL_REFERENCES,
            "disclaimer": DISCLAIMER,
        }

    return {
        "exercises_schema_version": EXERCISES_SCHEMA_VERSION,
        "protocol": PROTOCOL_NAME,
        "severity_tier": severity_tier,
        "summary": plan["summary"],
        "progression": plan["progression"],
        "exercises": [_build_exercise(k, why) for k, why in plan["exercises"]],
        "typical_course": TYPICAL_COURSE,
        "safety_note": SAFETY_NOTE,
        "protocol_references": PROTOCOL_REFERENCES,
        "disclaimer": DISCLAIMER,
    }

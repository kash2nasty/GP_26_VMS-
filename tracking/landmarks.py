"""MediaPipe Face Landmarker landmark index constants (478-landmark model)."""

# Iris ring centers. Only present when the 478-landmark (refined) model runs.
LEFT_IRIS_CENTER = 468
LEFT_IRIS_RING = (469, 470, 471, 472)
RIGHT_IRIS_CENTER = 473
RIGHT_IRIS_RING = (474, 475, 476, 477)

# Eye socket corners. "Outer" = toward the temple, "inner" = toward the nose.
#
# NAMING CAVEAT, relied on by tracking/face_tracker.py and scoring/indications.py:
# "LEFT" and "RIGHT" here name the two landmark groups as MediaPipe indexes them.
# Which anatomical side of the subject each group falls on has never been verified
# against a labelled capture in this project. Everything that only needs the two
# eyes to agree with each other (the iris sign convention, gaze compensation) is
# unaffected. Anything that reports a SIDE to a reader must say the side is
# unverified. See ANATOMICAL_SIDE_CAVEAT.
LEFT_EYE_OUTER = 33
LEFT_EYE_INNER = 133
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145

RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374

# Stable mid-face points, used as a fallback pose reference.
NOSE_TIP = 1
CHIN = 199
FOREHEAD = 10

# Mouth corners and mid-brow peaks, used for the resting facial-symmetry measure.
# Same naming caveat as the eyes above.
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291
LEFT_BROW_PEAK = 105
RIGHT_BROW_PEAK = 334

ANATOMICAL_SIDE_CAVEAT = (
    "Side labels follow the landmark groups in tracking/landmarks.py, which have "
    "not been verified against the subject's anatomical left and right. Read the "
    "magnitude of any asymmetry as measured, and confirm which side is affected by "
    "looking at the person."
)

"""MediaPipe Face Landmarker landmark index constants (478-landmark model)."""

# Iris ring centers — only present when the 478-landmark (refined) model runs.
LEFT_IRIS_CENTER = 468
LEFT_IRIS_RING = (469, 470, 471, 472)
RIGHT_IRIS_CENTER = 473
RIGHT_IRIS_RING = (474, 475, 476, 477)

# Eye socket corners. "Outer" = toward the temple, "inner" = toward the nose.
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

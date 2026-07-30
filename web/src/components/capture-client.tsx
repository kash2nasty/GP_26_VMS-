"use client"

/**
 * Browser capture for the VOMS visual-motion subtest.
 *
 * The browser is a camera and a display. It grabs frames, ships them to Python
 * over a WebSocket, and renders the progress Python sends back. It does no
 * analysis: every number here originates from the same pipeline the CLI uses.
 *
 * TWO DETAILS THAT ARE EASY TO GET WRONG
 *
 * 1. The preview is mirrored for comfort, but the frames sent to Python are NOT.
 *    Mirroring the captured pixels would invert head yaw and swap which eye is
 *    which, which is exactly the left/right sign confusion that once silently
 *    destroyed the gaze signal in the Python layer. The mirror is a CSS transform
 *    on the <video> element only; the canvas draws from the unmirrored source.
 *
 * 2. The metronome is audible, not just visual. The patient is supposed to be
 *    staring at their own thumb, so a purely on-screen pacing cue would be
 *    invisible exactly when it matters. Pace is also the thing this project found
 *    it was getting wrong: uncontrolled rotation speed makes sessions
 *    incomparable, so helping the user hold 50 bpm is a correctness feature, not
 *    decoration.
 */

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  CameraIcon,
  CircleStopIcon,
  LoaderCircleIcon,
  TriangleAlertIcon,
  Volume2Icon,
  VolumeXIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { Disclaimers } from "@/lib/api"

/** Standardized protocol: 80 deg each side at 50 bpm, one beat per direction. */
const CADENCE_BPM = 50
const BEAT_MS = (60 / CADENCE_BPM) * 1000
const TARGET_AMPLITUDE_DEG = 80
const CAPTURE_FPS = 15
const FRAME_WIDTH = 640
const FRAME_HEIGHT = 480
const JPEG_QUALITY = 0.7
/** Skip a frame rather than queue it if the socket is already backed up. */
const MAX_BUFFERED_BYTES = 512 * 1024

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"

function websocketUrl(): string {
  const base = API_BASE.replace(/^http/, "ws").replace(/\/$/, "")
  return `${base}/ws/capture`
}

type Phase = "intro" | "starting" | "recording" | "scoring" | "saving" | "error"

type Progress = {
  frames: number
  face: boolean
  yaw: number | null
  reps: number
  elapsed_s: number
  complete: boolean
}

export function CaptureClient({
  disclaimers,
  targetReps = 5,
}: {
  disclaimers: Disclaimers
  targetReps?: number
}) {
  const router = useRouter()

  const [phase, setPhase] = React.useState<Phase>("intro")
  const [error, setError] = React.useState<string | null>(null)
  const [progress, setProgress] = React.useState<Progress | null>(null)
  const [beat, setBeat] = React.useState(0)
  const [soundOn, setSoundOn] = React.useState(true)
  const [maxYaw, setMaxYaw] = React.useState(0)

  const videoRef = React.useRef<HTMLVideoElement | null>(null)
  const streamRef = React.useRef<MediaStream | null>(null)
  const socketRef = React.useRef<WebSocket | null>(null)
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null)
  const frameTimer = React.useRef<number | null>(null)
  const beatTimer = React.useRef<number | null>(null)
  const audioRef = React.useRef<AudioContext | null>(null)
  const soundOnRef = React.useRef(true)
  const finishedRef = React.useRef(false)
  /**
   * True once the capture has reached any terminal state: saved, aborted, or
   * already reporting an error. The close handler checks it so a socket closing as
   * a CONSEQUENCE of one of those does not overwrite the specific message with a
   * generic connection error.
   */
  const settledRef = React.useRef(false)

  React.useEffect(() => {
    soundOnRef.current = soundOn
  }, [soundOn])

  // ---- teardown ---------------------------------------------------------

  const stopEverything = React.useCallback(() => {
    if (frameTimer.current !== null) {
      window.clearInterval(frameTimer.current)
      frameTimer.current = null
    }
    if (beatTimer.current !== null) {
      window.clearInterval(beatTimer.current)
      beatTimer.current = null
    }
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (audioRef.current) {
      void audioRef.current.close()
      audioRef.current = null
    }
  }, [])

  React.useEffect(() => {
    return () => {
      // Leaving the page mid-capture: tell the server to discard, then tear down.
      const socket = socketRef.current
      if (socket && socket.readyState === WebSocket.OPEN && !finishedRef.current) {
        socket.send(JSON.stringify({ type: "abort" }))
      }
      socket?.close()
      stopEverything()
    }
  }, [stopEverything])

  // ---- metronome --------------------------------------------------------

  const tick = React.useCallback((index: number) => {
    if (!soundOnRef.current) return
    try {
      if (!audioRef.current) {
        audioRef.current = new AudioContext()
      }
      const ctx = audioRef.current
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      // Two pitches so left and right beats are distinguishable by ear alone.
      osc.frequency.value = index % 2 === 0 ? 660 : 440
      gain.gain.setValueAtTime(0.0001, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.09)
      osc.connect(gain).connect(ctx.destination)
      osc.start()
      osc.stop(ctx.currentTime + 0.1)
    } catch {
      // Audio is a convenience; never let it break the capture.
    }
  }, [])

  // ---- capture ----------------------------------------------------------

  const sendFrame = React.useCallback(() => {
    const video = videoRef.current
    const socket = socketRef.current
    if (!video || !socket || socket.readyState !== WebSocket.OPEN) return
    if (video.readyState < 2) return
    if (socket.bufferedAmount > MAX_BUFFERED_BYTES) return

    if (!canvasRef.current) {
      canvasRef.current = document.createElement("canvas")
      canvasRef.current.width = FRAME_WIDTH
      canvasRef.current.height = FRAME_HEIGHT
    }
    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // NOTE: no mirroring here on purpose -- see the header comment.
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const current = socketRef.current
        if (current && current.readyState === WebSocket.OPEN) {
          current.send(blob)
        }
      },
      "image/jpeg",
      JPEG_QUALITY
    )
  }, [])

  const begin = React.useCallback(async () => {
    setError(null)
    setPhase("starting")
    finishedRef.current = false
    settledRef.current = false

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: FRAME_WIDTH, height: FRAME_HEIGHT, facingMode: "user" },
        audio: false,
      })
    } catch (cause) {
      const name = cause instanceof DOMException ? cause.name : ""
      setError(
        name === "NotAllowedError"
          ? "Camera access was blocked. Allow camera access for this site in your browser, then try again."
          : name === "NotFoundError"
            ? "No camera was found. Connect a webcam and try again."
            : `Could not start the camera: ${String(cause)}`
      )
      setPhase("error")
      return
    }

    streamRef.current = stream
    if (videoRef.current) {
      videoRef.current.srcObject = stream
      try {
        await videoRef.current.play()
      } catch {
        // Autoplay restrictions: the muted+playsInline video normally avoids this.
      }
    }

    let socket: WebSocket
    try {
      socket = new WebSocket(websocketUrl())
    } catch (cause) {
      setError(`Could not open a connection to the API: ${String(cause)}`)
      setPhase("error")
      stopEverything()
      return
    }
    socketRef.current = socket

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "start", target_reps: targetReps }))
    }

    socket.onerror = () => {
      settledRef.current = true
      setError(
        "Lost the connection to the screening API. Check that it is running on " +
          `${API_BASE} and try again.`
      )
      setPhase("error")
      stopEverything()
    }

    socket.onclose = () => {
      if (finishedRef.current || settledRef.current) {
        stopEverything()
        return
      }
      // A socket dying mid-capture used to tear the camera down silently and leave
      // the UI on "Recording" with a frozen frame counter, so the only symptom of a
      // crashed backend was that nothing happened. Say so instead.
      settledRef.current = true
      stopEverything()
      setError(
        "The connection to the screening API closed before this session finished, " +
          "so nothing was written to disk. Check that the Python service is still " +
          "running, then start again."
      )
      setPhase("error")
    }

    socket.onmessage = (event) => {
      let message: Record<string, unknown>
      try {
        message = JSON.parse(String(event.data))
      } catch {
        return
      }

      if (message.type === "error") {
        settledRef.current = true
        setError(String(message.detail ?? "Capture failed."))
        setPhase("error")
        stopEverything()
        return
      }

      if (message.type === "ready") {
        setPhase("recording")
        frameTimer.current = window.setInterval(
          sendFrame,
          Math.round(1000 / CAPTURE_FPS)
        )
        let index = 0
        tick(index)
        setBeat(index)
        beatTimer.current = window.setInterval(() => {
          index += 1
          setBeat(index)
          tick(index)
        }, BEAT_MS)
        return
      }

      if (message.type === "progress") {
        const update = message as unknown as Progress
        setProgress(update)
        if (typeof update.yaw === "number") {
          setMaxYaw((previous) => Math.max(previous, Math.abs(update.yaw as number)))
        }
        if (update.complete) {
          finishedRef.current = true
          stopEverything()
          setPhase("scoring")
        }
        return
      }

      if (message.type === "saved") {
        finishedRef.current = true
        stopEverything()
        socket.close()
        router.push(`/sessions/${String(message.id)}`)
      }
    }
  }, [router, sendFrame, stopEverything, targetReps, tick])

  const stopRecording = React.useCallback(() => {
    finishedRef.current = true
    stopEverything()
    setPhase("scoring")
  }, [stopEverything])

  const submitScore = React.useCallback(
    (score: number | null) => {
      const socket = socketRef.current
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        settledRef.current = true
        setError(
          "The connection closed before this session could be saved. The capture " +
            "was not written to disk."
        )
        setPhase("error")
        return
      }
      setPhase("saving")
      socket.send(JSON.stringify({ type: "finish", symptom_score: score }))
    },
    []
  )

  const discard = React.useCallback(() => {
    settledRef.current = true
    const socket = socketRef.current
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "abort" }))
      socket.close()
    }
    stopEverything()
    router.push("/sessions")
  }, [router, stopEverything])

  // ---- rendering --------------------------------------------------------

  const direction = beat % 2 === 0 ? "left" : "right"
  const reps = progress?.reps ?? 0
  const amplitudeShare = Math.min(1, maxYaw / TARGET_AMPLITUDE_DEG)

  return (
    <div className="space-y-4">
      {phase === "intro" ? (
        <IntroCard disclaimers={disclaimers} targetReps={targetReps} onBegin={begin} />
      ) : null}

      {phase === "error" ? (
        <Card className="ring-destructive/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TriangleAlertIcon className="size-4" />
              Capture could not continue
            </CardTitle>
            <CardDescription className="leading-relaxed">{error}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button onClick={begin}>Try again</Button>
            <Button variant="outline" onClick={() => router.push("/sessions")}>
              Back to sessions
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {(phase === "starting" ||
        phase === "recording" ||
        phase === "scoring" ||
        phase === "saving") ? (
        <div className="grid gap-4 @4xl/main:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card className="overflow-hidden">
            <CardContent className="p-0">
              <div className="relative aspect-4/3 bg-muted">
                <video
                  ref={videoRef}
                  muted
                  playsInline
                  // Mirrored for the viewer only. The canvas that feeds Python
                  // draws from the unmirrored source.
                  className="size-full -scale-x-100 object-cover"
                />
                {phase === "recording" ? (
                  <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-2 bg-linear-to-b from-black/60 to-transparent p-3 text-white">
                    <span className="flex items-center gap-2 text-sm font-medium">
                      <span className="size-2 animate-pulse rounded-full bg-red-500" />
                      Recording
                    </span>
                    <span className="text-sm tabular-nums">
                      {progress ? `${progress.elapsed_s.toFixed(1)}s` : "0.0s"}
                    </span>
                  </div>
                ) : null}
                {phase === "recording" && progress && !progress.face ? (
                  <div className="absolute inset-x-0 bottom-0 bg-red-600/90 p-2 text-center text-sm font-medium text-white">
                    No face detected. Move back into frame.
                  </div>
                ) : null}
                {phase === "starting" ? (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <LoaderCircleIcon className="size-6 animate-spin text-muted-foreground" />
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            {phase === "recording" ? (
              <PacingCard
                direction={direction}
                reps={reps}
                targetReps={targetReps}
                yaw={progress?.yaw ?? null}
                maxYaw={maxYaw}
                amplitudeShare={amplitudeShare}
                soundOn={soundOn}
                onToggleSound={() => setSoundOn((on) => !on)}
                onStop={stopRecording}
              />
            ) : null}

            {phase === "scoring" ? (
              <ScoreCard
                reps={reps}
                frames={progress?.frames ?? 0}
                onSubmit={submitScore}
                onDiscard={discard}
              />
            ) : null}

            {phase === "saving" ? (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <LoaderCircleIcon className="size-4 animate-spin" />
                    Analysing and saving
                  </CardTitle>
                  <CardDescription>
                    Python is scoring the capture. This takes a moment.
                  </CardDescription>
                </CardHeader>
              </Card>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function IntroCard({
  disclaimers,
  targetReps,
  onBegin,
}: {
  disclaimers: Disclaimers
  targetReps: number
  onBegin: () => void
}) {
  return (
    <div className="space-y-4">
      {/* This test deliberately provokes symptoms. The caution belongs before the
          start button, not after the fact. */}
      <Card className="bg-amber-50 ring-amber-300 dark:bg-amber-950/40 dark:ring-amber-900">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TriangleAlertIcon className="size-4" />
            Before you begin
          </CardTitle>
          <CardDescription className="space-y-2 leading-relaxed text-amber-950 dark:text-amber-100">
            <p>
              This test is designed to provoke symptoms. Dizziness, nausea,
              headache or fogginess are expected outcomes, not signs that something
              went wrong. <strong>Stop at any time</strong> using the stop button.
            </p>
            <p>
              Sit down for it. Do not attempt it standing if you are prone to
              falls, and have someone nearby if you are unsteady.
            </p>
            <p>{disclaimers.screening}</p>
          </CardDescription>
        </CardHeader>
      </Card>

      <Card className="hero-wash">
        <CardHeader>
          <CardTitle className="text-lg">How to perform the test</CardTitle>
          <CardDescription>
            The standardized protocol: {TARGET_AMPLITUDE_DEG}° to each side at{" "}
            {CADENCE_BPM} beats per minute, {targetReps} repetitions.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <ol className="space-y-3">
            {[
              "Sit facing the camera with your whole face in frame and reasonable light on it. Avoid strong light behind you.",
              "Hold one thumb up at arm's length, roughly level with your eyes.",
              "Keep your eyes locked on your thumb for the entire test. Do not let your gaze drift to the screen.",
              "Rotate your head, eyes and thumb together as one unit, turning your neck rather than just moving your eyes.",
              "A tone will sound each time you should reach a turning point. High tone means turn left, low tone means turn right.",
            ].map((step, index) => (
              <li key={step} className="flex gap-3">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground tabular-nums">
                  {index + 1}
                </span>
                <span className="leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>
          <Separator />
          <p className="max-w-[68ch] text-muted-foreground">
            Turn your volume up so you can hear the pacing tones, because you should
            be looking at your thumb rather than at this screen. Rotation speed
            changes the result, so keeping to the beat is what makes one session
            comparable to another.
          </p>
          {/* The wider signal set needs a few seconds of a squarely presented face
              to measure anything about it, and a test made entirely of turning the
              head does not otherwise provide them. */}
          <p className="max-w-[68ch] text-muted-foreground">
            Before the sweeps begin, face the camera squarely for a few seconds. The
            eyelid, eye alignment and facial symmetry checks can only be measured
            while the head is near frontal, and without those frames they report as
            not assessable.
          </p>
          <Button onClick={onBegin} className="w-full sm:w-auto">
            <CameraIcon className="size-4" />
            Start camera and begin
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function PacingCard({
  direction,
  reps,
  targetReps,
  yaw,
  maxYaw,
  amplitudeShare,
  soundOn,
  onToggleSound,
  onStop,
}: {
  direction: "left" | "right"
  reps: number
  targetReps: number
  yaw: number | null
  maxYaw: number
  amplitudeShare: number
  soundOn: boolean
  onToggleSound: () => void
  onStop: () => void
}) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardDescription>Turn to your</CardDescription>
          <CardTitle
            key={direction + String(reps)}
            className="text-3xl uppercase tracking-tight"
          >
            {direction}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <div
              className={`h-2 flex-1 rounded-full transition-colors ${
                direction === "left" ? "bg-primary" : "bg-muted"
              }`}
            />
            <div
              className={`h-2 flex-1 rounded-full transition-colors ${
                direction === "right" ? "bg-primary" : "bg-muted"
              }`}
            />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Repetitions
              </p>
              <p className="text-2xl font-semibold tabular-nums">
                {reps}
                <span className="text-base text-muted-foreground"> / {targetReps}</span>
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Head angle
              </p>
              <p className="text-2xl font-semibold tabular-nums">
                {yaw === null ? "n/a" : `${yaw > 0 ? "+" : ""}${yaw.toFixed(0)}°`}
              </p>
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-baseline justify-between text-xs">
              <span className="uppercase tracking-wide text-muted-foreground">
                Widest turn so far
              </span>
              <span className="tabular-nums text-muted-foreground">
                {maxYaw.toFixed(0)}° of {TARGET_AMPLITUDE_DEG}°
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width]"
                style={{ width: `${Math.round(amplitudeShare * 100)}%` }}
              />
            </div>
            {amplitudeShare < 0.75 ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Turn further if you comfortably can, because the protocol asks for{" "}
                {TARGET_AMPLITUDE_DEG}° each way.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button variant="destructive" onClick={onStop}>
          <CircleStopIcon className="size-4" />
          Stop
        </Button>
        <Button variant="outline" onClick={onToggleSound}>
          {soundOn ? (
            <Volume2Icon className="size-4" />
          ) : (
            <VolumeXIcon className="size-4" />
          )}
          {soundOn ? "Sound on" : "Sound off"}
        </Button>
      </div>
    </>
  )
}

function ScoreCard({
  reps,
  frames,
  onSubmit,
  onDiscard,
}: {
  reps: number
  frames: number
  onSubmit: (score: number | null) => void
  onDiscard: () => void
}) {
  const [selected, setSelected] = React.useState<number | null>(null)

  return (
    <Card>
      <CardHeader>
        <CardTitle>How much did that provoke your symptoms?</CardTitle>
        <CardDescription className="leading-relaxed">
          Dizziness, nausea, headache or fogginess. 0 means none at all, 10 means
          the worst imaginable. Captured {reps} repetition
          {reps === 1 ? "" : "s"} over {frames} frames.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          {Array.from({ length: 11 }, (_, score) => (
            <Button
              key={score}
              variant={selected === score ? "default" : "outline"}
              size="icon"
              onClick={() => setSelected(score)}
              aria-label={`Score ${score}`}
              className="tabular-nums"
            >
              {score}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={selected === null} onClick={() => onSubmit(selected)}>
            Save session
          </Button>
          <Button variant="outline" onClick={() => onSubmit(null)}>
            Save without a score
          </Button>
          <Button variant="ghost" onClick={onDiscard}>
            Discard
          </Button>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          The score is the outcome measure this test is built around, so saving
          without one limits what the result can say. Discarding writes nothing.
        </p>
      </CardContent>
    </Card>
  )
}

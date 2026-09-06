"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  PhoneOff,
  Video,
  VideoOff,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type RemoteParticipant,
} from "livekit-client";
import { InterviewerStage, type InterviewerPresence } from "@/components/candidate/interviewer-stage";
import { Button } from "@/components/ui/button";
import { completeInviteSession, getPublicInvite, startInviteSession } from "@/lib/api/invites";
import type { PublicInvite, SessionStart } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import {
  formatQuestionProgress,
  resolveQuestionProgress,
} from "@/lib/interview/question-progress";

type RoomUiState =
  | "preparing"
  | "connecting"
  | "connected"
  | "interviewer_joining"
  | "ready"
  | "listening"
  | "speaking"
  | "reconnecting"
  | "connection_lost"
  | "completed"
  | "failed";

export default function InterviewRoomPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = params.token;
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [session, setSession] = useState<SessionStart | null>(null);
  const [uiState, setUiState] = useState<RoomUiState>("preparing");
  const [error, setError] = useState<string | null>(null);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [questionIndex, setQuestionIndex] = useState(1);
  const roomRef = useRef<Room | null>(null);
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null);
  const startedAtRef = useRef<number>(Date.now());

  const presence: InterviewerPresence = useMemo(() => {
    if (uiState === "speaking") return "speaking";
    if (uiState === "listening" || uiState === "ready") return "listening";
    if (uiState === "connecting" || uiState === "preparing" || uiState === "interviewer_joining") {
      return "connecting";
    }
    return "idle";
  }, [uiState]);

  const statusLabel = useMemo(() => {
    const map: Record<RoomUiState, string> = {
      preparing: "Preparing",
      connecting: "Connecting",
      connected: "Connected",
      interviewer_joining: "Interviewer joining",
      ready: "Ready",
      listening: "Listening",
      speaking: "Interviewer speaking",
      reconnecting: "Reconnecting",
      connection_lost: "Connection lost",
      completed: "Completed",
      failed: "Unable to connect",
    };
    return map[uiState];
  }, [uiState]);

  const disconnectRoom = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) {
      await room.disconnect();
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const publicInvite = await getPublicInvite(token);
        if (cancelled) return;
        setInvite(publicInvite);
        if (!publicInvite.consent_accepted || !publicInvite.can_begin_setup) {
          router.replace(`/interview/${token}`);
          return;
        }
        setUiState("connecting");
        const started = await startInviteSession(token);
        if (cancelled) return;
        setSession(started);
        if (started.questions_total) setQuestionIndex(1);

        const setupRaw = sessionStorage.getItem(`firstround.setup.${token}`);
        const setup = setupRaw ? JSON.parse(setupRaw) : {};
        setCameraEnabled(Boolean(setup.cameraEnabled));

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
        });
        roomRef.current = room;

        room.on(RoomEvent.ConnectionStateChanged, (state) => {
          if (state === "connecting") setUiState("connecting");
          if (state === "connected") setUiState((prev) => (prev === "reconnecting" ? "ready" : "connected"));
          if (state === "reconnecting") setUiState("reconnecting");
          if (state === "disconnected") setUiState("connection_lost");
        });

        room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
          if (String(participant.identity || "").toLowerCase().includes("agent") ||
              String(participant.identity || "").toLowerCase().includes("interview")) {
            setUiState("ready");
          } else {
            setUiState("interviewer_joining");
          }
        });

        room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
          if (track.kind === Track.Kind.Audio && remoteAudioRef.current) {
            track.attach(remoteAudioRef.current);
            setUiState("speaking");
          }
        });

        room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
          const agentSpeaking = speakers.some((p) =>
            String(p.identity || "").toLowerCase().includes("agent") ||
            String(p.identity || "").toLowerCase().includes("interview"),
          );
          if (agentSpeaking) setUiState("speaking");
          else if (room.state === "connected") setUiState("listening");
        });

        room.on(RoomEvent.DataReceived, (payload) => {
          try {
            const text = new TextDecoder().decode(payload);
            const data = JSON.parse(text) as {
              type?: string;
              question_index?: number;
              questions_total?: number;
              completed?: boolean;
            };
            if (data.type === "interview_ui") {
              if (data.question_index) setQuestionIndex(data.question_index);
              if (data.completed) {
                setUiState("completed");
              }
            }
          } catch {
            // ignore non-JSON packets
          }
        });

        await room.connect(started.livekit_url, started.token);
        await room.localParticipant.setMicrophoneEnabled(true);
        if (setup.cameraEnabled) {
          await room.localParticipant.setCameraEnabled(true);
        }
        startedAtRef.current = Date.now();
        if (!cancelled) setUiState("ready");
      } catch (err) {
        if (!cancelled) {
          setUiState("failed");
          setError(
            err instanceof ApiError
              ? err.detail
              : "We could not start the interview room. Please return to setup and try again.",
          );
        }
      }
    })();

    return () => {
      cancelled = true;
      void disconnectRoom();
    };
  }, [token, router, disconnectRoom]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
    }, 250);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const room = roomRef.current;
    if (!room) return;
    const pub = Array.from(room.localParticipant.videoTrackPublications.values())[0];
    const track = pub?.track;
    if (localVideoRef.current && track) {
      track.attach(localVideoRef.current);
    }
  }, [cameraEnabled, uiState]);

  async function toggleMic() {
    const room = roomRef.current;
    if (!room) return;
    const next = !micEnabled;
    await room.localParticipant.setMicrophoneEnabled(next);
    setMicEnabled(next);
  }

  async function toggleCamera() {
    const room = roomRef.current;
    if (!room) return;
    const next = !cameraEnabled;
    await room.localParticipant.setCameraEnabled(next);
    setCameraEnabled(next);
  }

  async function endInterview() {
    setConfirmEnd(false);
    try {
      await disconnectRoom();
      await completeInviteSession(token);
      router.push(`/interview/${token}/complete`);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Interview ended locally, but status sync failed.",
      );
      router.push(`/interview/${token}/complete`);
    }
  }

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-4 sm:px-6">
        <header className="mb-4 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">FirstRound</div>
            <div className="text-xs text-zinc-400">
              {invite?.job_title || "Technical interview"}
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span className="tabular-nums">
              {formatQuestionProgress(
                resolveQuestionProgress({
                  questionsTotal: session?.questions_total,
                  questionIndex,
                }),
              )}
            </span>
            <span className="tabular-nums">{mm}:{ss}</span>
            <span className="inline-flex items-center gap-1">
              {uiState === "reconnecting" || uiState === "connection_lost" ? (
                <WifiOff className="h-3.5 w-3.5 text-amber-400" />
              ) : (
                <Wifi className="h-3.5 w-3.5 text-emerald-400" />
              )}
              <span>{statusLabel}</span>
            </span>
          </div>
        </header>

        <div className="grid flex-1 gap-4 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div className="flex justify-center">
            <InterviewerStage presence={presence} className="w-full max-w-lg border-zinc-800" />
          </div>
          <div className="space-y-4">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
              <div className="text-sm font-medium">Your preview</div>
              <div className="mt-3 aspect-video overflow-hidden rounded-xl border border-zinc-800 bg-black">
                {cameraEnabled ? (
                  <video
                    ref={localVideoRef}
                    muted
                    playsInline
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-zinc-500">
                    Camera off
                  </div>
                )}
              </div>
            </div>
            {error ? (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}
            {uiState === "reconnecting" ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
                Reconnecting to the interview room. Please stay on this page.
              </div>
            ) : null}
          </div>
        </div>

        <audio ref={remoteAudioRef} autoPlay />

        <footer className="mt-4 flex flex-wrap items-center justify-center gap-2 border-t border-zinc-900 pt-4">
          <Button
            variant="secondary"
            className="bg-zinc-900 text-zinc-50 hover:bg-zinc-800"
            onClick={() => void toggleMic()}
            aria-pressed={micEnabled}
          >
            {micEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            {micEnabled ? "Mute" : "Unmute"}
          </Button>
          <Button
            variant="secondary"
            className="bg-zinc-900 text-zinc-50 hover:bg-zinc-800"
            onClick={() => void toggleCamera()}
            aria-pressed={cameraEnabled}
          >
            {cameraEnabled ? <Video className="h-4 w-4" /> : <VideoOff className="h-4 w-4" />}
            Camera
          </Button>
          <Button variant="danger" onClick={() => setConfirmEnd(true)}>
            <PhoneOff className="h-4 w-4" />
            End interview
          </Button>
        </footer>
      </div>

      {confirmEnd ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 p-5 shadow-xl">
            <h2 className="text-lg font-semibold">End interview?</h2>
            <p className="mt-2 text-sm text-zinc-400">
              You may not be able to resume this session after ending. Your
              responses so far will be submitted to the hiring team.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmEnd(false)}>
                Keep interviewing
              </Button>
              <Button variant="danger" onClick={() => void endInterview()}>
                End interview
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

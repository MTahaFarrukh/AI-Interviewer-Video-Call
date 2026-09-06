"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { CandidateChrome } from "@/components/candidate/chrome";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { getPublicInvite } from "@/lib/api/invites";
import type { PublicInvite } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type CheckState = "pending" | "ok" | "warn" | "fail";

export default function InterviewSetupPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = params.token;
  const [invite, setInvite] = useState<PublicInvite | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [micPermission, setMicPermission] = useState<CheckState>("pending");
  const [micLevel, setMicLevel] = useState(0);
  const [browserOk, setBrowserOk] = useState<CheckState>("pending");
  const [networkOk, setNetworkOk] = useState<CheckState>("pending");
  const [mics, setMics] = useState<MediaDeviceInfo[]>([]);
  const [cams, setCams] = useState<MediaDeviceInfo[]>([]);
  const [selectedMic, setSelectedMic] = useState("");
  const [selectedCam, setSelectedCam] = useState("");
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rafRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getPublicInvite(token);
        if (cancelled) return;
        setInvite(data);
        if (!data.can_begin_setup) {
          setError(data.message || "This invite cannot start setup.");
        }
        if (!data.consent_accepted) {
          router.replace(`/interview/${token}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : "Invite unavailable");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  useEffect(() => {
    const supported =
      typeof navigator !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia &&
      typeof window !== "undefined" &&
      "WebSocket" in window &&
      "AudioContext" in window;
    setBrowserOk(supported ? "ok" : "fail");
    setNetworkOk(navigator.onLine ? "ok" : "warn");
    const onOnline = () => setNetworkOk("ok");
    const onOffline = () => setNetworkOk("warn");
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    let analyser: AnalyserNode | null = null;
    let audioCtx: AudioContext | null = null;
    let cancelled = false;

    async function startMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: selectedMic ? { deviceId: { exact: selectedMic } } : true,
          video: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setMicPermission("ok");
        const devices = await navigator.mediaDevices.enumerateDevices();
        setMics(devices.filter((d) => d.kind === "audioinput"));
        setCams(devices.filter((d) => d.kind === "videoinput"));
        audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        const data = new Uint8Array(analyser.fftSize);
        const tick = () => {
          if (!analyser) return;
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (const value of data) {
            const v = (value - 128) / 128;
            sum += v * v;
          }
          setMicLevel(Math.min(1, Math.sqrt(sum / data.length) * 4));
          rafRef.current = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        setMicPermission("fail");
      }
    }

    void startMic();
    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      void audioCtx?.close();
    };
  }, [selectedMic]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    async function startCam() {
      if (!cameraEnabled) {
        if (videoRef.current) videoRef.current.srcObject = null;
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: selectedCam ? { deviceId: { exact: selectedCam } } : true,
          audio: false,
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
      } catch {
        setCameraEnabled(false);
        setError("Camera could not be started. You can continue without it.");
      }
    }
    void startCam();
    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [cameraEnabled, selectedCam]);

  const ready = useMemo(() => {
    return micPermission === "ok" && browserOk === "ok" && networkOk !== "fail";
  }, [micPermission, browserOk, networkOk]);

  if (loading) {
    return (
      <CandidateChrome>
        <PageSkeleton />
      </CandidateChrome>
    );
  }

  if (error && !invite) {
    return (
      <CandidateChrome>
        <ErrorState title="Setup unavailable" description={error} />
      </CandidateChrome>
    );
  }

  return (
    <CandidateChrome eyebrow="System check">
      <Card>
        <CardHeader>
          <CardTitle>Check your setup</CardTitle>
          <p className="text-sm text-muted-foreground">
            Confirm microphone access before entering the interview room.
            Camera is optional.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <ChecklistItem
            label="Browser supported"
            state={browserOk}
            detail="WebSocket, getUserMedia, and AudioContext are required."
          />
          <ChecklistItem
            label="Microphone ready"
            state={micPermission}
            detail={
              micPermission === "fail"
                ? "Allow microphone access in your browser settings and retry."
                : "Speak to confirm input is detected."
            }
          />
          <div>
            <div className="mb-1 text-xs text-muted-foreground">Input level</div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-[width] duration-75"
                style={{ width: `${Math.round(micLevel * 100)}%` }}
              />
            </div>
          </div>
          <ChecklistItem
            label="Connection"
            state={networkOk}
            detail={
              networkOk === "warn"
                ? "You appear offline. Reconnect before entering."
                : "Browser reports an active network connection."
            }
          />

          <div className="rounded-xl border border-border p-3">
            <div className="text-sm font-medium">Speaker (optional)</div>
            <p className="mt-1 text-xs text-muted-foreground">
              Play a short tone to confirm your speakers or headphones work.
            </p>
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              type="button"
              onClick={() => {
                const Ctx =
                  window.AudioContext ||
                  (window as unknown as { webkitAudioContext: typeof AudioContext })
                    .webkitAudioContext;
                const ctx = new Ctx();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.frequency.value = 440;
                gain.gain.value = 0.05;
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                window.setTimeout(() => {
                  osc.stop();
                  void ctx.close();
                }, 400);
              }}
            >
              Play test tone
            </Button>
          </div>

          {mics.length > 0 ? (
            <div>
              <label className="mb-1.5 block text-sm font-medium" htmlFor="mic">
                Microphone
              </label>
              <select
                id="mic"
                className="h-10 w-full rounded-lg border border-border bg-card px-3 text-sm"
                value={selectedMic}
                onChange={(e) => setSelectedMic(e.target.value)}
              >
                <option value="">System default</option>
                {mics.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || "Microphone"}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="rounded-xl border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium">Camera (optional)</div>
                <div className="text-xs text-muted-foreground">
                  Enable a small self-view or skip for this interview.
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setCameraEnabled(true);
                  }}
                >
                  Enable camera
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCameraEnabled(false);
                  }}
                >
                  Skip camera
                </Button>
              </div>
            </div>
            {cams.length > 0 && cameraEnabled ? (
              <select
                className="mt-3 h-10 w-full rounded-lg border border-border bg-card px-3 text-sm"
                value={selectedCam}
                onChange={(e) => setSelectedCam(e.target.value)}
                aria-label="Camera"
              >
                <option value="">System default</option>
                {cams.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || "Camera"}
                  </option>
                ))}
              </select>
            ) : null}
            {cameraEnabled ? (
              <video
                ref={videoRef}
                muted
                playsInline
                className="mt-3 aspect-video w-full max-w-sm rounded-xl border border-border bg-black object-cover"
              />
            ) : null}
          </div>

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          <Button
            disabled={!ready || !invite?.can_begin_setup}
            onClick={() => {
              sessionStorage.setItem(
                `firstround.setup.${token}`,
                JSON.stringify({
                  micId: selectedMic || null,
                  camId: selectedCam || null,
                  cameraEnabled,
                }),
              );
              router.push(`/interview/${token}/room`);
            }}
          >
            Enter interview
          </Button>
        </CardContent>
      </Card>
    </CandidateChrome>
  );
}

function ChecklistItem({
  label,
  state,
  detail,
}: {
  label: string;
  state: CheckState;
  detail: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border p-3">
      <span
        className={cn(
          "mt-0.5 h-2.5 w-2.5 rounded-full",
          state === "ok" && "bg-emerald-500",
          state === "warn" && "bg-amber-500",
          state === "fail" && "bg-red-500",
          state === "pending" && "bg-zinc-300",
        )}
        aria-hidden
      />
      <div>
        <div className="text-sm font-medium">
          {label}
          <span className="sr-only"> status {state}</span>
        </div>
        <div className="text-xs text-muted-foreground">{detail}</div>
      </div>
    </div>
  );
}

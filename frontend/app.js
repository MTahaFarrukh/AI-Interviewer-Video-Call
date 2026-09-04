const landingScreen = document.getElementById("landing-screen");
const setupScreen = document.getElementById("setup-screen");
const joinForm = document.getElementById("join-form");
const interviewPanel = document.getElementById("interview-panel");
const completeScreen = document.getElementById("complete-screen");
const partialScreen = document.getElementById("partial-screen");
const nameInput = document.getElementById("candidate-name");
const startButton = document.getElementById("start-button");
const joinButton = document.getElementById("join-button");
const leaveButton = document.getElementById("leave-button");
const micButton = document.getElementById("mic-button");
const micCheckButton = document.getElementById("mic-check-button");
const micCheckLabel = document.getElementById("mic-check-label");
const statusEl = document.getElementById("status");
const candidateEl = document.getElementById("candidate-label");
const micEl = document.getElementById("mic-label");
const faceStage = document.getElementById("face-stage");
const mouth = document.getElementById("mouth");
const remoteAudio = document.getElementById("remote-audio");
const timerEl = document.getElementById("timer");
const progressEl = document.getElementById("progress-label");
const avatarImg = faceStage ? faceStage.querySelector("img") : null;

let room = null;
let micEnabled = true;
let analyser = null;
let animationId = 0;
let faceState = "idle";
let interruptUntil = 0;
let timerId = 0;
let interviewStartedAt = 0;
let interviewCompleted = false;
let interviewJoined = false;

function showScreen(el) {
  for (const screen of [landingScreen, setupScreen, interviewPanel, completeScreen, partialScreen]) {
    if (!screen) continue;
    screen.classList.toggle("hidden", screen !== el);
  }
}

function setStatus(text) {
  statusEl.textContent = text;
}

function setMicLabel() {
  micEl.textContent = micEnabled ? "Enabled" : "Disabled";
  micButton.textContent = micEnabled ? "Disable microphone" : "Enable microphone";
}

function formatTime(seconds) {
  const capped = Math.max(0, Math.floor(seconds));
  const mm = String(Math.floor(capped / 60)).padStart(2, "0");
  const ss = String(capped % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function startTimer() {
  stopTimer();
  interviewStartedAt = Date.now();
  timerEl.textContent = "00:00";
  timerId = window.setInterval(() => {
    timerEl.textContent = formatTime((Date.now() - interviewStartedAt) / 1000);
  }, 250);
}

function stopTimer() {
  if (timerId) {
    window.clearInterval(timerId);
    timerId = 0;
  }
}

function setFaceState(next) {
  faceState = next;
  faceStage.dataset.state = next;
  if (next !== "speaking") {
    mouth.style.height = "8px";
    mouth.style.width = "54px";
  }
}

function isAgentParticipant(participant) {
  const kind = String(participant.kind || "").toLowerCase();
  if (kind === "agent") return true;
  const identity = String(participant.identity || "").toLowerCase();
  return identity.includes("agent") || identity.includes("interviewer");
}

function readAgentState(participant) {
  const attrs = participant.attributes || {};
  return attrs["lk.agent.state"] || "";
}

function applyAgentState(state) {
  if (Date.now() < interruptUntil && state === "speaking") {
    return;
  }
  if (state === "speaking") {
    setStatus("Speaking");
    setFaceState("speaking");
  } else if (state === "listening") {
    setStatus("Listening");
    setFaceState("listening");
  } else if (state === "thinking") {
    setStatus("Thinking");
    setFaceState("listening");
  } else if (state === "initializing") {
    setStatus("Preparing");
    setFaceState("idle");
  } else {
    setStatus("Listening");
    setFaceState("idle");
  }
}

function applyInterviewUi(payload) {
  if (!payload || payload.type !== "interview_ui") return;
  const total = Number(payload.questions_total) || 0;
  const index = Number(payload.question_index) || 0;
  if (payload.completed || payload.phase === "wrap_up") {
    interviewCompleted = true;
    progressEl.textContent = total ? `Question ${total} of ${total}` : "Interview complete";
    return;
  }
  if (total > 0 && index > 0) {
    const suffix = payload.phase === "follow_up" ? " · follow-up" : "";
    progressEl.textContent = `Question ${index} of ${total}${suffix}`;
  }
}

function decodeDataPacket(payload) {
  try {
    const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch (_err) {
    return null;
  }
}

function startMouthAnimation() {
  if (animationId) return;
  const tick = () => {
    if (!analyser || faceState !== "speaking") {
      animationId = requestAnimationFrame(tick);
      return;
    }
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const centered = (data[i] - 128) / 128;
      sum += centered * centered;
    }
    const rms = Math.sqrt(sum / data.length);
    const open = Math.min(1, rms * 8);
    mouth.style.height = `${8 + open * 22}px`;
    mouth.style.width = `${54 + open * 16}px`;
    animationId = requestAnimationFrame(tick);
  };
  animationId = requestAnimationFrame(tick);
}

function attachAnalyser(track) {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx || !track.mediaStreamTrack) return;
  const ctx = new Ctx();
  const stream = new MediaStream([track.mediaStreamTrack]);
  const source = ctx.createMediaStreamSource(stream);
  analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);
  ctx.resume().catch(() => {});
  startMouthAnimation();
}

function markInterrupted() {
  interruptUntil = Date.now() + 400;
  setFaceState("interrupted");
  setStatus("Listening");
  setTimeout(() => {
    if (faceState === "interrupted") setFaceState("idle");
  }, 180);
}

function resetSessionUi() {
  interviewCompleted = false;
  interviewJoined = false;
  progressEl.textContent = "Interview in progress";
  timerEl.textContent = "00:00";
  stopTimer();
}

async function joinInterview(event) {
  event.preventDefault();
  const name = nameInput.value.trim();
  if (!name) return;

  joinButton.disabled = true;
  setStatus("Preparing");

  const response = await fetch("/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    setStatus("Could not start interview");
    joinButton.disabled = false;
    return;
  }

  const { token, url } = await response.json();
  const LK = window.LivekitClient;
  room = new LK.Room({
    adaptiveStream: true,
    dynacast: true,
  });

  room.on(LK.RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === LK.Track.Kind.Audio) {
      const el = track.attach();
      el.autoplay = true;
      remoteAudio.replaceChildren(el);
      attachAnalyser(track);
    }
  });

  room.on(LK.RoomEvent.ParticipantConnected, (participant) => {
    if (isAgentParticipant(participant)) {
      applyAgentState(readAgentState(participant) || "listening");
    }
  });

  room.on(LK.RoomEvent.ParticipantAttributesChanged, (_changed, participant) => {
    if (isAgentParticipant(participant)) {
      applyAgentState(readAgentState(participant));
    }
  });

  room.on(LK.RoomEvent.ActiveSpeakersChanged, (speakers) => {
    const localSpeaking = speakers.some((p) => p.identity === room.localParticipant.identity);
    const agentSpeaking = speakers.some((p) => isAgentParticipant(p));
    if (localSpeaking && (agentSpeaking || faceState === "speaking")) {
      markInterrupted();
    }
  });

  room.on(LK.RoomEvent.DataReceived, (payload) => {
    applyInterviewUi(decodeDataPacket(payload));
  });

  room.on(LK.RoomEvent.Disconnected, () => {
    stopTimer();
    setFaceState("idle");
    if (!interviewJoined) return;
    if (interviewCompleted) {
      showScreen(completeScreen);
    } else {
      showScreen(partialScreen);
    }
    room = null;
  });

  await room.connect(url, token);
  await room.localParticipant.setMicrophoneEnabled(true);
  micEnabled = true;
  setMicLabel();
  candidateEl.textContent = name;
  interviewJoined = true;
  interviewCompleted = false;
  showScreen(interviewPanel);
  startTimer();
  setStatus("Preparing");

  for (const participant of room.remoteParticipants.values()) {
    if (isAgentParticipant(participant)) {
      applyAgentState(readAgentState(participant) || "listening");
    }
  }
}

async function toggleMic() {
  if (!room) return;
  micEnabled = !micEnabled;
  await room.localParticipant.setMicrophoneEnabled(micEnabled);
  setMicLabel();
}

async function leaveInterview() {
  const completed = interviewCompleted;
  if (room) {
    await room.disconnect();
    room = null;
  }
  analyser = null;
  joinButton.disabled = false;
  setFaceState("idle");
  stopTimer();
  if (completed) {
    showScreen(completeScreen);
  } else if (interviewJoined) {
    showScreen(partialScreen);
  } else {
    showScreen(setupScreen);
  }
}

async function checkMicrophone() {
  micCheckLabel.textContent = "Checking microphone…";
  micCheckLabel.classList.remove("ok", "warn");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    micCheckLabel.textContent = "Microphone ready";
    micCheckLabel.classList.add("ok");
  } catch (_err) {
    micCheckLabel.textContent = "Microphone unavailable. Allow access to continue.";
    micCheckLabel.classList.add("warn");
  }
}

function returnHome() {
  resetSessionUi();
  joinButton.disabled = false;
  showScreen(landingScreen);
}

if (avatarImg) {
  avatarImg.addEventListener("error", () => {
    faceStage.classList.add("no-photo");
  });
}

startButton.addEventListener("click", () => {
  showScreen(setupScreen);
  nameInput.focus();
});
joinForm.addEventListener("submit", (event) => {
  joinInterview(event).catch((error) => {
    console.error(error);
    setStatus("Could not start interview");
    joinButton.disabled = false;
  });
});
micButton.addEventListener("click", () => {
  toggleMic().catch(console.error);
});
leaveButton.addEventListener("click", () => {
  leaveInterview().catch(console.error);
});
micCheckButton.addEventListener("click", () => {
  checkMicrophone().catch(console.error);
});
document.getElementById("done-complete-button").addEventListener("click", returnHome);
document.getElementById("done-partial-button").addEventListener("click", returnHome);
setMicLabel();
showScreen(landingScreen);

# Phase 1 test checklist

Do not mark a box unless that test was actually run.

## Connection

- [x] Agent joins LiveKit room
- [x] Candidate joins browser
- [x] Candidate microphone works

## Conversation

- [x] AI speaks
- [x] Candidate speaks
- [x] AI understands candidate
- [x] AI responds

## Barge-in

- [x] Candidate interrupts AI
- [x] AI stops speaking immediately
- [x] AI listens after interruption

## Face

- [x] 2D face visible
- [x] Face animates while AI speaks
- [x] Face returns to idle after interruption

## Observability

- [x] Latency measurement appears in logs
- [x] Session can remain active for several minutes



## How to verify barge-in in logs

Look for this sequence in the agent terminal, not only a UI animation:

```
[TURN] Agent speaking
[TURN] Candidate started speaking
[INTERRUPT] Agent interrupted
[TURN] Listening to candidate
```

Latency line format:

```
[LATENCY] candidate_stop_to_agent_audio_ms=<measured>
```



## Automated checks run during implementation

These were executed without real LiveKit / Gemini credentials:

- [x] Python config loads `FIRSTROUND_MODE=voice` and the Gemini 2.5 Live model id
- [x] `python src/agent.py --help` exposes `start` / `dev` / `console`
- [x] Gemini `RealtimeModel` constructs with compression + session resumption
- [x] Token endpoint mints a LiveKit JWT and dispatches `firstround-interviewer`
- [x] Frontend `/`, `/app.js`, and `/public/avatar.png` serve correctly
- [x] Agent worker process starts and registers the Google plugin

These were **not** executed (no `.env` with real keys on this machine):

- [ ] Agent joins a real LiveKit room
- [ ] Candidate microphone / AI speech / barge-in / measured latency on a live call
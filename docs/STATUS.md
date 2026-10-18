# Project status

Date: 2026-10-17

## Summary
Phase 0 is complete and every Phase 1 item that can be built without a bulb is implemented
and tested against a protocol-level fake bulb over real UDP. No physical H6004 has been
contacted. LAN Control availability on the actual units is still unverified.

## Verified (how)
- [x] GitHub CI passes install, ruff, compileall and pytest on the starter (run 39089150903, commit e45b8dd4)
- [x] GitHub CI green on this session's work: ruff clean, 30 passed on Linux (run 39090654305, commit 1138b12)
- [x] Local quickstart on Windows 11, Python 3.14.3, ruff 0.17.1: `ruff check .` clean, `pytest -q` 30 passed
- [x] Local simulation server: /health, start chase on four bulbs, frames advancing, stop (curl)
- [x] Browser UI in Chrome: four animated orbs, Start, per-bulb Status, Off refused with 409 while playback owns the bulb, diagnostics panel, no console errors
- [x] Engine drives four fake bulbs on 127.0.0.2-5 over UDP; devStatus read-back matches the last frame (tests/test_lan.py)
- [x] 25 ms command gap prevents the documented third-command drop; 0 ms gap reproduces it on the fake (test)
- [x] Benchmark CLI against fake-bulb CLI: 5 Hz target, 4.994 Hz achieved, 15/15 updates verified, state restored
- [ ] One physical H6004 identified with successful LAN discovery
- [ ] devStatus reply observed from a real bulb
- [ ] RGB and brightness packet application observed
- [ ] Safe rate benchmark recorded for one and four bulbs
- [ ] 10-minute single-bulb soak (Phase 1 acceptance)

## Added this session
- `GET /api/devices/{id}/status` (devStatus over UDP 4002, 1 s timeout, 504 on silence)
- `POST /api/devices/{id}/power`, refused unless `LIGHT_ENGINE_ALLOW_POWER=1`, 409 while playback owns the bulb
- `GET /api/diagnostics`: per-device sends, errors, consecutive errors, backoff
- Per-device exponential backoff on send errors (cap 30 s); recovery sends the current frame, never a backlog
- Per-device command spacing for every command (was only colour-to-brightness), configurable via `LIGHT_ENGINE_COMMAND_GAP_MS`
- Discovery `--interface` and `--write` (merge cache keyed by MAC, stable `govee-<mac>` IDs, stale-IP eviction)
- Device file validation: unknown fields, duplicate IPs
- `light_engine.bench` fire-and-verify benchmark; `light_engine.fakebulb` protocol emulator
- docs/HARDWARE_TEST.md acceptance script and result template

## Blocked on hardware (needs Matt, about 15 minutes)
Blocked: the remaining Phase 1 items need a powered H6004 on the LAN. Smallest useful step:
in Govee Home, check whether one bulb shows a LAN Control toggle and enable it, then run
steps 1 to 3 of docs/HARDWARE_TEST.md on a machine on the same subnet and paste the JSON
results. That answers whether the LAN path works at all and which rate to set.

## Next autonomous task
Phase 2 work that does not need hardware: separate render tick from output tick with an
injected clock, per-fixture ownership state machine, and config schema validation.

## Decisions already made
- Engine independent of Home Assistant and Matter
- Python asyncio backend, FastAPI controller, replaceable frontend
- Physical networking opt-in; simulation default; power control opt-in and never implicit
- Conservative provisional max output cadence 3 Hz per device, pending benchmark
- No resend of failed frames; the next tick supersedes them
- No purchase necessary for initial implementation

## Known gaps
- The LAN-mode server, discovery and benchmark all bind UDP 4002; run one at a time
- devStatus replies are matched by source IP only; any LAN host can spoof one (the protocol has no authentication)
- The starlette TestClient emits a deprecation warning about httpx; harmless today

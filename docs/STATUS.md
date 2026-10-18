# Project status

Date: 2026-10-17

## Starter scope
Core skeleton and docs prepared in the initial starter-kit branch. Real bulbs have not been tested and LAN Control availability on the actual H6004 units remains unverified.

## Intended verification
- [x] GitHub CI passes install, ruff, compileall and pytest (run 39089150903, commit e45b8dd4)
- [ ] Local simulation opens browser, plays/stops all four mock bulbs
- [ ] One physical H6004 identified with successful LAN discovery
- [ ] RGB and brightness packet application observed
- [ ] Safe rate benchmark recorded for one and four bulbs

## First autonomous task
CI is green. Run the local simulation smoke test, then implement mocked LAN discovery/status and explicit safe power control. Continue into benchmarking infrastructure without requiring early user involvement.

## Decisions already made
- Engine independent of Home Assistant and Matter
- Python asyncio backend, FastAPI controller, replaceable frontend
- Physical networking opt-in; simulation default
- Conservative provisional max output cadence 3 Hz per device
- No purchase necessary for initial implementation

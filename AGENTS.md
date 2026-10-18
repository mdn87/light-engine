# Desktop agent operating contract

This repository is a hands-on build, not a planning exercise. Continue implementing the system autonomously, exercising available tools, reading docs, writing code and tests, and resolving ordinary design questions without repeatedly asking the user for decisions.

## Objective
Deliver a stable local-first lighting animation controller for up to four Govee H6004 bulbs, hosted on a Ryzen 3 2200G desktop, with Home Assistant integration as an optional separate concern.

## First action
1. Inspect the entire repo and run ruff + pytest. Repair any starter errors before features.
2. Verify protocol assumptions against source docs and preserve citations/links in docs.
3. Implement the missing high-priority functionality from docs/IMPLEMENTATION_PLAN.md, starting with simulated behavior and integration tests.
4. Open focused PRs or commit on the user-directed feature branch. Do not rewrite history or merge to main without permission.

## Working standards
- Never claim a physical-device feature works without a recorded physical test.
- Favor minimal working increments over broad redesigns or speculative infrastructure.
- Make a reasonable reversible choice instead of blocking on noncritical ambiguity; document assumptions.
- Do not ask the user to run many trivial tests. Use mocks, test fixtures, simulation and code inspection yourself.
- Ask for assistance only when a real device, LAN setting, privileged network access or destructive host operation cannot be tested remotely.
- No extra purchases; use the stated Ryzen machine and available network equipment.
- Keep effect evaluation pure and independent from transports. Keep hardware access off by default.
- Avoid auto-scanning networks or turning on lights without an explicit command.
- Device update rate must be bounded and tunable. Do not schedule unbounded queues of stale frames.
- Keep secrets out of git. Respect that the project may be public.
- No unauthenticated LAN/public API exposure. Require an authenticated proxy or built-in authorization before enabling remote phone access.
- Preserve manual override semantics and prevent Home Assistant and the renderer from fighting for the same bulb.
- If hardware measurements invalidate the current architecture, change it and document evidence, not guesses.
- Run tests before each completed increment and report precisely what was verified.

## Completion and residual work
Complete obvious residuals in the current scope instead of ending with a list of tasks you could have done. Maintain docs/STATUS.md with verified progress, blockers, next steps and hardware test data. Do not gate implementation of testable work behind device tests.

## Non-goals for initial milestone
Do not install Proxmox, configure Matter, add MQTT, build an elaborate React keyframe timeline, or buy Zigbee hardware before one simulated end-to-end path and one controlled physical-bulb benchmark are established.

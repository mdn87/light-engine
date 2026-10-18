# Prioritized implementation plan

## Phase 0 - Baseline (starter delivered)
- [x] Python package, FastAPI and browser control page
- [x] Pure pulse / rainbow / fire / chase mathematical effects
- [x] Per-device bounded scheduler + simulation transport
- [x] Govee documented UDP write adapter and read-only discovery utility
- [x] Baseline tests, lint and Docker simulation
- [x] Confirm CI green on GitHub and repair any failures
- [x] Verify dependencies and quickstart on the desktop agent's environment (Windows 11, Python 3.14.3, 2026-10-17)

Acceptance: clean checkout passes checks, starts without hardware, demonstrates four virtual fixtures and Start/Stop.

## Phase 1 - Safe real-device communication
- [ ] Verify LAN Control toggle and actual H6004 SKU/version on at least one bulb
- [x] Implement explicit power on/off REST action with opt-in policy (simulation + fake bulb only)
- [x] Add status-response listener on UDP 4002 with scoped discovery, timeouts and verification (fake bulb only)
- [x] Add persistent device discovery cache and stable device IDs
- [x] Improve network error handling: dropped devices, retries/backoff, recovery and diagnostics (no retries by design: a missed frame is superseded by the next)
- [ ] Benchmark one bulb (RGB vs brightness updates) then four: sustainable update rate, dropped datagrams, perceived fade quality and drift
- [x] Benchmark tool written: `python -m light_engine.bench` (exercised against fake bulb only; real measurements still open above)
- [x] Write reproducible manual hardware acceptance script and result template (docs/HARDWARE_TEST.md)
- [ ] Address command spacing and network behavior using measurement rather than optimistic assumptions

Acceptance: single bulb can run a 10-minute pulse/recolor test, stop cleanly, no accumulating queue, and recorded observed delivery rate, model and firmware. Four bulbs next.

## Phase 2 - Engine correctness and reliability
- [ ] Design an explicit per-fixture ownership/arbitration state machine
- [ ] Separate render tick from transport output tick; simulate 30 FPS preview while output at measured rate
- [x] Keep global monotonic timebase for coherent multi-bulb phase offsets (layout positions, concurrent sends; docs/TIMELINE.md)
- [ ] Add presets/scenes persisted to SQLite + schema migration
- [ ] Unattended startup behavior, watchdog/health checks, graceful shutdown, restart policy
- [ ] Telemetry: desired vs observed state, errors, send cadence and queue age
- [ ] Config schema and validation, no hard-coded MACs
- [ ] Deterministic animation snapshots and timer tests with injected clock

Acceptance: simulation reliability test over hours and real repeated Start/Stop tests with no thread/task leaks or conflicts.

## Phase 3 - Editor and local UX
- [ ] React + TypeScript editor with device groups and browser-side high-FPS preview
- [ ] Preset library with versioned serialized effect parameters
- [ ] Responsive mobile-friendly layout
- [ ] Authenticated access over LAN/VPN with documented onboarding
- [x] Keyframe curve support: engine side done (linear/smooth/step easing, loop/ping_pong/once, per-position offset); editor UI still open
- [ ] Accessibility and reduced-motion controls for browser visualization

Acceptance: create, preview, save and launch a lighting scene from desktop and phone without editing JSON.

## Phase 4 - Home Assistant integration
- [ ] Document HA OS VM setup on Proxmox separately from engine deployment
- [ ] Define scene trigger endpoints + health/ownership feedback
- [ ] HA rest_command examples, scripts and optional entity definitions
- [ ] Prove no dual-writer conflicts
- [ ] Confirm Matter is optional and has no responsibility for the fast animation path

Acceptance: HA can start/stop scenes; manual overrides release ownership as documented.

## Phase 5 - Expand
- [ ] Audio-reactive input (opt-in mic/audio capture)
- [ ] Additional fixture adapters and per-zone output where actually supported
- [ ] Layered effects, advanced curves, timelines, chase choreography
- [ ] Cross-device synchronization benchmarking and transition smoothing
- [ ] Export/import scene packs and optional event/WebSocket connections

## Quality gate for every phase
- Document implemented vs unverified work
- Run unit/API/integration tests
- No silent network exposure, commands to unexpected devices or surprise power-on
- Keep out-of-scope features from delaying basic functionality

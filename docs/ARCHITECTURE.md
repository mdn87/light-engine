# System architecture

## Deployment goal

Proxmox VE on target AMD Ryzen 3 2200G + ASRock B450 Pro4 + 16 GB RAM + Samsung 850 Pro 256 GB SSD. Ethernet preferred. Proposed allocations: Home Assistant VM 2 vCPU / 4 GB / 40 GB; Debian lighting VM 2 vCPU / 2 GB / 24 GB. vCPUs are shared, not pinned. Confirm BIOS virtualization, NIC support, idle power and storage health before installation. This is a proposed platform, not an installation prerequisite.

Simpler initial path: run this Python app natively on a Linux machine or Debian VM. Do not over-build the infrastructure while testing a bulb.

## Logical pipeline

Browser -> FastAPI -> playback state -> pure effect generator -> bounded scheduler -> device-specific transport -> bulbs.

- Effects: mathematical function of monotonic elapsed time, fixture index, user parameters; no I/O.
- Engine: one owner per fixture; global monotonic epoch, per-fixture update frequency, skip unchanged frames and coalesce stale frames.
- Transports: protocol adapters; in-memory simulation and initial Govee LAN UDP.
- HTTP: validation and control, not a source of time-critical animation frames.
- UI: initial single-page non-framework controller; future React/TypeScript visual editor can replace it without rewriting effect evaluation.
- Persistence: eventually SQLite for devices, scenes, and presets; currently config file and in-memory playback only.

## Govee protocol

Official local UDP data path:
- Scan via multicast 239.255.255.250:4001
- Scan/status responses to UDP 4002
- Commands unicast to fixture IP:4003
- JSON envelope: {"msg":{"cmd":"brightness","data":{"value":55}}}
- Color is colorwc with RGB fields and colorTemInKelvin: 0
- Brightness uses 1..100; power uses turn value 0/1
- devStatus (empty data) to IP:4003 is answered on client UDP 4002 with onOff, brightness, color, colorTemInKelvin; replies are matched to requests by source IP
- Nothing is acknowledged. Per the protocol notes, a command arriving directly behind two others can be dropped silently, so the transport spaces every send to one device by LIGHT_ENGINE_COMMAND_GAP_MS (default 25 ms)

Real hardware support must be verified with firmware and Govee Home LAN toggle; no speculative undocumented frame formats. Color and brightness are independent commands, which constrains effective timing. Start near 3 frame updates/sec/device then measure and adapt; this is a conservative provisional policy, not a documented maximum. Avoid overclaiming 30 FPS.

## Ownership and overrides

When an effect owns a fixture, Home Assistant must trigger and stop effects through the engine rather than issuing conflicting color updates. Define later:
- manual device adjustment suspends effect for that fixture;
- release may retain final state or restore a captured state based on scene policy;
- lights do not unexpectedly power on after reboot;
- explicit opt-in for power-on and restore behaviors;
- loss of network drops stale frames rather than replaying a backlog.

## Network security

Govee LAN control is unauthenticated and unencrypted. VLAN/trusted subnet recommended. API currently unauthenticated, intentionally bound to 127.0.0.1. Use authenticated proxy / VPN for mobile access later. Avoid exposing UDP commands publicly.

## Why separate Home Assistant?

HA is ideal for sensors, automation and general device management, but is not the high-frequency frame clock. Engine remains usable without HA or Matter. HA integration can use rest_command to call saved-scene endpoints once implemented.

## Not yet implemented

Persistence, authentication, HA scene entities, Matter, music/audio input, transition profiling, WebSocket telemetry, React UI, timeline/keyframe editing, periodic background rediscovery, continuous fire-and-verify during playback, adaptive scheduling and comprehensive metrics.

Implemented since the starter: opt-in power control, devStatus requests, discovery cache with MAC-derived IDs, per-device error backoff and diagnostics, a fire-and-verify benchmark (`light_engine.bench`) and a protocol-level fake bulb (`light_engine.fakebulb`) for tests.

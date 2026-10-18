# Light Engine

A local-first programmable lighting service, designed initially for four Govee H6004 RGBWW smart bulbs illuminating 3D-printed decorations. Backend prototype is Python/FastAPI. Runs in simulation by default, with an explicit opt-in Govee LAN adapter. Home Assistant integration and a full visual timeline editor are planned, not implemented.

**Status: starter kit, not a validated hardware controller.** Code is a scaffold for an autonomous desktop coding agent. Do not present it as tested with physical H6004 bulbs until bench measurements exist.

## Architecture

- Ryzen 3 2200G / 16 GB / 256 GB SSD is the proposed always-on host.
- Proxmox VE is the future virtualization host. Home Assistant OS may run as one VM.
- Light Engine can run in a Debian VM or directly on Linux, independently of Home Assistant.
- FastAPI exposes controls to a minimal browser UI. The independent effect renderer outputs frames to a per-device scheduler.
- A pluggable transport sends frames to simulated devices or Govee LAN via UDP.
- Home Assistant eventually triggers saved scenes through the API. It must not fight the engine for bulb ownership.

See docs/ARCHITECTURE.md and docs/IMPLEMENTATION_PLAN.md.

## Start in simulation (safe)

Requires Python 3.11+.

    python -m venv .venv
    # Linux / macOS:
    . .venv/bin/activate
    # Windows PowerShell: .venv\Scripts\Activate.ps1
    pip install -e ".[dev]"
    pytest -q
    uvicorn light_engine.api:app --host 127.0.0.1 --port 8765

Open http://127.0.0.1:8765. The app shows four virtual bulbs. Change the effect, adjust controls, and press Start. Stop holds the last simulated frame. There is no Wi-Fi traffic in simulation.

Alternate simulation deployment:

    docker compose up --build

The Docker Compose port is bound to localhost only.

## First physical bulb (explicit opt-in)

1. Open Govee Home and verify a bulb exposes the LAN Control toggle; enable it. H6004 support in ecosystem lists does not establish that this particular firmware and retail unit have LAN control enabled.
2. Put the Linux machine on the same trusted subnet, preferably Ethernet.
3. Run discovery from native Linux (not from a Docker bridge):

       python -m light_engine.discovery

   Verify the returned IP and sku. Multicast discovery may require UDP 4001/4002 access.
4. Copy devices.json.example to devices.json and replace example addresses with verified private-LAN addresses. This file is gitignored.
5. Stop the simulation server. In the same shell, set:

       export LIGHT_ENGINE_MODE=lan
       export LIGHT_ENGINE_DEVICES_FILE="$PWD/devices.json"
       export LIGHT_ENGINE_MAX_HZ=3
       uvicorn light_engine.api:app --host 127.0.0.1 --port 8765

   In PowerShell use $env:LIGHT_ENGINE_MODE="lan", etc. The initial controller does not send a power-on command. Turn the test bulb on in Govee Home before running an effect.
6. Begin with ONE bulb and a low-speed pulse. Measure packet delivery and observed animation smoothness. Expand to four after validation.

CAUTION: Govee LAN UDP uses no authentication or encryption. Keep the control service and bulbs on a trusted/segmented LAN. Do not expose UDP 4001-4003 or port 8765 to the public internet. The app does not yet implement user authentication; do not bind it to 0.0.0.0 on a shared network without an authenticated reverse proxy.

## API (starter)

- GET /health
- GET /api/devices
- GET /api/effects
- GET /api/playback
- POST /api/playback/start
- POST /api/playback/stop

Example:

    curl -X POST http://127.0.0.1:8765/api/playback/start \
      -H "Content-Type: application/json" \
      -d '{"effect":"pulse","brightness":70,"minimum_brightness":12,"speed":1,"device_ids":["bulb-1"]}'

A stop request suspends animation without powering bulbs off. No persistence, scenes, home automation integration, or device state reconciliation have been implemented.

## Development

    pip install -e ".[dev]"
    ruff check .
    pytest -q

The unit and API tests run entirely in simulation. Continuous integration runs those checks on pushes and pull requests. Physical timing, H6004 compatibility, color fidelity, and reliability are unverified.

## Agent handoff

Read AGENTS.md, docs/HANDOFF.md, docs/IMPLEMENTATION_PLAN.md, and docs/HARDWARE.md before changing architecture. Work in short, testable increments. Build and finish Phase 1 before proposing major stack expansions.

Sources:
- Govee LAN WLAN guide: https://app-h5.govee.com/user-manual/wlan-guide
- LAN protocol notes: https://github.com/damient/govee-toolkit/blob/main/docs/protocol/lan.md
- Home Assistant Govee local: https://www.home-assistant.io/integrations/govee_light_local/
- Home Assistant Proxmox: https://www.home-assistant.io/installation/alternative/

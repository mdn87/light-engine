# Manual hardware acceptance script

Run on the always-on Linux host (or any machine on the bulbs' subnet), natively rather than
from a Docker bridge. Every step is read-only or touches only the bulb you name. Nothing here
powers a bulb on. Turn the test bulb on yourself in Govee Home first.

Record results in the template at the bottom and paste them into docs/HARDWARE.md (redact
MACs before posting publicly if you prefer).

## 0. Preconditions

- Govee Home: device settings show a **LAN Control** toggle and it is enabled. If the
  toggle is missing, stop and record that; the LAN adapter cannot work on that unit.
- Host and bulb are on the same subnet, with no Wi-Fi client isolation and UDP 4001-4003
  open in the host firewall.
- Nothing else on the host is bound to UDP 4002 (a running LAN-mode server is, so stop it).

## 1. Discovery (read-only)

    python -m light_engine.discovery --write devices.json
    # add --interface <host LAN IP> if the host has several interfaces

Pass: the bulb appears with `sku` and firmware fields, and devices.json gains an entry with
a `govee-<mac>` ID. Rename `name` freely; keep `id` stable once scenes reference it.

## 2. Status read (read-only)

    LIGHT_ENGINE_MODE=lan LIGHT_ENGINE_DEVICES_FILE=$PWD/devices.json \
      uvicorn light_engine.api:app --host 127.0.0.1 --port 8765
    curl -s http://127.0.0.1:8765/api/devices/<id>/status

Pass: JSON with `on`, `brightness` and `color` matching what Govee Home shows. A 504 means
no devStatus reply: LAN Control is off, or a firewall is blocking UDP 4002.

## 3. Single-bulb benchmark (stop the server first; it holds UDP 4002)

    python -m light_engine.bench --ip <bulb IP> --rate 1 --duration 30 --out bench-1x1hz.json
    python -m light_engine.bench --ip <bulb IP> --rate 3 --duration 60 --out bench-1x3hz.json
    python -m light_engine.bench --ip <bulb IP> --rate 5 --duration 60 --out bench-1x5hz.json
    python -m light_engine.bench --ip <bulb IP> --rate 3 --duration 60 --pattern brightness \
        --out bench-1x3hz-bright.json

Watch the bulb while each run goes. The benchmark refuses to run on a bulb that reports off
or does not answer, and restores the starting color and brightness when it finishes.

Read `applied_ratio` (share of updates confirmed by devStatus), `status_timeouts`, and
`status_rtt_ms`. Stop raising the rate when `applied_ratio` drops below 0.98 or timeouts
appear; the last clean rate is the candidate `LIGHT_ENGINE_MAX_HZ`.

Optional: repeat one run with `--gap-ms 0` to see whether this firmware drops the third
back-to-back command, as the protocol notes describe.

## 4. Four-bulb benchmark

    python -m light_engine.bench --ip <ip1> --ip <ip2> --ip <ip3> --ip <ip4> \
        --rate 3 --duration 120 --out bench-4x3hz.json

## 5. Ten-minute engine soak (Phase 1 acceptance)

    LIGHT_ENGINE_MODE=lan LIGHT_ENGINE_DEVICES_FILE=$PWD/devices.json \
      LIGHT_ENGINE_MAX_HZ=<measured rate> uvicorn light_engine.api:app --host 127.0.0.1 --port 8765
    curl -s -X POST http://127.0.0.1:8765/api/playback/start -H 'Content-Type: application/json' \
      -d '{"effect":"pulse","device_ids":["<id>"]}'
    # after 10 minutes:
    curl -s http://127.0.0.1:8765/api/diagnostics
    curl -s -X POST http://127.0.0.1:8765/api/playback/stop

Pass: smooth visible pulse for 10 minutes, diagnostics show `errors: 0` (or explained
errors), and the bulb stops changing within one second of the stop call.

## Result template

    Date:
    Host OS / network (wired or Wi-Fi):
    Bulb SKU / firmware (from discovery):
    LAN Control toggle present:          yes / no
    Discovery worked:                    yes / no
    devStatus matched app:               yes / no
    1 Hz applied_ratio / timeouts:
    3 Hz applied_ratio / timeouts:
    5 Hz applied_ratio / timeouts:
    brightness-only 3 Hz applied_ratio:
    gap 0 ms drops observed:             yes / no / not run
    4 bulbs 3 Hz applied_ratio (each):
    status_rtt_ms median / p95:
    10-minute soak result:
    Chosen LIGHT_ENGINE_MAX_HZ:
    Notes (visible stepping, resets, drift):

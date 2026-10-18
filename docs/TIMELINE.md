# Synced timelines and waves

Every bulb in a playback renders from one monotonic clock. A wave is the same pattern played
on each bulb with a delay that depends on where the bulb sits in the layout.

## Layout positions

A device entry may carry `position`, a number in slot units. Without it, a bulb's position is
its index in the playback's `device_ids` list (0, 1, 2, ...), which matches the earlier
behaviour. Positions let the physical order differ from the list order, leave gaps (0, 1, 3,
4) or put two bulbs at the same spot so they change together:

    [{"id": "porch-left", "name": "Porch left", "ip": "192.168.1.21", "position": 0},
     {"id": "porch-right", "name": "Porch right", "ip": "192.168.1.22", "position": 3}]

`phase_spread` is the delay per slot. For the built-in effects it is a fraction of the
effect's cycle; for a timeline it is a fraction of the timeline's length.

## Timeline effect

`effect: "timeline"` plays a list of keyframes. Each keyframe has `t` (seconds), `hue`
(0-360), `brightness` (1-100), optional `saturation` (0-1, default 1) and `ease`, which shapes
the move to the next keyframe: `linear`, `smooth` (smoothstep, the default) or `step` (hold,
then jump). `repeat` is `loop` (default), `ping_pong` or `once`. Hue moves the short way round
the colour wheel. A loop jumps from the last keyframe to the first, so repeat the first values
at the end for a seamless cycle. `speed` scales time.

Four bulbs in a row, amber to red to violet and back over 6 s, each a quarter-cycle behind
the one before:

    curl -X POST http://127.0.0.1:8765/api/playback/start -H "Content-Type: application/json" -d '{
      "effect": "timeline", "phase_spread": 0.25,
      "keyframes": [{"t": 0, "hue": 30, "brightness": 80}, {"t": 2, "hue": 0, "brightness": 40},
                    {"t": 4, "hue": 280, "brightness": 90}, {"t": 6, "hue": 30, "brightness": 80}]}'

Set `phase_spread` to 0 for all bulbs changing in unison. The browser UI has this demo as
"Timeline wave (demo keyframes)".

`light_engine.effects.sample(keyframes, t, repeat)` is pure, so timelines are tested at fixed
times without a clock or a transport (tests/test_timeline.py).

## Timing between bulbs

Each tick renders every due bulb at the same instant, then sends to all of them concurrently,
outside the engine lock. The command gap applies per bulb, so it no longer adds up across
bulbs. On loopback with a 25 ms gap, bulb 4's first packet now arrives within 15 ms of bulb
1's; the previous serial loop put it 94 ms behind (tests/test_lan.py). A bulb whose send is
still in flight is skipped on the next tick instead of queueing a second send, and a send that
finishes after a restart does not record its frame as current.

This is scheduler timing on loopback. How closely real bulbs change together depends on Wi-Fi
latency and firmware, which have not been measured.

## Low update rates

At about 3 updates per second, a timeline is sampled, not streamed: a keyframe shorter than
one update period (about 330 ms) can be skipped entirely. Keep segments at two update periods
or longer and prefer `smooth` easing, which hides stepping better than `linear`.

## Not done yet (from the design review)

A roundtable review (three ideators, one curator) produced this shortlist. Items 1, 3 and 4
are implemented above; the simultaneity goal of item 2 is met by concurrent sends.

- Scene files: versioned JSON holding layout plus timeline, with golden-frame snapshot tests.
- Deliberate staggered send phase across bulbs, compared with aligned sends in bench.py.
- A deadband that skips imperceptible changes, and a preview endpoint listing planned sends.
- Per-cue choice between simultaneous changes and a wave that follows the send order.
- Predicted-arrival rendering, worth revisiting only if real bulbs show per-command lag.

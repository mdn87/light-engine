# Copy/paste handoff for a desktop coding agent

You are taking over mdn87/light-engine. Read README.md, AGENTS.md, docs/ARCHITECTURE.md, docs/IMPLEMENTATION_PLAN.md, docs/HARDWARE.md and docs/STATUS.md. Work autonomously on this repo; verify the existing code before adding features. The repo begins with a simulation-safe FastAPI lighting engine, a Govee UDP adapter and deterministic effect functions.

Mission: deliver a dependable browser-controlled animation engine for four Govee H6004 bulbs, with pulse/breathing, rainbow, fire and chase patterns. User plans to use a Ryzen 3 2200G / 16GB desktop as always-on host. Home Assistant may run separately later under Proxmox, but must not be an initial prerequisite.

Start with ruff, pytest, and a complete simulation smoke test. Fix defects; don't stop after merely listing them. Then implement highest priority missing Phase 1 tasks that can be developed without physical access, especially status response handling, safe opt-in power control, diagnostics and benchmark tooling. Test with simulated UDP responses and mocks. Avoid broad overengineering or starting the React timeline editor before the network adapter is reliable.

Do not claim that any H6004 hardware test passed until results have actually been observed. Ask for the minimum physical interaction needed when blocked, such as turning on LAN Control and running a single documented smoke test. Proactively use tools and alternate test strategies rather than waiting for the user on work that can proceed. Complete residual code/test/doc changes in each session. Update docs/STATUS.md with verified state and your next autonomous task.

Create incremental commits/PRs and do not merge main without explicit instruction. Never expose an unauthenticated control API publicly. Keep networking opt-in, avoid surprise bulb power state changes, preserve testability through mock transports, and treat output-rate assumptions as provisional pending a measured benchmark.

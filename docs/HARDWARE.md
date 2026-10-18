# Target environment and measured data

## Proposed dedicated machine
- AMD Ryzen 3 2200G with integrated graphics
- 16 GB G.Skill Trident Z 3000 MHz
- Samsung 850 Pro 256 GB SATA SSD
- ASRock B450 Pro4 motherboard
- Corsair RM550x PSU
- Fractal Design Meshify C case
- Wi-Fi adapter present; use wired Ethernet if feasible
These are the proposed host specs supplied for planning, not a verified asset inventory.

## Bulbs
- Four Govee RGBWW A19 9 W 800 lm lamps from the user's Home Depot purchase
- Label/phone screenshots indicate H6004 and firmware 29.0
- Home Depot retail model number and underlying H-series identifier may differ
- Matter / Apple Home availability does not establish LAN API switch presence
- Need to inspect Govee Home app device settings for LAN Control on this exact hardware

## Physical test record (fill after testing)
Date:
Fixture MAC (redact from public issue if desired):
Fixture firmware:
Govee LAN toggle present:
Host OS / network:
Command pacing:
Target output rate:
Observed effective updates per second:
10-minute pulse behavior:
Four-device phase drift:
Lost frames or device resets:
Error recovery:
Conclusions and scheduler changes:

## Network
Devices and host should share a subnet supporting local UDP. Discovery multicast to 239.255.255.250:4001; status replies 4002; controls 4003. Be careful with Proxmox VM bridges, Docker networking, Wi-Fi client isolation and host firewalls. Verify connectivity instead of assuming it.

## Power
The PC consumes substantially more power at idle than a Pi 3B; measure actual wattage if running 24/7. Do not assume low idle power from CPU TDP.

## Performance
Four RGB bulbs will not tax the Ryzen CPU. The limiting variable is bulb protocol/firmware throughput and the inability to upload arbitrary animation timelines over the documented LAN API.

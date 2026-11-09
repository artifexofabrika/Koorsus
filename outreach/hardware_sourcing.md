# Hardware Sourcing Decision (2026-11-08)

## Chosen Board

**Yahboom Jetson Orin Nano 8GB SUB Super Developer Kit**

- Official NVIDIA Orin Nano 8GB core module on a Yahboom carrier board.
- 256GB NVMe SSD (installed), no microSD slot.
- Wi-Fi card and antennas included.
- Power supply included.
- Approximately $670 on Amazon (Yahboom seller).

## Why This Board

- Legitimate third-party carrier, same pattern as the Raspberry Pi
  ecosystem. The SoC comes from NVIDIA; the surrounding board is
  designed by Yahboom.
- Carrier board is layout-compatible with the official NVIDIA dev kit.
- Includes SSD, Wi-Fi, and power supply, which the official $399 kit
  does not.
- Official NVIDIA dev kits are currently out of stock or priced above
  $600 on the secondary market. The Yahboom kit is the only sane
  sourcing path at present.

## Practical Caveats

- No SD card slot. NVMe only.
- Flashing requires Yahboom's factory image and super boot procedure.
- NVIDIA SDK Manager does not always recognize the custom carrier.
- This is why the hardware-only tier is sold UNFLASHED.

## Enclosure

**Waveshare Aluminum Alloy Case for Jetson Orin**, with camera holder.
Approximately $22. Compatible with Orin Nano Super Developer Kit, Orin
Nano, and Orin NX kits.

- Hardware-only tier: can ship bare in anti-static packaging. Enclosure
  optional.
- Hardware + Software tier: must ship in the enclosure, mounted.

## Pricing Tiers (Cross-Reference)

See  for the full tier breakdown with
inclusions and exclusions:

1. Hardware Only — $1,200 (unflashed, no support)
2. Hardware + Software — $1,500 (flashed, no setup service)
3. Turnkey Orin — $3,500 (remote setup, 20 hours, 90 days support)
4. Turnkey NX — $5,500 (premium hardware tier)
5. Odoo Connector — $99 (App Store module)

## Sourcing Notes for Future Orders

- Amazon stock of the Yahboom kit fluctuates. Set up a stock alert.
- Alternative boards exist (Seeed reComputer J3011, TWOWIN T201) but
  have not been tested. Stick with Yahboom until the first ten units
  are shipped and proven.
- The Jetson market is volatile. DRAM price surges in mid-2026 pushed
  all Orin kits up 50-60%. Buy in small batches, do not stockpile
  unless you have a customer order in hand.

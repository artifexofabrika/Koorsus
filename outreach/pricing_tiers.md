# Myarra Pricing Tiers (Final 2026-11-08)

Every tier is sold as-is with the inclusions and exclusions stated below.
Nothing is implied. If it is not listed as included, it is not included.

---

## 1. Hardware Only — $1,200

**This is the box. You do everything yourself.**

### INCLUDED
- Yahboom Jetson Orin Nano 8GB SUB Developer Kit (official NVIDIA core
  module on Yahboom carrier board)
- 256GB NVMe SSD (installed)
- Wi-Fi card and antennas (installed)
- Power supply
- Waveshare aluminum alloy case with camera holder (~$22 value)
- Anti-static packaging

### NOT INCLUDED
- **NO SOFTWARE FLASHED.** The SSD is blank. You must flash JetPack and
  install Myarra and Koorsus yourself using the open-source repository.
- **NO OPERATING SYSTEM.** The board arrives as shipped by Yahboom.
- **NO SETUP, NO TRAINING, NO SUPPORT OF ANY KIND.** No phone, no email,
  no remote session. If you cannot get it running, that is your project.
- **NO ODOO CONNECTOR.** That is $99 separately.
- **NO MASTER DATA CONFIGURATION.** You populate your own lines, SKUs,
  BOMs, and rates via the Setup page.
- **NO WARRANTY BEYOND THE MANUFACTURER'S.** Yahboom's warranty passes
  to you. Artifexo Fabrika warrants nothing on this tier.
- **NO REFUNDS.**

### WHO BUYS THIS
Someone who wants the parts at a fair price and intends to do their own
build. This exists as the floor of the pricing ladder. It is not the
recommended path.

---

## 2. Hardware + Software Bundle — $1,500

**The box arrives ready to plug in. You still configure your own data.**

### INCLUDED
- Everything in Tier 1 (Yahboom kit, SSD, Wi-Fi, PSU, case)
- **JetPack and Linux flashed to the SSD by Artifexo Fabrika**
- **Myarra installed and configured with demo data**
- **Koorsus installed and indexed with sample documents**
- **The Telegram bot configured and paired**
- **A quick-start guide (PDF) for uploading your master data via the
  Setup page**
- Initial boot verified: the box powers on, the services start, the
  dashboard loads at the local IP.

### NOT INCLUDED
- **NO SETUP SERVICE OF ANY KIND.** You plug it in and do the data entry
  yourself.
- **NO REMOTE SETUP SESSION.**
- **NO ON-SITE VISIT.**
- **NO MASTER DATA ENTRY.** Your lines, SKUs, BOMs, rates, and jobs are
  yours to populate via the Setup page or CSV upload.
- **NO ODOO CONNECTOR.** That is $99 separately.
- **NO TRAINING CALL.**
- **NO ONGOING SUPPORT.** 30 days of email-only bug-report response:
  if the box is broken as shipped, we will fix it. If you cannot figure
  out how to use it, we will point you at the guide.
- **NO REFUNDS after the box has been powered on.**

### WHO BUYS THIS
A plant with someone technical on staff (an IT admin, an engineer, a
capable lead) who can follow a setup guide and populate CSVs.

---

## 3. Turnkey Setup (Orin Nano) — $3,500

**We configure it for you remotely. It works when we finish.**

### INCLUDED
- Everything in Tier 2 (Yahboom kit, flashed, Myarra + Koorsus installed)
- **20 hours of REMOTE professional services at $100/hour ($2,000 value):**
  - Remote installation and network configuration
  - Ingestion of your master data (lines, SKUs, BOMs, line rates,
    changeover procedures) from whatever format you have
  - Telegram bot configuration for your operators
  - Remote training for your plant manager and lead operators
  - One follow-up remote session within 30 days
- **The Odoo Connector module (a $99 value), if you use Odoo.**
- **90 days of support** covering installation issues, data errors,
  and software bugs.

### NOT INCLUDED
- **NO ON-SITE VISIT AT THIS PRICE.** On-site installation is available
  and quoted separately. Travel, lodging, and per-diem are billed at cost
  on top of the day rate.
- **NO ONGOING MAINTENANCE AFTER 90 DAYS.** Continued support requires a
  monthly retainer, quoted separately.
- **NO CUSTOM FEATURE DEVELOPMENT.** Changes to the software beyond bug
  fixes are quoted separately.
- **NO HARDWARE UPGRADES AFTER DELIVERY** except at additional cost.
- **NO DATA CLEANUP BEYOND INITIAL INGESTION.** If your master data is
  wrong after setup, correcting it is your project or a new engagement.
- **NO REFUNDS after the remote setup session begins.**

### WHO BUYS THIS
A plant manager who wants a working system, not a project. This is the
recommended tier and the one to lead with in every conversation.

---

## 4. Turnkey Setup (Orin NX) — $5,500

**The premium hardware tier for larger plants and future vision work.**

### INCLUDED
- Everything in Tier 3, but with an **NVIDIA Jetson Orin NX 16GB**
  instead of the Orin Nano 8GB
- The NX module delivers roughly 4× the AI compute and unlocks future
  capabilities (vision inspection, larger local models) that the Nano
  cannot run
- 20 hours of REMOTE professional services as in Tier 3
- 90 days of support as in Tier 3

### NOT INCLUDED
- Everything excluded in Tier 3 applies here as well.
- **NO ON-SITE VISIT AT THIS PRICE.** Quoted separately, travel at cost.
- **NO VISION MODULE.** The NX is capable of running one. It does not
  include one. Vision is a future paid module.
- **NO NX HARDWARE UPGRADE PATH from a Nano tier.** You buy the NX
  outright or you do not.

### WHO BUYS THIS
A larger plant, a multi-line operation, or a client who intends to add
vision or heavier AI workloads within 12 months.

---

## 5. Odoo Connector Module — $99

**A read-only bridge between Odoo and an existing Myarra installation.**

### INCLUDED
- The OPL-1 licensed Odoo module, downloaded from the Odoo Apps Store
- Installation in your Odoo instance
- Configuration documentation

### NOT INCLUDED
- **NO MYARRA INSTALLATION.** The connector is useless without a Myarra
  appliance. If you do not already have one, buy Tier 2, 3, or 4.
- **NO SUPPORT.** Bug reports handled through the App Store review
  channel only.

### WHO BUYS THIS
An existing Myarra customer who runs Odoo and wants automatic work order
sync. Never sold to a customer who does not already have Myarra.

---

## OPTIONAL ADD-ON: On-Site Installation

Available on Tier 3 and Tier 4 only, quoted separately.

**Base price:** day rate plus travel. Travel, lodging, and per-diem billed
at cost. Quoted per engagement based on location and scope.

On-site adds:
- Physical installation and cabling on your floor
- Face-to-face training with your team
- Same-day troubleshooting of any environmental issues (network, power,
  rack mounting)

On-site is not required. Remote setup is sufficient for most plants. It
exists for customers who prefer a physical presence or whose environment
requires it.

---

## THE LADDER, AT A GLANCE

| Tier | Price | Flashed | Setup | Training | Support | Odoo Connector |
|---|---|---|---|---|---|---|
| 1. Hardware Only | $1,200 | ✗ | ✗ | ✗ | ✗ | ✗ |
| 2. Hardware + Software | $1,500 | ✓ | ✗ | ✗ | 30d email | ✗ |
| 3. Turnkey Orin | $3,500 | ✓ | Remote | Remote | 90 days | ✓ |
| 4. Turnkey NX | $5,500 | ✓ | Remote | Remote | 90 days | ✓ |
| 5. Odoo Connector | $99 | n/a | n/a | n/a | ✗ | ✓ |

---

## STANDING NOTES

- **Voice vs. Text:** Marketing leads with voice ("Let them talk"). Text
  is acknowledged in the second sentence. The bot accepts typed Telegram
  messages as easily as voice, which matters in loud factory floors.
- **Hardware sourcing:** Yahboom kit confirmed on Amazon at ~$670, case
  (Waveshare aluminum, ~$22) confirmed. Official NVIDIA dev kits are
  currently out of stock or priced above $600 — the Yahboom kit is the
  only sane sourcing path.
- **No SD card slot** on the SUB board. NVMe only. Flashing uses
  Yahboom's factory image and super boot procedure.
- **On-site is an upsell, never a default.** Remote is the operating
  assumption. Travel is always billed separately.

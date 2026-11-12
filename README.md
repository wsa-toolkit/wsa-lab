# wsa-lab

> Hermetic wireless access point generator for security assessment.
> Companion to WSA and any wireless assessment tool that needs a
> safe, reproducible target.

wsa-lab creates self-contained wireless access points for authorized
security training, testing, and lab work. One command, one menu, and
every wireless protocol from 1997 to 2018 is available as a working,
reproducible target — with DHCP, NAT, and internet sharing managed
automatically.

## Why this tool

Security students need wireless targets they can test legally. The
alternatives are either:

- **Too complex** — hand-edit hostapd configs, manage dnsmasq, set up
  iptables, reverse it all on shutdown — for each protocol
- **Too aggressive** — rogue-AP tools built for live engagements, not
  training environments

wsa-lab is the **"create a target"** side of the wireless training
equation. A student picks a protocol from a menu and gets a working AP
in about ten seconds. No RF leaves the room. No neighbors involved.
Nothing to violate.

## Who this is for

- **Students and trainees** — you need legal wireless targets to
  practise on. wsa-lab gives you one in ten seconds. No neighbors,
  no permission slips, no RF leaving the room.
- **Instructors** — you need a reproducible classroom setup. The same
  mode produces the same AP on every machine, every time.
- **Self-learners** — you're studying for a certification (OSCP, CEH,
  CWNA) and need a lab you can reset. Ctrl+C, restart, fresh AP.
- **Researchers** — you need a controlled test bed for protocol-level
  experiments. Every mode is a documented, honest configuration.

## Designed to fit any wireless assessment tool

wsa-lab is an **AP generator**, not an assessment tool. It produces
targets; you point your assessment tool of choice at them.

The primary companion is the [WSA assessment framework](https://github.com/wsa-toolkit/wsa) —
a wireless security assessment conductor that drives aircrack-ng,
hostapd-mana, hashcat, and john, and produces NIST SP 800-53 remediation
reports. The WSA workflow maps directly to wsa-lab's SSIDs, credentials,
and protocols.

But wsa-lab is not tied to WSA. Any offensive tool that needs a
hermetic, safe, AP-mode target works:

- **WSA** — assessment conductor with NIST-mapped reporting
- **aircrack-ng** — handshake capture, WEP IV collection
- **hostapd-mana** — rogue AP testing (against wsa-lab's APs)
- **hashcat / john** — offline recovery against captured material
- **Custom scripts** — anything that needs a reproducible AP to test against

The goal is the same in every case: **offensive operations against an
AP, in a controlled environment, without touching anyone else's
network.** wsa-lab gives you that AP in ten seconds.

## What it does

    AP SECURITY PROFILE

        1  1997  Open                                          no auth
        2  1997  Open (MAC Filter)                             allowlist only
        3  1997  WEP                             legacy        RC4, broken
        4  2003  WPA-Personal (TKIP)             legacy        PSK, deprecated
        5  2003  WPA-Enterprise (TKIP)           legacy        802.1X, deprecated
        6  2004  WPA2-Personal (CCMP)                          PSK, offline attack
        7  2004  WPA2-Enterprise (CCMP)                        802.1X
        8  2004  WPA/WPA2-Personal               mixte         TKIP+CCMP
        9  2017  OWE (Enhanced Open)                           RFC 8110
       10  2018  WPA3-Personal (SAE)                           SAE, online-only guessing
       11  2018  WPA3-Enterprise (EAP-SHA256)                  PMF required
       12  2018  WPA2/WPA3-Personal              mixte         PSK+SAE, Dragonblood surface
       13  2018  WPA2/WPA3-Enterprise            mixte         EAP+EAP-SHA256
       14  ----  Custom Personal                 custom        user config
       15  ----  Custom Enterprise               custom        user config

Every mode is:

- **Pre-configured** — sensible defaults, no editing required
- **Verified** — tested end-to-end with real clients
- **Reproducible** — same commands produce the same AP, every time
- **Isolated** — no external network impact, no RF leakage

## Verified modes

Tested end-to-end (AP, client auth, DHCP, internet) on Kali 2026.x with:

- **Tested in:** VirtualBox VM (internal wlan0) and on a physical
  TP-Link Archer T2U Nano (RTL8811AU, USB 2357:011e)
- **Clients:** Galaxy A02 (Android 11), Galaxy Tab S9+ (Android 13)

| #  | Protocol                     | Status        |
|----|------------------------------|---------------|
| 1  | Open                         | verified      |
| 2  | Open (MAC Filter)            | verified      |
| 3  | WEP                          | verified      |
| 4  | WPA-Personal (TKIP)          | verified      |
| 5  | WPA-Enterprise (TKIP)        | verified      |
| 6  | WPA2-Personal (CCMP)         | verified      |
| 7  | WPA2-Enterprise (CCMP)       | verified      |
| 8  | WPA/WPA2-Personal (mixte)    | verified      |
| 9  | OWE                          | partial       |
| 10 | WPA3-Personal (SAE)          | verified      |
| 11 | WPA3-Enterprise (EAP-SHA256) | verified      |
| 12 | WPA2/WPA3-Personal (mixte)   | verified      |
| 13 | WPA2/WPA3-Enterprise (mixte) | verified      |
| 14 | Custom Personal              | user template |
| 15 | Custom Enterprise            | user template |

**12 of 15 modes fully verified** through the full chain (AP, auth,
DHCP, internet). Mode 9 (OWE) partially works — see Known issues.
Modes 14–15 are templates that require user configuration.

## Requirements

### Software

- **Root (sudo)** — wireless interface manipulation requires CAP_NET_ADMIN
- **Kali Linux** (or any Debian-derived system)
- **Packages:** hostapd, dnsmasq, iw, iptables

For specific modes:

- **WEP (mode 3):** hostapd must be compiled with CONFIG_WEP=y
  (stock Kali hostapd 2.10+ does not include it)
- **Enterprise (modes 5, 7, 11, 13, 15):** freeradius and freeradius-utils
- **WPA3 (modes 10, 11, 12, 13):** hostapd 2.9+ with SAE support
  (stock Kali hostapd 2.11 is fine)

### Hardware

Any AP-mode-capable wireless adapter. No specific hardware required.
Tested reference: TP-Link Archer T2U Nano (RTL8811AU) and VirtualBox
internal wlan0.

**For WPA3-Enterprise and full enterprise flows**, the adapter must
support PMF (802.11w) in AP mode. Most do; some cheap Realtek chips do
not.

**For OWE**, the adapter must support the Diffie-Hellman exchange in
AP mode. Confirmed non-working: rtl8821au (T2U Nano). See Known issues.

## Quick start

### Setup

    git clone https://github.com/wsa-toolkit/wsa-lab.git
    cd wsa-lab
    sudo python3 wsa-lab.py

No separate setup script required. First run prompts for the AP
interface and the internet-sharing interface; both are saved to
`~/.config/wsa-lab/settings.json`.

### Launch

    sudo python3 wsa-lab.py

**First run:** prompts for AP and internet interfaces, saves them to
`~/.config/wsa-lab/settings.json`.

**Every subsequent run:** skips prompt, goes straight to menu.

### Example — WEP lab in 15 seconds

    SELECT OPTION: 1          (Initiate AP)
    SELECT OPTION: 3          (WEP)
    SELECT OPTION: 2          (Run AP)

Client connects to SSID `00_wep` with password `12345`.

Watch the AP terminal:

    HOSTAPD
       wlan0: interface state UNINITIALIZED->ENABLED
       wlan0: AP-ENABLED
       wlan0: STA xx:xx:xx:xx:xx:xx IEEE 802.11: associated
       wlan0: AP-STA-CONNECTED xx:xx:xx:xx:xx:xx
       dnsmasq-dhcp: DHCPACK(wlan0) 192.168.99.66 ... Galaxy-A02
       dnsmasq: query[A] www.google.com from 192.168.99.66

Client is on the network, has DHCP, has internet. Run WSA or any
assessment tool against it from a separate monitor-mode adapter.

## Menu reference

### Main menu

| Option | Purpose |
|--------|---------|
| 1 | Initiate AP — pick protocol, run |
| 2 | Adapter settings — change AP or internet interface |
| 3 | Themes and layout — 20 palettes, 3 slots |

### Per-mode submenu

| Option | Purpose |
|--------|---------|
| 1 | Edit configuration — opens hostapd config in editor |
| 2 | Edit users/passwords — Enterprise modes only |
| 3 | Run AP |

Every edit is saved to `~/.config/wsa-lab/MODE.conf` and reused next
run. Delete the file to return to the template default.

### Default credentials (per mode)

| Mode | SSID                     | Credentials                           |
|------|--------------------------|---------------------------------------|
| 1    | wsa_open_unrestricted    | none                                  |
| 2    | wsa_open_macfilter       | MAC allowlist                         |
| 3    | 00_wep                   | key 12345 (ASCII) or 3132333435 (hex) |
| 4    | wpa1                     | LabPassword123                        |
| 5    | wsa_wpa_enterprise       | user1 / 12345678                      |
| 6    | capture_wpa2_personal    | LabPassword123                        |
| 7    | wsa_wpa2_enterprise      | user1 / 12345678                      |
| 8    | wpa21-2                  | Password123456                        |
| 9    | owe                      | none (Enhanced Open)                  |
| 10   | Lab_WPA3_2.4GHz          | password123                           |
| 11   | wsa_wpa3_enterprise      | user1 / 12345678                      |
| 12   | wpa32                    | Password123456                        |
| 13   | wsa_wpa3_wpa2_enterprise | user1 / 12345678                      |
| 14   | custom-personal          | changeme                              |
| 15   | custom-enterprise        | user1 / 12345678                      |

## Enterprise users

Enterprise modes authenticate via FreeRADIUS. Users are stored in
`/etc/freeradius/3.0/mods-config/files/authorize` inside a
wsa-lab-managed block:

    # BEGIN WSA-LAB MANAGED USERS
    user1   Cleartext-Password := "12345678"
    user2   Cleartext-Password := "anotherpassword"
    # END WSA-LAB MANAGED USERS

Manage via menu (from any Enterprise mode submenu):

    OPTIONS
       1  Edit configuration
       2  Edit users/passwords
       3  Run AP

Interactive operations:

- **Add a user** — prompts username + password, validates format
- **Change a password** — for any managed user
- **Remove a user** — with confirmation

FreeRADIUS auto-restarts after any change. Pre-existing users (like
FreeRADIUS default `bob`) are preserved untouched — only wsa-lab's
managed block is rewritten.

## MAC filter (mode 2)

Open network with MAC allowlist. Manage interactively:

    MAC FILTER SETUP

       File:    ~/.config/wsa-lab/accept_macs.txt
       Entries: 1

        1  0C:02:BD:51:81:06

       1  Start AP with current allowlist
       2  Add a MAC
       3  Remove a MAC
       4  Clear all entries

- **Add a MAC** — validates format AA:BB:CC:DD:EE:FF or with dashes
- **Denied MACs** — connect to SSID, association rejected by AP
- **Allowed MACs** — full connection with DHCP

## Themes

Three configurable colour slots, 20 palettes each:

    THEMES AND LAYOUT
       text:   matrix
       title:  matrix
       layout: follow text colour

Palettes: amber, green, blue, dark_blue, light_blue, military,
interpol, nasa, matrix, magenta, monochrome, airodump, neo,
military_red, orange, yellow, forest, olive, steel, crimson.

Saved to `settings.json`, persists between sessions.

## Command-line options

For scripting and CI:

    sudo python3 wsa-lab.py --help              # full help
    sudo python3 wsa-lab.py --list-modes        # print all modes
    sudo python3 wsa-lab.py --mode N --no-edit  # run mode N directly
    sudo python3 wsa-lab.py --reconfigure       # re-prompt interfaces
    sudo python3 wsa-lab.py --reset             # clear all settings
    sudo python3 wsa-lab.py --no-share          # isolated lab (no NAT)

## Clean shutdown

Ctrl+C at any point — during menu, during config edit, during AP
running — exits cleanly:

- Kills hostapd, dnsmasq, freeradius
- Flushes iptables (if internet sharing was active)
- Resets ip_forward
- Removes temp files
- Returns terminal to normal

No orphan processes, no leftover rules. Verified by crash test: 5
consecutive kill -9 / restart cycles pass.

## Known issues

### OWE client authentication fails on rtl8821au

Symptom: AP broadcasts `owe` SSID with correct beacon (AKM=18, PMF
required). Client sees "Enhanced Open", tries to connect, fails
DHCP/auth silently.

Cause: Out-of-tree rtl8821au driver (used by TP-Link Archer T2U Nano,
USB 2357:011e) advertises OWE support in nl80211 capabilities but
cannot complete the Diffie-Hellman exchange in AP mode.

Workaround: Use an Atheros AR9271 (Alfa AWUS036NHA, TP-Link TL-WN722N
v1) or MediaTek MT7612U (Alfa AWUS036ACM) adapter for OWE.

### GCMP not supported on rtl8821au

Symptom: WPA3 configs with `rsn_pairwise=GCMP` fail at beacon. Error:
`Failed to set beacon parameters`.

Cause: rtl8821au driver supports WEP40, WEP104, TKIP, CCMP-128, CMAC
only. GCMP-128 and GCMP-256 are not advertised.

Impact: WPA3 templates use CCMP (valid for WPA3, preferred on this
adapter). Clients requiring GCMP (WPA3-Enterprise 192-bit/Suite B)
will not connect.

### airodump-ng shows WPA3-Enterprise as WPA2

Symptom: Scanning a WPA3-Enterprise AP (mode 11) from airodump-ng, WSA
recon, or any tool built on the aircrack-ng suite shows the target as
WPA2 CCMP with blank AUTH column instead of WPA3-Enterprise.

Cause: airodump-ng's AKM classifier has no label for AKM=5
(WPA-EAP-SHA256). Unknown AKMs leave the AUTH column blank and default
ENC to WPA2.

Verification: The beacon is correct. Confirmed via tcpdump/tshark
showing AKM=5 in the RSN IE. Android clients show "WPA3-Enterprise"
in Wi-Fi settings. Clients authenticate successfully.

This is a scanner display limitation, not a wsa-lab issue. A future WSA
release will add AKM=5 to its classifier.

### WPA3 requires capable client hardware

Symptom: WPA3 AP works, but some clients associate-then-drop or show
authentication failed.

Cause: Client hardware/firmware may not support WPA3-SAE or
WPA3-Enterprise with EAP-SHA256, even on modern OS versions.

Verified working clients: Galaxy A02 (Android 11) for WPA3-SAE and
WPA3-Enterprise.

## Menu philosophy

The menu displays all 15 protocols, including mixed/transition modes
(8, 12, 13) and OWE (9). Design choices:

- **No protocol is hidden.** Every mode is visible and available.
  Students see the full taxonomy even if they don't test every mode.
- **Mixed modes labeled mixte.** These APs accept multiple AKMs. Each
  client negotiates exactly one — the mixed nature lives on the AP
  side, not the client side. Mixed mode is the attack surface for
  KRACK, Dragonblood, and FragAttacks — useful for teaching why pure
  protocols are preferred in production.
- **Status flags (legacy, mixte, custom)** are teaching aids, not
  judgments. Legacy modes are still useful as targets.
- **Mode numbers are permanent.** Future modes append at 16+, never
  renumber.

## Related

- **WSA** — Wireless Security Assessment Framework — the assessment
  companion to wsa-lab. Packaged for Kali; in submission review.
  https://github.com/wsa-toolkit/wsa

## Legal notice

wsa-lab is intended for **authorized security assessments and training
only**.

Use of this tool against networks you do not own, or have not been
given explicit written authorization to test, is illegal in most
jurisdictions. The authors assume no liability for misuse.

Before using wsa-lab:

- Obtain written authorization from the network owner (if assessing a
  real network)
- For training, use wsa-lab's own isolated AP — no external RF, no
  neighbors involved
- Document the scope (ESSIDs, BSSIDs, time windows)
- Comply with all applicable laws (CFAA in the US, Computer Misuse Act
  in the UK, similar statutes worldwide)

wsa-lab is designed for authorized penetration testing engagements,
security training in controlled lab environments, and internal
wireless security audits on networks you own.

wsa-lab is not designed for unauthorized access to wireless networks,
war driving, or any activity that violates local or international law.

## License

GNU General Public License v2.0 or later. See `LICENSE`.

## Contributing

See `CONTRIBUTING.md`. Issues and pull requests welcome.

## Files in this repository

- `wsa-lab.py` — the tool (single file, ~750 lines)
- `README.md` — this file
- `LICENSE` — GNU General Public License v2.0 or later
- `CONTRIBUTING.md` — contribution guidelines

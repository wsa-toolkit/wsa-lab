# wsa-lab

**A one-command wireless practice range for learning security assessment.**
Companion to [WSA](https://github.com/wsa-toolkit/wsa), and usable with any wireless assessment tool that needs a safe, reproducible target.

wsa-lab brings up a self-contained lab access point for authorized security training, testing and teaching. Pick a protocol from a menu and get a working AP with DHCP, RADIUS (for Enterprise modes) and optional internet sharing, configured and cleaned up automatically. The menu covers wireless security from 1997 to 2018, from Open and WEP to WPA3-Enterprise.

## Why this tool

Students need wireless targets they are allowed to test. The alternatives are:

- **Too complex:** hand-editing hostapd configs, dnsmasq and iptables for each protocol, then undoing it all afterwards.
- **Too risky:** practising on a home or neighbour's network.

wsa-lab is the "create a target" side of wireless training. A student picks a protocol and gets a working lab AP in about ten seconds, so there is no reason to practise on anyone else's network.

## Who this is for

- **Students and trainees:** a legal target to practise on, on your own hardware.
- **Instructors:** the same mode produces the same AP on every machine, so a class starts from the same setup.
- **Self-learners:** studying for a certification (OSCP, CEH, CWNA) and want a lab you can reset. Ctrl+C, restart, fresh AP.
- **Researchers and defenders:** a controlled, documented configuration for protocol experiments and detection work.

## Works with any assessment tool

wsa-lab is an AP generator, not an assessment tool. It produces targets; you point your own tools at them.

The primary companion is the [WSA assessment framework](https://github.com/wsa-toolkit/wsa), which guides a human-controlled assessment (capture, analyse, report) and produces NIST SP 800-53 mapped reports. WSA's workflow maps directly to wsa-lab's SSIDs, credentials and protocols.

It also works with other tools that need a controlled AP to test against, for example:

- `aircrack-ng`: handshake capture and WEP IV collection
- `hostapd-mana`: rogue-AP testing against the lab APs
- `hashcat` / `john`: offline recovery on material captured from the lab
- your own scripts, detection tools and classroom exercises

## Safety and scope

wsa-lab transmits **real radio signals** when it runs on a physical adapter. To keep it a lab:

- Use it **only on adapters and networks you own**, and never against anyone else's network.
- Neighbouring devices can see the lab SSID. Choose a unique lab SSID, keep transmit power low where your adapter allows, and follow your local radio regulations.
- Use `--no-share` when the lab does not need internet access, so the lab network stays isolated.
- Default credentials in this README are for lab use only. Change them if the AP is reachable by anyone else.
- Run it in a VM or on a dedicated test machine where possible.

See the Legal notice at the end of this file.

## What it does

```
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
```

(`mixte` in the menu means mixed or transition mode.)

Every mode is:

- **Pre-configured:** sensible defaults, no editing required.
- **Reproducible:** the same commands produce the same AP every time.
- **Contained:** its own subnet (192.168.99.0/24); internet sharing is optional.
- **Cleaned up:** Ctrl+C stops all services and restores the system state.

## Verified modes

Tested end-to-end (AP, client authentication, DHCP, internet) on Kali 2026.x.

- **Environments:** VirtualBox VM (internal wlan0) and a physical TP-Link Archer T2U Nano (RTL8811AU, USB 2357:011e).
- **Clients:** Galaxy A02 (Android 11), Galaxy Tab S9+ (Android 13).

| #  | Protocol                     | Status        |
|----|------------------------------|---------------|
| 1  | Open                         | verified      |
| 2  | Open (MAC Filter)            | verified      |
| 3  | WEP                          | verified      |
| 4  | WPA-Personal (TKIP)          | verified      |
| 5  | WPA-Enterprise (TKIP)        | verified      |
| 6  | WPA2-Personal (CCMP)         | verified      |
| 7  | WPA2-Enterprise (CCMP)       | verified      |
| 8  | WPA/WPA2-Personal (mixed)    | verified      |
| 9  | OWE                          | partial       |
| 10 | WPA3-Personal (SAE)          | verified      |
| 11 | WPA3-Enterprise (EAP-SHA256) | verified      |
| 12 | WPA2/WPA3-Personal (mixed)   | verified      |
| 13 | WPA2/WPA3-Enterprise (mixed) | verified      |
| 14 | Custom Personal              | user template |
| 15 | Custom Enterprise            | user template |

**12 of 15 entries are fully verified** through the full chain. Mode 9 (OWE) partially works (see Known issues). Modes 14 and 15 are templates that need user configuration.

## Requirements

### Software

- Root (`sudo`), because wireless interface changes need `CAP_NET_ADMIN`
- Kali Linux, or any Debian-derived system
- Packages: `hostapd`, `dnsmasq`, `iw`, `iptables`

For specific modes:

- **WEP (mode 3):** hostapd must be compiled with `CONFIG_WEP=y` (stock Kali hostapd 2.10+ does not include it)
- **Enterprise (modes 5, 7, 11, 13, 15):** `freeradius` and `freeradius-utils`
- **WPA3 (modes 10 to 13):** hostapd 2.9+ with SAE support (stock Kali hostapd 2.11 is fine)

### Hardware

Any adapter that supports AP mode. Tested reference: TP-Link Archer T2U Nano (RTL8811AU) and VirtualBox internal wlan0.

- WPA3-Enterprise and full enterprise flows need PMF (802.11w) in AP mode. Most adapters have it, but some cheap Realtek chips do not.
- OWE needs the Diffie-Hellman exchange in AP mode. Confirmed non-working: rtl8821au (T2U Nano). See Known issues.

## Quick start

```bash
git clone https://github.com/wsa-toolkit/wsa-lab.git
cd wsa-lab
sudo python3 wsa-lab.py
```

No separate setup script is needed. On first run it asks for the AP interface and the internet-sharing interface and saves them to `~/.config/wsa-lab/settings.json`. Later runs go straight to the menu.

### Example: a WEP lab in about 15 seconds

```
SELECT OPTION: 1          (Initiate AP)
SELECT OPTION: 3          (WEP)
SELECT OPTION: 2          (Run AP)
```

A client connects to SSID `00_wep` with password `12345`. Watch the AP terminal:

```
HOSTAPD
   wlan0: interface state UNINITIALIZED->ENABLED
   wlan0: AP-ENABLED
   wlan0: STA xx:xx:xx:xx:xx:xx IEEE 802.11: associated
   wlan0: AP-STA-CONNECTED xx:xx:xx:xx:xx:xx
   dnsmasq-dhcp: DHCPACK(wlan0) 192.168.99.66 ... Galaxy-A02
```

The client is on the lab network with DHCP. Run WSA or any assessment tool against it from a separate adapter.

## Menu reference

### Main menu

| Option | Purpose                                               |
|--------|-------------------------------------------------------|
| 1      | Initiate AP: pick a protocol and run                  |
| 2      | Adapter settings: change the AP or internet interface |
| 3      | Themes and layout: 20 palettes, 3 slots               |

### Per-mode submenu

| Option | Purpose                                                     |
|--------|-------------------------------------------------------------|
| 1      | Edit configuration: opens the hostapd config in your editor |
| 2      | Edit users/passwords (Enterprise modes only)                |
| 3      | Run AP                                                      |

Edits are saved to `~/.config/wsa-lab/MODE.conf` and reused next run. Delete the file to return to the template default.

## Default lab credentials

For lab use only. Change them if anyone else can reach the AP.

| Mode | SSID                            | Credentials                               |
|------|---------------------------------|-------------------------------------------|
| 1    | wsa_open_unrestricted           | none                                      |
| 2    | wsa_open_macfilter              | MAC allowlist                             |
| 3    | 00_wep                          | key `12345` (ASCII) or `3132333435` (hex) |
| 4    | wpa1                            | LabPassword123                            |
| 5    | wsa_wpa_enterprise              | user1 / 12345678                          |
| 6    | capture_wpa2_personal           | LabPassword123                            | 
| 7    | wsa_wpa2_enterprise             | user1 / 12345678                          |
| 8    | wpa21-2                         | Password123456                            |
| 9    | owe                             | none (Enhanced Open)                      |
| 10   | Lab_WPA3_2.4GHz                 | password123                               |
| 11   | wsa_wpa3_enterprise             | user1 / 12345678                          |
| 12   | wpa32                           | Password123456                            |
| 13   | wsa_wpa3_wpa2_enterprise        | user1 / 12345678                          |
| 14   | custom-personal                 | changeme                                  |
| 15   | custom-enterprise               | user1 / 12345678                          |

### Enterprise users

Enterprise modes authenticate through FreeRADIUS. Users are stored in `/etc/freeradius/3.0/mods-config/files/authorize` inside a block managed by wsa-lab:

```
# BEGIN WSA-LAB MANAGED USERS
user1   Cleartext-Password := "12345678"
user2   Cleartext-Password := "anotherpassword"
# END WSA-LAB MANAGED USERS
```

From any Enterprise submenu you can add a user, change a password or remove a user (with confirmation). FreeRADIUS restarts automatically after a change. Pre-existing users (such as the FreeRADIUS default `bob`) are left untouched.

### MAC filter (mode 2)

An open network with a MAC allowlist, managed interactively: add a MAC (`AA:BB:CC:DD:EE:FF` or with dashes), remove one, or clear all. Denied MACs are rejected at association; allowed MACs get a full connection with DHCP.

## Themes

Three colour slots with 20 palettes each (amber, green, blue, dark_blue, light_blue, military, interpol, nasa, matrix, magenta, monochrome, airodump, neo, military_red, orange, yellow, forest, olive, steel, crimson). Saved to `settings.json`.

## Command-line options

For scripting and CI:

```bash
sudo python3 wsa-lab.py --help              # full help
sudo python3 wsa-lab.py --list-modes        # print all modes
sudo python3 wsa-lab.py --mode N --no-edit  # run mode N directly
sudo python3 wsa-lab.py --reconfigure       # re-prompt interfaces
sudo python3 wsa-lab.py --reset             # clear all settings
sudo python3 wsa-lab.py --no-share          # isolated lab (no NAT)
```

## Clean shutdown

Ctrl+C at any point (menu, config edit or running AP) exits cleanly:

- stops hostapd, dnsmasq and FreeRADIUS
- flushes the iptables rules wsa-lab added (when internet sharing was active)
- resets `ip_forward`
- removes temporary files

Checked by a crash test: 5 consecutive `kill -9` and restart cycles pass.

## Known issues

### OWE client authentication fails on rtl8821au

**Symptom:** the AP broadcasts the `owe` SSID with a correct beacon (AKM=18, PMF required). The client sees "Enhanced Open", tries to connect, and fails silently.

**Cause:** the out-of-tree rtl8821au driver (used by the TP-Link Archer T2U Nano) advertises OWE support in nl80211 but cannot complete the Diffie-Hellman exchange in AP mode.

**Workaround:** use an Atheros AR9271 (Alfa AWUS036NHA, TP-Link TL-WN722N v1) or a MediaTek MT7612U (Alfa AWUS036ACM) adapter.

### GCMP not supported on rtl8821au

**Symptom:** WPA3 configs with `rsn_pairwise=GCMP` fail at beacon with `Failed to set beacon parameters`.

**Cause:** the driver supports WEP40, WEP104, TKIP, CCMP-128 and CMAC only.

**Impact:** WPA3 templates use CCMP, which is valid for WPA3. Clients that require GCMP (WPA3-Enterprise 192-bit / Suite B) will not connect.

### airodump-ng shows WPA3-Enterprise as WPA2

**Symptom:** scanning a mode 11 AP with airodump-ng or any tool built on the aircrack-ng suite shows WPA2 CCMP with a blank AUTH column.

**Cause:** airodump-ng has no label for AKM=5 (WPA-EAP-SHA256).

**Verification:** the beacon is correct. tcpdump/tshark shows AKM=5 in the RSN IE, Android shows "WPA3-Enterprise", and clients authenticate. This is a scanner display limitation, not a wsa-lab issue. A future WSA release will add AKM=5 to its classifier.

### WPA3 needs capable client hardware

Some clients associate and then drop, or report authentication failed, because their hardware or firmware does not support WPA3-SAE or WPA3-Enterprise with EAP-SHA256. Verified working client: Galaxy A02 (Android 11).

## Menu philosophy

- **No protocol is hidden.** Students see the full taxonomy even if they never test every mode.
- **Mixed modes are labelled `mixte`.** These APs accept multiple AKMs, and each client negotiates one. Mixed and transition modes are where KRACK, Dragonblood and FragAttacks matter, which makes them useful for teaching why pure protocols are preferred in production.
- **Status flags (`legacy`, `mixte`, `custom`) are teaching aids**, not judgments. Legacy modes are still useful as targets.
- **Mode numbers are permanent.** New modes append at 16 and up and are never renumbered.

## Roadmap (planned, not yet implemented)

- A virtual-radio backend (`mac80211_hwsim`) so the lab runs with no adapter at all
- Automated tests that start each profile and verify it came up correctly
- More profiles: OWE Transition Mode, SAE-PK, WPS, 802.11r, WPA3-Enterprise 192-bit
- A rogue-AP / evil-twin detection scenario for defenders
- Safer defaults: lab SSID prefix, transmit-power and channel controls
- A short lesson for each profile

Suggestions and pull requests are welcome in the issue tracker.

## Related

- [WSA](https://github.com/wsa-toolkit/wsa): the assessment companion. A `.deb` package is available in its releases.

## Legal notice

wsa-lab is intended for authorized security assessments and training only.

Using any assessment tool against networks you do not own, or have not been given explicit written authorization to test, is illegal in most jurisdictions. The authors assume no liability for misuse.

Before using wsa-lab:

- For training, use wsa-lab's own lab AP on hardware you own.
- If you assess a real network, obtain written authorization from its owner and document the scope (ESSIDs, BSSIDs, time windows).
- Comply with all applicable laws (CFAA in the US, the Computer Misuse Act in the UK, and similar statutes elsewhere) and with local radio regulations.

wsa-lab is not designed for unauthorized access to wireless networks, war driving, or any activity that violates local or international law.

## License

GNU General Public License v2.0 or later. See `LICENSE`.

## Contributing

See `CONTRIBUTING.md`. Issues and pull requests are welcome.

## Files in this repository

- `wsa-lab.py`: the tool (single file, about 750 lines)
- `README.md`: this file
- `LICENSE`: GNU General Public License v2.0 or later
- `CONTRIBUTING.md`: contribution guidelines

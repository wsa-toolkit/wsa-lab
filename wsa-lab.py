#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Astite Abdelkader <abdelkader.astite@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

"""wsa-lab - hermetic wireless AP generator for WSA assessment training.

Usage:
  sudo python3 wsa-lab.py [OPTIONS]

Interactive: launches WSA Manual Conductor-style menu.

Options:
  --mode N          run mode N directly (no menu) - for scripting/CI
  --no-edit         skip config editing, use template directly
  --no-share        skip internet sharing (isolated lab)
  --reconfigure     force re-prompt for interface selection
  --reset           delete saved settings and all mode overrides
  --list-modes      print all modes and exit
  -h, --help        show this help

Storage:
  ~/.config/wsa-lab/settings.json       interfaces + 3 theme slots
  ~/.config/wsa-lab/<mode>.conf         per-mode overrides
  ~/.config/wsa-lab/accept_macs.txt     MAC allowlist (mode 2)

Requirements:
  Root (sudo), hostapd, dnsmasq, iw, iptables.
  For mode 3 (WEP):               /usr/local/sbin/hostapd-wep
  For Enterprise modes
    (5, 7, 11, 13, 15):           freeradius, freeradius-utils

See wsa-lab-setup.sh for the one-shot installer.
"""

import atexit
import json
import os
import pwd
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time


# --------------------------------------------------------------- paths
def _real_user():
    su = os.environ.get("SUDO_USER")
    if su:
        try:
            pw = pwd.getpwnam(su)
            return pw.pw_name, pw.pw_dir, pw.pw_uid, pw.pw_gid
        except KeyError:
            pass
    pw = pwd.getpwuid(os.getuid())
    return pw.pw_name, pw.pw_dir, pw.pw_uid, pw.pw_gid


USERNAME, HOME, UID, GID = _real_user()
CONFIG_DIR    = os.path.join(HOME, ".config", "wsa-lab")
LEGACY_CONFIG = os.path.join(HOME, ".config", "ap-generator")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
FREERADIUS_AUTHORIZE = "/etc/freeradius/3.0/mods-config/files/authorize"
FREERADIUS_BLOCK_BEGIN = "# BEGIN WSA-LAB MANAGED USERS"
FREERADIUS_BLOCK_END   = "# END WSA-LAB MANAGED USERS"

if os.path.isdir(LEGACY_CONFIG) and not os.path.isdir(CONFIG_DIR):
    try:
        shutil.copytree(LEGACY_CONFIG, CONFIG_DIR)
        for root, dirs, files in os.walk(CONFIG_DIR):
            for entry in dirs + files:
                try:
                    os.chown(os.path.join(root, entry), UID, GID)
                except OSError:
                    pass
        os.chown(CONFIG_DIR, UID, GID)
    except OSError:
        pass


# ---------------------------------------------------------------- temp
TMP_DIR = tempfile.mkdtemp(prefix=f"wsa-lab-{os.getpid()}-")
TMP_FILES = []
STARTED = set()
SHARING_ACTIVE = False


def _cleanup():
    for svc in list(STARTED):
        subprocess.run(f"pkill -9 {svc}", shell=True)
        STARTED.discard(svc)
    subprocess.run("pkill -9 hostapd 2>/dev/null", shell=True)
    subprocess.run("pkill -9 dnsmasq 2>/dev/null", shell=True)
    try:
        reset_network()
    except Exception:
        pass
    for path in TMP_FILES:
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        os.rmdir(TMP_DIR)
    except OSError:
        pass


atexit.register(_cleanup)


# ------------------------------------------------------------- palette
PALETTES = {
    "amber":        (255, 191, 0),
    "green":        (0,   255, 0),
    "blue":         (0,   120, 255),
    "dark_blue":    (0,   0,   160),
    "light_blue":   (135, 206, 235),
    "military":     (75,  83,  32),
    "interpol":     (0,   102, 204),
    "nasa":         (30,  90,  180),
    "matrix":       (0,   255, 65),
    "magenta":      (255, 0,   255),
    "monochrome":   (220, 220, 220),
    "airodump":     (100, 255, 100),
    "neo":          (0,   230, 0),
    "military_red": (200, 50,  50),
    "orange":       (255, 165, 0),
    "yellow":       (240, 240, 80),
    "forest":       (34,  139, 34),
    "olive":        (128, 128, 0),
    "steel":        (70,  130, 180),
    "crimson":      (220, 20,  60),
}

PALETTE_ORDER = list(PALETTES.keys())


def _fg(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m"


def _swatch(rgb):
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m" + ("█" * 10) + "\033[0m"


SEM_RED    = "\033[38;2;255;80;80m"
SEM_YELLOW = "\033[38;2;255;220;80m"
SEM_GREEN  = "\033[38;2;100;255;100m"
RESET      = "\033[0m"

BODY = TITLE = BORDER = VAL = DIM = ""
ERR = WARN = OK = ""


def refresh_colors(settings):
    global BODY, TITLE, BORDER, VAL, DIM, ERR, WARN, OK
    text_name   = settings.get("theme_text",   "matrix")
    title_name  = settings.get("theme_title",  "matrix")
    layout_name = settings.get("theme_layout", "follow")

    body_rgb   = PALETTES.get(text_name,  PALETTES["matrix"])
    title_rgb  = PALETTES.get(title_name, PALETTES["matrix"])
    layout_rgb = body_rgb if layout_name == "follow" else PALETTES.get(layout_name, body_rgb)

    BODY   = _fg(body_rgb)
    TITLE  = _fg(title_rgb)
    BORDER = _fg(layout_rgb)
    VAL    = _fg(body_rgb)
    DIM    = _fg(body_rgb)

    ERR  = SEM_RED
    WARN = SEM_YELLOW
    OK   = SEM_GREEN


# ------------------------------------------------------- mode layout
# (num, year, name, posture, note)
# Display order is chronological. Mode numbers are permanent.
# Future modes must APPEND at the end - never renumber.
MODE_LAYOUT = [
    ("1",  "1997", "Open",                        "",           "no auth"),
    ("2",  "1997", "Open (MAC Filter)",           "",           "allowlist only"),
    ("3",  "1997", "WEP",                         "legacy",     "RC4, broken"),
    ("4",  "2003", "WPA-Personal (TKIP)",         "legacy",     "PSK, deprecated"),
    ("5",  "2003", "WPA-Enterprise (TKIP)",       "legacy",     "802.1X, deprecated"),
    ("6",  "2004", "WPA2-Personal (CCMP)",        "",           "PSK, offline attack"),
    ("7",  "2004", "WPA2-Enterprise (CCMP)",      "",           "802.1X"),
    ("8",  "2004", "WPA/WPA2-Personal",           "mixte", "TKIP+CCMP"),
    ("9",  "2017", "OWE (Enhanced Open)",         "",           "RFC 8110"),
    ("10", "2018", "WPA3-Personal (SAE)",         "",           "SAE, online-only guessing"),
    ("11", "2018", "WPA3-Enterprise (EAP-SHA256)","",           "PMF required"),
    ("12", "2018", "WPA2/WPA3-Personal",          "mixte", "PSK+SAE, Dragonblood surface"),
    ("13", "2018", "WPA2/WPA3-Enterprise",        "mixte", "EAP+EAP-SHA256"),
    ("14", "----", "Custom Personal",             "custom",     "user config"),
    ("15", "----", "Custom Enterprise",           "custom",     "user config"),
]

MODE_LABELS = {num: name for num, _, name, _, _ in MODE_LAYOUT}


# ------------------------------------------------------------ templates
TEMPLATES = {
    "1": ("open", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_open_unrestricted
"""),
    "2": ("open_mac", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_open_macfilter
macaddr_acl=1
accept_mac_file={macs_file}
"""),
    "3": ("wep", """\
interface={ap_iface}
driver=nl80211
ssid=00_wep
hw_mode=g
channel=6
ieee80211n=0
auth_algs=3
wep_default_key=0
wep_key0=3132333435
#wep_key_len_broadcast=5
wep_key_len_unicast=5
ignore_broadcast_ssid=0
"""),
    "4": ("wpa_p", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wpa1
auth_algs=1
wpa=1
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
wpa_passphrase=LabPassword123
"""),
    "5": ("wpa_e", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_wpa_enterprise
wpa=1
wpa_key_mgmt=WPA-EAP
wpa_pairwise=TKIP
ieee8021x=1
auth_server_addr=127.0.0.1
auth_server_port=1812
auth_server_shared_secret=testing123
"""),
    "6": ("wpa2_p", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=capture_wpa2_personal
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=LabPassword123
"""),
    "7": ("wpa2_e", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_wpa2_enterprise
wpa=2
wpa_key_mgmt=WPA-EAP
rsn_pairwise=CCMP
auth_algs=1
ieee8021x=1
auth_server_addr=127.0.0.1
auth_server_port=1812
auth_server_shared_secret=testing123
"""),
    "8": ("wpa21_p", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wpa21-2
auth_algs=1
wpa=3
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP CCMP
rsn_pairwise=CCMP
wpa_passphrase=Password123456
wpa_group_rekey=3600
"""),
    "9": ("owe", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=owe
wpa=2
wpa_key_mgmt=OWE
rsn_pairwise=CCMP
group_cipher=CCMP
ieee80211w=2
"""),
    "10": ("wpa3_p", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=Lab_WPA3_2.4GHz
ieee80211w=2
wpa=2
wpa_key_mgmt=SAE
rsn_pairwise=CCMP
wpa_passphrase=password123
sae_require_mfp=1
sae_pwe=2
"""),
    "11": ("wpa3_e", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_wpa3_enterprise
wpa=2
wpa_key_mgmt=WPA-EAP-SHA256
rsn_pairwise=CCMP
ieee80211w=2
ieee8021x=1
auth_server_addr=127.0.0.1
auth_server_port=1812
auth_server_shared_secret=testing123
"""),
    "12": ("wpa32_p", """\
interface={ap_iface}
driver=nl80211
ssid=wpa32
hw_mode=g
channel=6
wpa=2
wpa_key_mgmt=WPA-PSK SAE
rsn_pairwise=CCMP
wpa_passphrase=Password123456
ieee80211w=1
sae_pwe=2
"""),
    "13": ("wpa32_e", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=wsa_wpa3_wpa2_enterprise
wpa=2
wpa_key_mgmt=WPA-EAP WPA-EAP-SHA256
rsn_pairwise=CCMP
wpa_pairwise=CCMP
ieee80211w=1
ieee8021x=1
auth_server_addr=127.0.0.1
auth_server_port=1812
auth_server_shared_secret=testing123
"""),
    "14": ("custom_p", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=custom-personal
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=changeme
"""),
    "15": ("custom_e", """\
interface={ap_iface}
driver=nl80211
hw_mode=g
channel=6
ssid=custom-enterprise
wpa=2
wpa_key_mgmt=WPA-EAP
rsn_pairwise=CCMP
auth_algs=1
ieee8021x=1
auth_server_addr=127.0.0.1
auth_server_port=1812
auth_server_shared_secret=testing123
"""),
}

ENTERPRISE_MODES = {"5", "7", "11", "13", "15"}
MAC_FILTER_MODE  = "2"

DHCP_TEMPLATE = """\
interface={ap_iface}
dhcp-range=192.168.99.50,192.168.99.100,12h
dhcp-option=3,192.168.99.1
dhcp-option=6,192.168.99.1
dhcp-authoritative
log-queries
log-dhcp
"""


# ------------------------------------------------------------ helpers
def chown_user(path):
    try:
        os.chown(path, UID, GID)
    except (PermissionError, OSError):
        pass


def run(cmd, echo=False, check=False):
    if echo:
        print(f"      {DIM}$ {cmd}{RESET}")
    r = subprocess.run(cmd, shell=True)
    if check and r.returncode != 0:
        print(f"      {ERR}ERROR: {cmd}{RESET}")
        sys.exit(1)
    return r.returncode


def safe_input(prompt, default=""):
    try:
        v = input(prompt).strip()
        return v if v else default
    except EOFError:
        print()
        return default


def interface_exists(name):
    if not name or len(name) > 20:
        return False
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_.-]*$", name):
        return False
    return subprocess.run(
        ["ip", "link", "show", name], capture_output=True
    ).returncode == 0


def get_iface_info(iface):
    if not iface or not interface_exists(iface):
        return ("(not found)", "unknown")
    try:
        with open(f"/sys/class/net/{iface}/address") as f:
            mac = f.read().strip().upper()
    except OSError:
        mac = "(no mac)"
    mode = "unknown"
    try:
        out = subprocess.run(
            ["iw", "dev", iface, "info"], capture_output=True, text=True
        ).stdout
        m = re.search(r"^\s*type (\S+)$", out, re.MULTILINE)
        if m:
            mode = m.group(1) + " mode"
    except Exception:
        pass
    return (mac, mode)


def list_wireless_interfaces():
    ifaces = []
    for line in subprocess.run(
        ["iw", "dev"], capture_output=True, text=True
    ).stdout.split("\n"):
        m = re.match(r"\s+Interface (\S+)", line)
        if m:
            ifaces.append(m.group(1))
    return ifaces


def list_other_up_interfaces(ap_iface):
    ifaces = []
    for line in subprocess.run(
        ["ip", "-br", "link", "show", "up"],
        capture_output=True, text=True
    ).stdout.split("\n"):
        if not line.strip():
            continue
        name = line.split()[0]
        if name == ap_iface or name == "lo" or name.startswith("wl"):
            continue
        ifaces.append(name)
    return ifaces


def get_editor():
    for var in ("EDITOR", "VISUAL"):
        val = os.environ.get(var)
        if val:
            parts = shlex.split(val)
            if parts and shutil.which(parts[0]):
                return parts
    return ["nano"]


def check_requirements():
    required = [
        ("hostapd",  "sudo apt install hostapd"),
        ("dnsmasq",  "sudo apt install dnsmasq"),
        ("iw",       "sudo apt install iw"),
        ("iptables", "sudo apt install iptables"),
    ]
    missing = [(c, h) for c, h in required if not shutil.which(c)]
    if missing:
        print(f"\n  {ERR}ERROR: missing required tools:{RESET}")
        for cmd, hint in missing:
            print(f"    {cmd}   ({hint})")
        sys.exit(1)


def reset_network():
    global SHARING_ACTIVE
    if not SHARING_ACTIVE:
        return
    subprocess.run("iptables -F 2>/dev/null", shell=True)
    subprocess.run("iptables -t nat -F 2>/dev/null", shell=True)
    subprocess.run("echo 0 > /proc/sys/net/ipv4/ip_forward 2>/dev/null", shell=True)
    SHARING_ACTIVE = False


# -------------------------------------------------------- screen UI
def clear_screen():
    print("\033[2J\033[H", end="")


def hline(title=""):
    width = shutil.get_terminal_size((100, 20)).columns
    if title:
        prefix = f"── {title} "
        padding = "─" * max(0, width - len(prefix))
        print(f"{BORDER}{prefix}{padding}{RESET}")
    else:
        print(f"{BORDER}{'─' * width}{RESET}")


def show_header():
    print()
    hline("WSA")
    print()
    print(f"   {TITLE}WSA{RESET}")
    print(f"      {DIM}WIRELESS SECURITY ASSESSMENT LAB AP{RESET}")
    print()


def show_adapters(settings):
    print(f"   {TITLE}ADAPTERS{RESET}")
    for key in ("ap_iface", "mgmt_iface"):
        iface = settings.get(key, "")
        if not iface:
            continue
        mac, mode = get_iface_info(iface)
        print(f"      {BODY}{iface:<12}{mac:<20}{mode}{RESET}")
    print()


# ------------------------------------------------------------ settings
def migrate_old_theme(settings):
    if "theme" in settings:
        old = settings.pop("theme")
        mapping = {
            "dark":  ("matrix",     "matrix",     "follow"),
            "light": ("blue",       "blue",       "follow"),
            "mono":  ("monochrome", "monochrome", "follow"),
        }
        text, title, layout = mapping.get(old, ("matrix", "matrix", "follow"))
        settings.setdefault("theme_text",   text)
        settings.setdefault("theme_title",  title)
        settings.setdefault("theme_layout", layout)
    settings.setdefault("theme_text",   "matrix")
    settings.setdefault("theme_title",  "matrix")
    settings.setdefault("theme_layout", "follow")
    return settings


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return None
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"  {WARN}settings file unreadable - re-prompting{RESET}")
        return None
    ap   = s.get("ap_iface", "")
    mgmt = s.get("mgmt_iface", "")
    if not interface_exists(ap):
        print(f"  {WARN}saved AP interface '{ap}' not found - re-prompting{RESET}")
        return None
    if mgmt and not interface_exists(mgmt):
        print(f"  {WARN}saved internet interface '{mgmt}' not found - re-prompting{RESET}")
        return None
    return migrate_old_theme(s)


def save_settings(s):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)
    os.chmod(SETTINGS_FILE, 0o644)
    chown_user(CONFIG_DIR)
    chown_user(SETTINGS_FILE)


def prompt_interfaces(current=None):
    """Interactive interface selection. Each step re-renders full WSA screen.
    Returns dict {'ap_iface', 'mgmt_iface'} or None if cancelled."""
    wl = list_wireless_interfaces()
    if not wl:
        clear_screen()
        show_header()
        print(f"   {ERR}NO WIRELESS ADAPTERS DETECTED{RESET}")
        print()
        print(f"      Plug in a compatible wireless adapter")
        print(f"      Verify it appears with:  iw dev")
        print(f"      See wsa-lab-setup.sh for driver installation")
        print()
        sys.exit(1)

    # ── Step 1: pick AP interface ───────────────────────────
    if len(wl) == 1:
        ap = wl[0]
    else:
        ap = None
        while ap is None:
            clear_screen()
            show_header()
            if current:
                show_adapters(current)
            print(f"   {TITLE}INTERFACE SETUP{RESET}")
            print()
            print(f"      {BODY}Wireless (AP):{RESET}")
            for i, iface in enumerate(wl, 1):
                mac, mode = get_iface_info(iface)
                print(f"         {VAL}{i}  {iface:<12} {mac:<20} {mode}{RESET}")
            print()
            sel = safe_input(f"   {TITLE}SELECT OPTION [0 to cancel]{RESET}: ")
            if sel in ("0", ""):
                return None
            try:
                ap = wl[int(sel) - 1]
            except (ValueError, IndexError):
                continue

    # ── Step 2: pick internet interface ─────────────────────
    others = list_other_up_interfaces(ap)
    mgmt = ""
    if others:
        chosen = False
        while not chosen:
            clear_screen()
            show_header()
            print(f"   {TITLE}INTERFACE SETUP{RESET}")
            print()
            print(f"      {BODY}Wireless (AP):{RESET}  {VAL}{ap}{RESET}")
            print()
            print(f"      {BODY}Internet:{RESET}")
            for i, iface in enumerate(others, 1):
                mac, mode = get_iface_info(iface)
                print(f"         {VAL}{i}  {iface:<12} {mac:<20} {mode}{RESET}")
            none_idx = len(others) + 1
            print(f"         {VAL}{none_idx}  none (isolated lab){RESET}")
            print()
            sel = safe_input(f"   {TITLE}SELECT OPTION [0 to cancel]{RESET}: ")
            if sel in ("0", ""):
                return None
            if sel.isdigit() and int(sel) == none_idx:
                mgmt = ""
                chosen = True
            else:
                try:
                    mgmt = others[int(sel) - 1]
                    chosen = True
                except (ValueError, IndexError):
                    continue
    else:
        # No internet candidates — show info, isolated lab
        clear_screen()
        show_header()
        print(f"   {TITLE}INTERFACE SETUP{RESET}")
        print()
        print(f"      {BODY}Wireless (AP):{RESET}  {VAL}{ap}{RESET}")
        print(f"      {BODY}Internet:{RESET}      {DIM}none detected - isolated lab{RESET}")
        print()
        time.sleep(1.5)

    return {"ap_iface": ap, "mgmt_iface": mgmt}


# --------------------------------------------------------- config I/O
def materialize(name, template, ap_iface, macs_file=""):
    path = os.path.join(TMP_DIR, f"ap-gen-{name}.conf")
    with open(path, "w") as f:
        f.write(template.format(ap_iface=ap_iface, macs_file=macs_file))
    TMP_FILES.append(path)
    return path


def load_config(choice, ap_iface, macs_file=""):
    name, template = TEMPLATES[choice]
    override = os.path.join(CONFIG_DIR, f"{name}.conf")
    if os.path.exists(override):
        with open(override) as f:
            content = f.read()
        content = re.sub(
            r"^interface=.*$", f"interface={ap_iface}",
            content, count=1, flags=re.MULTILINE,
        )
        # Update accept_mac_file path (fixes stale temp path in overrides)
        if macs_file:
            if re.search(r"^accept_mac_file=.*$", content, re.MULTILINE):
                content = re.sub(
                    r"^accept_mac_file=.*$", f"accept_mac_file={macs_file}",
                    content, count=1, flags=re.MULTILINE,
                )
            else:
                content = content.rstrip() + f"\naccept_mac_file={macs_file}\n"
        path = os.path.join(TMP_DIR, f"ap-gen-{name}.conf")
        with open(path, "w") as f:
            f.write(content)
        TMP_FILES.append(path)
        print(f"      {DIM}using override: {override}{RESET}")
        return name, path
    path = materialize(name, template, ap_iface, macs_file)
    print(f"      {DIM}using template: {name}{RESET}")
    return name, path


def save_override(name, tmp_path):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    dest = os.path.join(CONFIG_DIR, f"{name}.conf")
    shutil.copy2(tmp_path, dest)
    os.chmod(dest, 0o644)
    chown_user(dest)
    return dest


def edit_file(path):
    env = os.environ.copy()
    # Under sudo, TERM may be stripped, making nano exit immediately
    # with "Error opening terminal: unknown"
    if not env.get("TERM") or env["TERM"] in ("dumb", "unknown", ""):
        env["TERM"] = "xterm-256color"
        os.environ["TERM"] = "xterm-256color"

    cmd = get_editor() + [path]
    print(f"      {DIM}editor: {' '.join(cmd)}  (TERM={env.get('TERM','')}){RESET}")
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        print(f"      {ERR}editor exited with code {r.returncode}{RESET}")
        print(f"      {DIM}try: sudo -E python3 wsa-lab.py{RESET}")
        time.sleep(2)


# ------------------------------------------------------- mac allowlist
def manage_macs_file(settings):
    """Interactive MAC allowlist management. Returns temp copy for AP, or None if cancelled."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    user_file = os.path.join(CONFIG_DIR, "accept_macs.txt")

    def read_entries():
        entries = []
        if not os.path.exists(user_file):
            return entries
        with open(user_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    entries.append(line)
        return entries

    def write_entries(entries):
        with open(user_file, "w") as f:
            f.write("# WSA-LAB MAC ALLOWLIST\n")
            f.write("# One MAC per line. Only these devices can connect to mode 2.\n")
            for mac in entries:
                f.write(f"{mac}\n")
        os.chmod(user_file, 0o644)
        chown_user(user_file)

    def normalize_mac(mac):
        return mac.strip().upper().replace("-", ":")

    def valid_mac(mac):
        return re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac) is not None

    # Create file with header if missing
    if not os.path.exists(user_file):
        write_entries([])

    while True:
        entries = read_entries()
        clear_screen()
        show_header()
        show_adapters(settings)
        print(f"   {TITLE}MAC FILTER SETUP{RESET}")
        print()
        print(f"      {BODY}File:{RESET}    {user_file}")
        print(f"      {BODY}Entries:{RESET} {len(entries)}")
        print()
        if entries:
            for i, mac in enumerate(entries, 1):
                print(f"      {VAL}{i:>2}  {mac}{RESET}")
            print()
        else:
            print(f"      {DIM}(empty - no clients will be allowed){RESET}")
            print()
        print(f"      {VAL}1  Start AP with current allowlist{RESET}")
        print(f"      {VAL}2  Add a MAC{RESET}")
        if entries:
            print(f"      {VAL}3  Remove a MAC{RESET}")
            print(f"      {VAL}4  Clear all entries{RESET}")
        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to cancel]{RESET}: ")

        if sel in ("0", ""):
            return None

        if sel == "1":
            if not entries:
                print(f"\n  {WARN}allowlist is empty - no clients will connect{RESET}")
                if safe_input(f"  Continue anyway? [y/N]: ").lower() != "y":
                    continue
            print(f"\n  {OK}starting AP with {len(entries)} entr{'y' if len(entries)==1 else 'ies'}{RESET}")
            time.sleep(1)
            return user_file

        if sel == "2":
            print()
            mac = safe_input(f"  {DIM}MAC address (AA:BB:CC:DD:EE:FF){RESET}: ")
            if not mac:
                continue
            mac = normalize_mac(mac)
            if not valid_mac(mac):
                print(f"\n  {ERR}invalid MAC format: {mac}{RESET}")
                print(f"  {DIM}expected AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF{RESET}")
                time.sleep(2.5)
                continue
            if mac in entries:
                print(f"\n  {WARN}{mac} already in allowlist{RESET}")
                time.sleep(2)
                continue
            entries.append(mac)
            write_entries(entries)
            print(f"\n  {OK}added {mac}{RESET}")
            time.sleep(1)

        if sel == "3" and entries:
            print()
            idx = safe_input(f"  {DIM}Remove which (1-{len(entries)}){RESET}: ")
            try:
                i = int(idx) - 1
                if 0 <= i < len(entries):
                    removed = entries.pop(i)
                    write_entries(entries)
                    print(f"\n  {OK}removed {removed}{RESET}")
                    time.sleep(1)
            except (ValueError, IndexError):
                pass

        if sel == "4" and entries:
            print()
            if safe_input(f"  {DIM}Clear all {len(entries)} entries? [y/N]{RESET}: ").lower() == "y":
                write_entries([])
                print(f"\n  {OK}cleared{RESET}")
                time.sleep(1)


# ------------------------------------------------------ interface prep
def prepare_ap_interface(iface):
    print(f"\n   {TITLE}CONFIGURING INTERFACE{RESET}")
    run(f"ip link set {iface} down", echo=True)
    run(f"iw dev {iface} set type managed", check=False)
    run(f"nmcli dev set {iface} managed no", check=False)
    run(f"iw dev {iface} set type __ap", echo=True, check=True)
    run(f"ip link set {iface} up", echo=True)
    run(f"ip addr flush dev {iface}", echo=True)
    run(f"ip addr add 192.168.99.1/24 dev {iface}", echo=True)
    time.sleep(1)


def setup_internet_sharing(ap_iface, mgmt_iface):
    global SHARING_ACTIVE
    print(f"\n   {TITLE}INTERNET SHARING{RESET}")
    print(f"      {VAL}{ap_iface} -> {mgmt_iface}{RESET}")
    run("echo 1 > /proc/sys/net/ipv4/ip_forward")
    run("iptables -F")
    run("iptables -t nat -F")
    run("iptables -P FORWARD ACCEPT")
    run(f"iptables -t nat -A POSTROUTING -o {mgmt_iface} -j MASQUERADE")
    run(f"iptables -A FORWARD -i {ap_iface} -o {mgmt_iface} -j ACCEPT")
    run(f"iptables -A FORWARD -i {mgmt_iface} -o {ap_iface} "
        f"-m state --state RELATED,ESTABLISHED -j ACCEPT")
    SHARING_ACTIVE = True


# ------------------------------------------------------------ services
def kill_stale():
    for svc in ("hostapd", "dnsmasq"):
        subprocess.run(f"pkill -9 {svc}", shell=True)
    time.sleep(1)


def freeradius_running():
    out = subprocess.run(
        ["ss", "-ulpn"], capture_output=True, text=True
    ).stdout
    return ":1812" in out


def start_freeradius():
    print(f"\n   {TITLE}FREERADIUS{RESET}")
    if freeradius_running():
        print(f"      {OK}already listening on 1812{RESET}")
        return
    subprocess.Popen(
        ["bash", "-c", "freeradius -X > /tmp/freeradius.log 2>&1"],
        start_new_session=True,
    )
    STARTED.add("freeradius")
    time.sleep(3)
    if not freeradius_running():
        print(f"      {ERR}ERROR: failed to start{RESET}")
        print(f"      see: sudo tail -30 /tmp/freeradius.log")
        sys.exit(1)
    print(f"      {OK}listening on 1812{RESET}")


def start_dnsmasq(dhcp_path):
    print(f"\n   {TITLE}DNSMASQ{RESET}")
    # Pipe daemon output through sed -u to prefix 6 spaces matching layout.
    subprocess.Popen(
        f"dnsmasq -C {dhcp_path} -d 2>&1 | sed -u 's/^/      /'",
        shell=True,
        start_new_session=True,
    )
    STARTED.add("dnsmasq")
    time.sleep(1)


def start_hostapd(choice, cfg_path):
    if choice == "3":
        wep_bin = "/usr/local/sbin/hostapd-wep"
        if not os.path.exists(wep_bin):
            print(f"\n  {ERR}ERROR: {wep_bin} not found{RESET}")
            print(f"  WEP requires hostapd built with CONFIG_WEP=y")
            print(f"  see wsa-lab-setup.sh for the build recipe")
            sys.exit(1)
        print(f"\n   {TITLE}HOSTAPD{RESET}")
        try:
            subprocess.run(
                f"{wep_bin} {cfg_path} 2>&1 | sed -u 's/^/      /'",
                shell=True,
            )
        except KeyboardInterrupt:
            pass
    else:
        print(f"\n   {TITLE}HOSTAPD{RESET}")
        try:
            subprocess.run(
                f"hostapd {cfg_path} 2>&1 | sed -u 's/^/      /'",
                shell=True,
            )
        except KeyboardInterrupt:
            pass


def cleanup_services():
    for svc in list(STARTED):
        subprocess.run(f"pkill -9 {svc}", shell=True)
        STARTED.discard(svc)
    subprocess.run("pkill -9 hostapd", shell=True)


# -------------------------------------------------- enterprise users
def _parse_authorize():
    """Parse authorize file. Returns (managed_users, other_lines).
    Managed users = single-line 'username   Cleartext-Password := "pwd"' entries.
    Other lines = everything else (bob with continuation, DEFAULT entries, comments)."""
    if not os.path.exists(FREERADIUS_AUTHORIZE):
        return {}, []
    with open(FREERADIUS_AUTHORIZE) as f:
        lines = f.readlines()

    managed = {}
    other = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("#") or not stripped:
            other.append(line)
            i += 1
            continue

        if FREERADIUS_BLOCK_BEGIN in line or FREERADIUS_BLOCK_END in line:
            i += 1
            continue

        m = re.match(
            r'^([a-zA-Z0-9_.-]+)\s+Cleartext-Password\s*:=\s*"([^"]*)"\s*$',
            stripped,
        )
        if m:
            has_continuation = (i + 1 < len(lines)
                                and lines[i + 1][:1].isspace()
                                and lines[i + 1].strip())
            if has_continuation:
                other.append(line)
                i += 1
                while i < len(lines) and (lines[i][:1].isspace()
                                          or not lines[i].strip()):
                    other.append(lines[i])
                    i += 1
                    if not lines[i - 1].strip():
                        break
            else:
                managed[m.group(1)] = m.group(2)
                i += 1
        else:
            other.append(line)
            i += 1

    return managed, other


def _write_authorize(managed, other):
    """Rewrite authorize file: preserved lines + new managed block."""
    if os.path.exists(FREERADIUS_AUTHORIZE):
        st = os.stat(FREERADIUS_AUTHORIZE)
        orig_uid, orig_gid, orig_mode = st.st_uid, st.st_gid, st.st_mode & 0o777
    else:
        orig_uid = orig_gid = None
        orig_mode = 0o640

    # Strip old managed block from `other`
    filtered = []
    skip = False
    for line in other:
        if FREERADIUS_BLOCK_BEGIN in line:
            skip = True
            continue
        if FREERADIUS_BLOCK_END in line:
            skip = False
            continue
        if not skip:
            filtered.append(line)

    content = "".join(filtered).rstrip("\n") + "\n"
    if managed:
        content += "\n" + FREERADIUS_BLOCK_BEGIN + "\n"
        for u, pw in managed.items():
            content += f'{u}   Cleartext-Password := "{pw}"\n'
        content += FREERADIUS_BLOCK_END + "\n"

    with open(FREERADIUS_AUTHORIZE, "w") as f:
        f.write(content)

    if orig_uid is not None:
        try:
            os.chown(FREERADIUS_AUTHORIZE, orig_uid, orig_gid)
            os.chmod(FREERADIUS_AUTHORIZE, orig_mode)
        except (PermissionError, OSError):
            pass

    if freeradius_running():
        subprocess.run("pkill freeradius", shell=True)
        time.sleep(1)


def _user_exists_anywhere(username):
    if not os.path.exists(FREERADIUS_AUTHORIZE):
        return False
    with open(FREERADIUS_AUTHORIZE) as f:
        for line in f:
            if re.match(rf'^{re.escape(username)}\s+', line):
                return True
    return False


def freeradius_has_users():
    managed, _ = _parse_authorize()
    return len(managed) > 0


def manage_enterprise_users(settings):
    """Interactive FreeRADIUS user management."""
    if not os.path.exists(FREERADIUS_AUTHORIZE):
        clear_screen()
        show_header()
        print(f"   {ERR}FreeRADIUS not installed{RESET}")
        print()
        print(f"      Enterprise modes require FreeRADIUS.")
        print(f"      Install with:  sudo apt install freeradius freeradius-utils")
        print()
        safe_input(f"   {DIM}Press Enter to return{RESET}: ")
        return False

    def valid_username(u):
        return re.match(r'^[a-zA-Z0-9_.-]{1,32}$', u) is not None

    def valid_password(pw):
        return 1 <= len(pw) <= 64 and '"' not in pw

    while True:
        managed, other = _parse_authorize()
        clear_screen()
        show_header()
        if settings:
            show_adapters(settings)
        print(f"   {TITLE}ENTERPRISE USERS{RESET}")
        print()
        print(f"      {BODY}File:{RESET}    {FREERADIUS_AUTHORIZE}")
        print(f"      {BODY}Entries:{RESET} {len(managed)}")
        print()
        if managed:
            for i, (u, pw) in enumerate(managed.items(), 1):
                print(f"      {VAL}{i:>2}  {u:<16}  {pw}{RESET}")
            print()
        else:
            print(f"      {DIM}(no users - enterprise auth will fail){RESET}")
            print()
        print(f"      {VAL}1  Done - return to menu{RESET}")
        print(f"      {VAL}2  Add a user{RESET}")
        if managed:
            print(f"      {VAL}3  Change a password{RESET}")
            print(f"      {VAL}4  Remove a user{RESET}")
        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to cancel]{RESET}: ")

        if sel in ("0", ""):
            return False

        if sel == "1":
            return True

        if sel == "2":
            print()
            u = safe_input(f"  {DIM}Username{RESET}: ").strip()
            if not u:
                continue
            if not valid_username(u):
                print(f"  {ERR}invalid username (letters, digits, _, -, .){RESET}")
                time.sleep(2)
                continue
            if u in managed or _user_exists_anywhere(u):
                print(f"  {WARN}user '{u}' already exists{RESET}")
                time.sleep(2)
                continue
            pw = safe_input(f"  {DIM}Password{RESET}: ").strip()
            if not pw:
                continue
            if not valid_password(pw):
                print(f"  {ERR}invalid password (1-64 chars, no quotes){RESET}")
                time.sleep(2)
                continue
            managed[u] = pw
            _write_authorize(managed, other)
            print(f"  {OK}added {u}{RESET}")
            time.sleep(1)
            continue

        if sel == "3" and managed:
            print()
            u = safe_input(f"  {DIM}Username to change{RESET}: ").strip()
            if u not in managed:
                print(f"  {ERR}user '{u}' not found in managed entries{RESET}")
                time.sleep(2)
                continue
            pw = safe_input(f"  {DIM}New password{RESET}: ").strip()
            if not pw:
                continue
            if not valid_password(pw):
                print(f"  {ERR}invalid password{RESET}")
                time.sleep(2)
                continue
            managed[u] = pw
            _write_authorize(managed, other)
            print(f"  {OK}password updated for {u}{RESET}")
            time.sleep(1)
            continue

        if sel == "4" and managed:
            print()
            u = safe_input(f"  {DIM}Username to remove{RESET}: ").strip()
            if u not in managed:
                print(f"  {ERR}user '{u}' not found{RESET}")
                time.sleep(2)
                continue
            if safe_input(f"  {DIM}Remove {u}? [y/N]{RESET}: ").lower() == "y":
                del managed[u]
                _write_authorize(managed, other)
                print(f"  {OK}removed {u}{RESET}")
                time.sleep(1)
            continue


# --------------------------------------------------- per-mode setup
def edit_mode_config(choice, ap_iface):
    """Open editor for mode config and save as override."""
    name, cfg_path = load_config(choice, ap_iface)
    print(f"\n      {DIM}opening {cfg_path} in editor - save and exit{RESET}")
    edit_file(cfg_path)
    override = save_override(name, cfg_path)
    print(f"      {OK}saved to {override}{RESET}")
    return override


def show_mode_setup(settings, choice):
    """Per-mode pre-flight menu. Returns 'edit' / 'edit_users' / 'run' / None."""
    name = MODE_LABELS[choice]
    mode_key = TEMPLATES[choice][0]
    cfg_path = os.path.join(CONFIG_DIR, f"{mode_key}.conf")
    is_enterprise = choice in ENTERPRISE_MODES

    year, posture, note = "", "", ""
    for num, y, m, p_, nt in MODE_LAYOUT:
        if num == choice:
            year, posture, note = y, p_, nt
            break

    while True:
        clear_screen()
        show_header()
        show_adapters(settings)

        print(f"   {TITLE}MODE: {name}{RESET}")
        info = []
        if year and year != "----":
            info.append(year)
        if posture:
            info.append(posture)
        if note:
            info.append(note)
        if info:
            print(f"      {DIM}{'  '.join(info)}{RESET}")
        exists_marker = "" if os.path.exists(cfg_path) else f"  {DIM}(will use template){RESET}"
        print(f"      {BODY}Config:{RESET} {cfg_path}{exists_marker}")
        if is_enterprise:
            managed, _ = _parse_authorize()
            print(f"      {BODY}Users:{RESET}  {len(managed)} configured")
        print()

        print(f"   {TITLE}OPTIONS{RESET}")
        print(f"      {VAL}1  Edit configuration{RESET}")
        if is_enterprise:
            print(f"      {VAL}2  Edit users/passwords{RESET}")
            print(f"      {VAL}3  Run AP{RESET}")
        else:
            print(f"      {VAL}2  Run AP{RESET}")
        print()

        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to go back]{RESET}: ")
        if sel in ("0", ""):
            return None
        if sel == "1":
            return "edit"
        if is_enterprise:
            if sel == "2":
                return "edit_users"
            if sel == "3":
                return "run"
        else:
            if sel == "2":
                return "run"


# --------------------------------------------------------------- menus
def show_main_menu(settings):
    while True:
        clear_screen()
        show_header()
        show_adapters(settings)
        print(f"   {TITLE}OPTIONS{RESET}")
        print(f"      {VAL}1  Initiate AP{RESET}")
        print(f"      {VAL}2  Adapter settings{RESET}")
        print(f"      {VAL}3  Themes and layout{RESET}")
        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to go back]{RESET}: ")
        if sel == "1":
            return "initiate"
        if sel == "2":
            return "adapters"
        if sel == "3":
            return "theme"
        if sel == "4":
            return "enterprise_users"
        if sel in ("0", "q", ""):
            return "exit"


def show_mode_menu(settings):
    while True:
        clear_screen()
        show_header()
        show_adapters(settings)
        print(f"   {TITLE}AP SECURITY PROFILE{RESET}")
        print()
        for num, year, name, posture, note in MODE_LAYOUT:
            print(
                f"      {VAL}{num:>2}  {year:<4}  {name:<30}  "
                f"{posture:<12}  {note}{RESET}"
            )
        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to go back]{RESET}: ")
        if sel in ("0", ""):
            return None
        if sel in MODE_LABELS:
            return sel


def show_theme_category_menu(settings):
    while True:
        clear_screen()
        show_header()
        show_adapters(settings)
        text_name   = settings.get("theme_text",   "matrix")
        title_name  = settings.get("theme_title",  "matrix")
        layout_name = settings.get("theme_layout", "follow")
        layout_disp = "follow text colour" if layout_name == "follow" else layout_name

        print(f"   {TITLE}THEMES AND LAYOUT{RESET}")
        print(f"      {BODY}text:   {text_name}{RESET}")
        print(f"      {BODY}title:  {title_name}{RESET}")
        print(f"      {BODY}layout: {layout_disp}{RESET}")
        print()
        print(f"   {TITLE}OPTIONS{RESET}")
        print(f"      {VAL}1  text colour    (body, values, output){RESET}")
        print(f"      {VAL}2  title colour   (section headers, menu titles){RESET}")
        print(f"      {VAL}3  layout colour  (borders, dividers){RESET}")
        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to go back]{RESET}: ")
        if sel in ("0", ""):
            return
        mapping = {"1": "text", "2": "title", "3": "layout"}
        if sel in mapping:
            show_palette_menu(settings, mapping[sel])


def show_palette_menu(settings, category):
    settings_key = f"theme_{category}"
    labels = {
        "text":   "TEXT COLOUR",
        "title":  "TITLE COLOUR",
        "layout": "LAYOUT COLOUR",
    }
    while True:
        clear_screen()
        show_header()
        show_adapters(settings)
        print(f"   {TITLE}{labels[category]}{RESET}")
        print()

        current = settings.get(
            settings_key,
            "follow" if category == "layout" else "matrix",
        )

        for i, name in enumerate(PALETTE_ORDER, 1):
            rgb = PALETTES[name]
            sw  = _swatch(rgb)
            marker = f"  {BODY}<- current{RESET}" if name == current else ""
            print(f"      {BODY}{i:>2}  {name:<14}{RESET}  {sw}{BODY}{marker}{RESET}")

        if category == "layout":
            marker = f"  {BODY}<- current{RESET}" if current == "follow" else ""
            print(f"      {BODY}F   follow text colour{RESET}{BODY}{marker}{RESET}")

        print()
        sel = safe_input(f"   {TITLE}SELECT OPTION [0 to go back]{RESET}: ")
        if sel in ("0", ""):
            return
        if category == "layout" and sel.upper() == "F":
            settings[settings_key] = "follow"
            save_settings(settings)
            refresh_colors(settings)
            return
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(PALETTE_ORDER):
                settings[settings_key] = PALETTE_ORDER[idx]
                save_settings(settings)
                refresh_colors(settings)
                return
        except ValueError:
            pass


# ----------------------------------------------------------- run AP
def run_ap(choice, settings, args):
    ap   = settings["ap_iface"]
    mgmt = settings.get("mgmt_iface", "")

    clear_screen()
    show_header()
    print(f"   {TITLE}PREPARING AP{RESET}")
    print(f"      {BODY}Wireless:{RESET}  {VAL}{ap}{RESET}")
    print(f"      {BODY}Internet:{RESET}  {VAL}{mgmt or '(none)'}{RESET}")
    print(f"      {BODY}Mode:{RESET}      {VAL}{MODE_LABELS[choice]}{RESET}")
    print()

    macs_file = ""
    if choice == MAC_FILTER_MODE:
        macs_file = manage_macs_file(settings)
        if macs_file is None:
            # User cancelled - back to menu
            return
        print(f"      {DIM}MAC allowlist file: {macs_file}{RESET}")
        # Re-show PREPARING AP context after MAC setup
        clear_screen()
        show_header()
        print(f"   {TITLE}PREPARING AP{RESET}")
        print(f"      {BODY}Wireless:{RESET}  {VAL}{ap}{RESET}")
        print(f"      {BODY}Internet:{RESET}  {VAL}{mgmt or '(none)'}{RESET}")
        print(f"      {BODY}Mode:{RESET}      {VAL}{MODE_LABELS[choice]}{RESET}")
        print()

    name, cfg_path = load_config(choice, ap, macs_file)

    dhcp_path = materialize("dhcp", DHCP_TEMPLATE, ap)

    try:
        prepare_ap_interface(ap)
        if mgmt and "--no-share" not in args:
            setup_internet_sharing(ap, mgmt)
        elif not mgmt:
            print(f"\n  {DIM}isolated lab (no internet sharing){RESET}")
        else:
            print(f"\n  {DIM}internet sharing disabled (--no-share){RESET}")

        if choice in ENTERPRISE_MODES:
            if not freeradius_has_users():
                print(f"\n  {WARN}no enterprise users configured{RESET}")
                print(f"  {DIM}manage: main menu -> 4 Enterprise users{RESET}")
                print(f"  {DIM}continuing - auth will fail until users added{RESET}")
                time.sleep(2)
            start_freeradius()

        start_dnsmasq(dhcp_path)
        start_hostapd(choice, cfg_path)
    except KeyboardInterrupt:
        print(f"\n  {DIM}interrupted{RESET}")
    finally:
        print(f"\n   {TITLE}CLEANING UP{RESET}")
        cleanup_services()
        reset_network()
        print(f"      {OK}done{RESET}")


# ---------------------------------------------------------------- main
def main():
    if os.geteuid() != 0:
        sys.stderr.write("ERROR: must be run as root\n")
        sys.stderr.write("       sudo python3 wsa-lab.py\n")
        sys.exit(1)

    argv = sys.argv[1:]
    args = set(argv)

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--list-modes" in args:
        for num, year, name, posture, note in MODE_LAYOUT:
            print(f"  {num:>2}  {year:<4}  {name:<30}  {posture:<12}  {note}")
        sys.exit(0)

    if "--reset" in args:
        shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        print(f"  cleared {CONFIG_DIR}")
        sys.exit(0)

    explicit_mode = None
    for i, a in enumerate(argv):
        if a == "--mode" and i + 1 < len(argv):
            explicit_mode = argv[i + 1]
            break
    if explicit_mode and explicit_mode not in TEMPLATES:
        print(f"ERROR: invalid --mode: {explicit_mode}")
        sys.exit(1)

    check_requirements()
    kill_stale()

    settings = None if "--reconfigure" in args else load_settings()
    if settings is None:
        settings = prompt_interfaces()
        if settings is None:
            clear_screen()
            print(f"\n  {DIM}cancelled - no settings configured{RESET}\n")
            sys.exit(0)
        save_settings(settings)
        print(f"\n  {OK}saved to {SETTINGS_FILE}{RESET}\n")

    migrate_old_theme(settings)
    refresh_colors(settings)

    if explicit_mode:
        if "--no-edit" in args:
            run_ap(explicit_mode, settings, args)
            return
        while True:
            sub = show_mode_setup(settings, explicit_mode)
            if sub is None:
                clear_screen()
                print(f"\n  {DIM}cancelled{RESET}\n")
                sys.exit(0)
            if sub == "edit":
                edit_mode_config(explicit_mode, settings["ap_iface"])
                continue
            if sub == "edit_users":
                manage_enterprise_users(settings)
                continue
            if sub == "run":
                run_ap(explicit_mode, settings, args)
                return
        return

    while True:
        action = show_main_menu(settings)
        if action == "exit":
            clear_screen()
            print(f"\n  {DIM}goodbye{RESET}\n")
            return
        if action == "adapters":
            new_settings = prompt_interfaces(current=settings)
            if new_settings is not None:
                settings = new_settings
                save_settings(settings)
            continue
        if action == "theme":
            show_theme_category_menu(settings)
            continue
        if action == "initiate":
            mode = show_mode_menu(settings)
            if mode is None:
                continue
            while True:
                sub = show_mode_setup(settings, mode)
                if sub is None:
                    break
                if sub == "edit":
                    edit_mode_config(mode, settings["ap_iface"])
                    continue
                if sub == "edit_users":
                    manage_enterprise_users(settings)
                    continue
                if sub == "run":
                    run_ap(mode, settings, args)
                    break
            continue


def _guarded_main():
    def _sigterm_handler(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, _sigterm_handler)
    try:
        signal.signal(signal.SIGHUP, _sigterm_handler)
    except (AttributeError, OSError):
        pass

    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}interrupted - exiting cleanly{RESET}\n")
        try:
            cleanup_services()
            reset_network()
        except Exception:
            pass
        sys.exit(130)


if __name__ == "__main__":
    _guarded_main()

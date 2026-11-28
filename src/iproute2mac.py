#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import json
import os
import random
import re
import subprocess
import sys
import types
from operator import itemgetter

# Version
VERSION = "1.7.6"

# Utilities
SUDO = "/usr/bin/sudo"
IFCONFIG = "/sbin/ifconfig"
ROUTE = "/sbin/route"
NETSTAT = "/usr/sbin/netstat"
NDP = "/usr/sbin/ndp"
ARP = "/usr/sbin/arp"
NETWORKSETUP = "/usr/sbin/networksetup"

HELP_ADDENDUM = """iproute2mac
Homepage: https://github.com/brona/iproute2mac
This is CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems.
Provided functionality is limited and command output is not fully compatible with iproute2.
For advanced usage use netstat, ifconfig, ndp, arp, route and networksetup directly."""  # noqa: E501


# Helper functions
def perror(*args):
    print(*args, file=sys.stderr)


def execute_cmd(cmd):
    if not isinstance(cmd, list):
        raise TypeError(
            "execute_cmd requires a list of argument strings, got %s"
            % type(cmd).__name__
        )
    print("Executing: %s" % " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        if res.stderr:
            perror(res.stderr.strip())
        if res.stdout:
            print(res.stdout, end="")
        return True
    else:
        if res.stderr:
            perror(res.stderr.strip())
        if res.stdout:
            perror(res.stdout.strip())
        return False


def json_dump(data, pretty):
    if pretty:
        print(json.dumps(data, indent=4))
    else:
        print(json.dumps(data, separators=(",", ":")))
    return True


# Classful to CIDR conversion with "default" being passed through
def cidr_from_netstat_dst(target):
    if target == "default":
        return target

    dots = target.count(".")
    if target.find("/") == -1:
        addr = target
        netmask = (dots + 1) * 8
    else:
        [addr, netmask] = target.split("/")

    addr = addr + ".0" * (3 - dots)
    return addr + "/" + str(netmask)


# Convert hexadecimal netmask in prefix length
def netmask_to_length(mask):
    return bin(int(mask, 16)).count("1")


def strict_startswith(value, start):
    if not start:
        return False
    return value.startswith(start)


def any_startswith(words, test):
    for word in words:
        if strict_startswith(word, test):
            return True
    return False


# Handles passing return value, error messages and program exit on error
def help_msg(help_func):
    if not isinstance(help_func, types.FunctionType):
        raise TypeError("Function expected for: %r" % (help_func,))

    def wrapper(func):
        def inner(*args, **kwargs):
            if not func(*args, **kwargs):
                help_func()
                return False
            return True

        return inner

    return wrapper


def randomMAC():
    """
    Generate random MAC address with XenSource Inc. OUI
    http://www.linux-kvm.com/sites/default/files/macgen.py
    """
    mac = [
        0x00,
        0x16,
        0x3E,
        random.randint(0x00, 0x7F),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return ":".join(["%02x" % x for x in mac])


# Output colorization following
# https://github.com/iproute2/iproute2/blob/915d3eafcc19706c27b220134b25c24a5b9913b3/lib/color.c#L14

# enum color
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_WHITE = "\033[37m"
C_BOLD_RED = "\033[1;31m"
C_BOLD_GREEN = "\033[1;32m"
C_BOLD_YELLOW = "\033[1;33m"
C_BOLD_BLUE = "\033[1;34m"
C_BOLD_MAGENTA = "\033[1;35m"
C_BOLD_CYAN = "\033[1;36m"
C_BOLD_WHITE = "\033[1;37m"
C_CLEAR = "\033[0m"


# color_attr
COLOR_IFNAME = 0
COLOR_MAC = 1
COLOR_INET = 2
COLOR_INET6 = 3
COLOR_OPERSTATE_UP = 4
COLOR_OPERSTATE_DOWN = 5
COLOR_NONE = 6
_COLOR_ATTR = [
    COLOR_IFNAME,
    COLOR_MAC,
    COLOR_INET,
    COLOR_INET6,
    COLOR_OPERSTATE_UP,
    COLOR_OPERSTATE_DOWN,
    COLOR_NONE,
]


# light background
# static enum color attr_colors_light[]
_ATTR_COLORS_LIGHT = [
    C_CYAN,
    C_YELLOW,
    C_MAGENTA,
    C_BLUE,
    C_GREEN,
    C_RED,
    C_CLEAR,
]


# dark background
# static enum color attr_colors_dark[]
_ATTR_COLORS_DARK = [
    C_BOLD_CYAN,
    C_BOLD_YELLOW,
    C_BOLD_MAGENTA,
    C_BOLD_BLUE,
    C_BOLD_GREEN,
    C_BOLD_RED,
    C_CLEAR,
]


def get_color_scheme(color_mode, json):
    """
    To be called from main, checks if coloring shoduld be enabled and returns applicable color scheme.

    iproute2 doesn't detect background color using OSC 11, instead it reads legacy COLORFGBG env var which is rarely used.

    From iproute2 source:
        COLORFGBG environment variable usually contains either two or three
        values separated by semicolons; we want the last value in either case.
        If this value is 0-6 or 8, background is dark.

    For iproute2mac, this as-implemented behaviour is respected.

    Returns:
        str: "none", "light", "dark"
    """
    if not _check_enable_color(color_mode, json):
        return "none"

    p = os.getenv("COLORFGBG")
    if p is not None:
        c = p.split(";")[-1]
        if c.isnumeric():
            c = int(c)
            if (c >= 0 and c <= 6) or c == 8:
                return "dark"
    return "light"


def _check_enable_color(color, json):
    """
    Check parameters, env variables and terminal features to determine if coloring should be enabled.

    For the auto mode, iproute2mac respects NO_COLOR env var.
    The original iproute2 ignores NO_COLOR with auto mode as it is relevant only if -color is not set and
    the library is configured with other than "never" as default which is distribution specific.
    In the library the default is "never" per https://github.com/iproute2/iproute2/blob/915d3eafcc19706c27b220134b25c24a5b9913b3/configure#L8

    Parameters:
        color (str): "always", "auto", "never"
        json (bool): True if json output was requested

    Returns:
        bool: True if coloring should be enabled
    """
    if color == "never" or json:
        return False

    if color == "always":
        return True

    # Following code implements auto mode
    if os.getenv("NO_COLOR") is not None:
        return False

    # Not supported if not attached to terminal
    if not sys.stdout.isatty():
        return False

    try:
        # Use tput to check color support
        colors = int(
            subprocess.check_output(
                ["tput", "colors"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
        return colors >= 8
    except (subprocess.CalledProcessError, ValueError, OSError):
        # If tput fails or returns invalid output, fall back to TERM check
        term = os.getenv("TERM", "")
        if term == "dumb":
            return False

        color_terms = [
            "xterm",
            "xterm-color",
            "xterm-256color",
            "linux",
            "screen",
            "screen-256color",
            "vt100",
            "rxvt",
        ]
        return any(term.startswith(t) for t in color_terms)


def colorize(scheme, attr, text, ljust=0):
    """
    Wraps text with color according to scheme and attribute type.

    Args:
        scheme (str): "none", "dark" or "light"
        attr (str): Attribute type, see COLOR_ATTR
        text (str): Text to colorize
        ljust (int): Left-justified space padding length

    Returns:
        str: Colorized text
    """
    if scheme == "none" or scheme is None:
        return text.ljust(ljust)

    if attr not in _COLOR_ATTR:
        raise ValueError("Invalid color attribute")

    if scheme == "light":
        color = _ATTR_COLORS_LIGHT[attr]
    else:
        color = _ATTR_COLORS_DARK[attr]

    return f"{color}{text}{C_CLEAR}" + (" " * max(0, ljust - len(text)))


def colorize_ifname(scheme, ifname, ljust=0):
    return colorize(scheme, COLOR_IFNAME, ifname, ljust)


def colorize_mac(scheme, mac, ljust=0):
    return colorize(scheme, COLOR_MAC, mac, ljust)


def colorize_inet(scheme, af, inet, ljust=0):
    """
    Matches behavior of ifa_family_color() for addresses.
    But skips coloring when inet is default.
    """
    if inet == "default":
        return str(inet).ljust(ljust)

    if af == "inet":
        return colorize(scheme, COLOR_INET, inet, ljust)
    elif af == "inet6":
        return colorize(scheme, COLOR_INET6, inet, ljust)
    else:
        return str(inet).ljust(ljust)


def colorize_op_state(scheme, state, ljust=0):
    """
    Matches behavior of oper_state_color() for states.
    """
    if state == "UP":
        return colorize(scheme, COLOR_OPERSTATE_UP, state, ljust)
    elif state == "DOWN":
        return colorize(scheme, COLOR_OPERSTATE_DOWN, state, ljust)
    else:
        return str(state).ljust(ljust)


def parse_ifconfig_links(
    res, af=-1, address=False, parse_bridge=False, sort_by_ifindex=False
):
    """Parse `ifconfig -v -a` output into a list of link dictionaries."""
    links = []
    link = None

    for line in res.split("\n"):
        if re.match(r"^[\w.-]+:", line):
            match = re.search(
                r"^([\w.-]+): flags=[\da-f]+<(.*)>.*?\bmtu (\d+).*?\bindex (\d+)",
                line,
            )
            if not match:
                link = None
                continue
            if link is not None:
                links.append(link)
            ifname, flags_raw, mtu, ifindex = match.groups()
            flags = flags_raw.split(",")
            link = {
                "ifindex": int(ifindex),
                "ifname": ifname,
                "flags": flags,
                "mtu": int(mtu),
                "operstate": "UNKNOWN",
                "link_type": "unknown",
            }
            if "LOOPBACK" in flags:
                link["link_type"] = "loopback"
                link["address"] = "00:00:00:00:00:00"
                link["broadcast"] = "00:00:00:00:00:00"
            elif "POINTOPOINT" in flags:
                link["link_type"] = "none"
            continue

        if link is None:
            continue

        if re.match(r"^\s+ether ", line):
            match = re.search(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", line)
            if match:
                link["link_type"] = "ether"
                link["address"] = match.group(1)
                link["broadcast"] = "ff:ff:ff:ff:ff:ff"
        elif address and re.match(r"^\s+inet ", line) and af != 6:
            match = re.search(
                r"inet (\d+\.\d+\.\d+\.\d+)(?: --> (\d+\.\d+\.\d+\.\d+))? netmask (0x[\da-f]+)",
                line,
            )
            if match:
                local, peer, netmask = match.groups()
                addr = {
                    "family": "inet",
                    "local": local,
                    "prefixlen": netmask_to_length(netmask),
                }
                if peer:
                    addr["address"] = peer
                brd_match = re.search(r"broadcast (\d+\.\d+\.\d+\.\d+)", line)
                if brd_match:
                    addr["broadcast"] = brd_match.group(1)
                link["addr_info"] = link.get("addr_info", []) + [addr]
        elif address and re.match(r"^\s+inet6 ", line) and af != 4:
            match = re.search(
                r"inet6 ([\da-f:]*:[\da-f:]+)%*\w*(?: --> ([\da-f:]*:[\da-f:]+)%*\w*)? prefixlen (\d+)",
                line,
            )
            if match:
                local, peer, prefixlen = match.groups()
                addr = {
                    "family": "inet6",
                    "local": local,
                    "prefixlen": int(prefixlen),
                }
                if peer:
                    addr["address"] = peer
                link["addr_info"] = link.get("addr_info", []) + [addr]
        elif match := re.search(r"^\s+status: (\w+)", line):
            status = match.group(1)
            link["operstate"] = "UP" if status == "active" else "DOWN"
        elif parse_bridge and re.match(r"^\s+maxage ", line):
            match = re.search(
                r"maxage (\d+) holdcnt (\d+) proto (\w+) maxaddr (\d+) timeout (\d+)",
                line,
            )
            if match:
                maxage, holdcnt, proto, maxaddr, timeout = match.groups()
                link["bridge"] = {
                    "maxage": int(maxage),
                    "holdcnt": int(holdcnt),
                    "proto": proto,
                    "maxaddr": int(maxaddr),
                    "timeout": int(timeout),
                    "members": [],
                }
        elif parse_bridge and re.match(r"^\s+member: ", line):
            match = re.search(r"member: ([\w.-]+) flags=[\da-f]+<(.*)>", line)
            if match and "bridge" in link:
                ifname, flags_raw = match.groups()
                link["bridge"]["members"].append(
                    {
                        "ifname": ifname,
                        "flags": flags_raw.split(","),
                    }
                )
        elif parse_bridge and re.match(r"^\s+ifmaxaddr ", line):
            match = re.search(
                r"ifmaxaddr (\d+) port (\d+) priority (\d+) path cost (\d+)",
                line,
            )
            if match and link.get("bridge", {}).get("members"):
                ifmaxaddr, ifindex, priority, cost = match.groups()
                link["bridge"]["members"][-1].update(
                    {
                        "ifmaxaddr": int(ifmaxaddr),
                        "ifindex": int(ifindex),
                        "priority": int(priority),
                        "cost": int(cost),
                    }
                )

    if link is not None:
        links.append(link)

    if sort_by_ifindex:
        return sorted(links, key=itemgetter("ifindex"))
    return links


def parse_cli_options(
    argv,
    prog,
    help_func,
    allow_af=False,
    allow_brief=False,
    allow_batch=False,
):
    """Parse common iproute2mac CLI flags for `ip` and `bridge`."""
    opts = {
        "af": -1,
        "json_print": False,
        "pretty_json": False,
        "brief": False,
        "color_mode": "never",
        "oneline": False,
    }

    while argv and argv[0].startswith("-"):
        if argv[0] == "-":
            help_func()
        elif argv[0] == "--":
            argv.pop(0)
            break
        elif argv[0][1] == "-":
            argv[0] = argv[0][1:]

        if allow_af and argv[0] == "-6":
            opts["af"] = 6
            argv.pop(0)
        elif allow_af and argv[0] == "-4":
            opts["af"] = 4
            argv.pop(0)
        elif allow_batch and strict_startswith("-batch", argv[0]):
            perror('iproute2mac: "{} -batch" is not implemented'.format(prog))
            exit(255)
        elif allow_brief and strict_startswith("-brief", argv[0]):
            opts["brief"] = True
            argv.pop(0)
        elif strict_startswith("-oneline", argv[0]):
            opts["oneline"] = True
            argv.pop(0)
        elif strict_startswith("-color", argv[0].split("=")[0]):
            color_mode = argv[0].split("=")[1] if "=" in argv[0] else "always"
            if color_mode not in ["never", "always", "auto"]:
                perror(
                    'Option "{}" is unknown, try "{} -help".'.format(
                        argv[0], prog
                    )
                )
                exit(255)
            opts["color_mode"] = color_mode
            argv.pop(0)
        elif strict_startswith("-json", argv[0]):
            opts["json_print"] = True
            argv.pop(0)
        elif strict_startswith("-pretty", argv[0]):
            opts["pretty_json"] = True
            argv.pop(0)
        elif strict_startswith("-Version", argv[0]):
            print("iproute2mac, v" + VERSION)
            exit(0)
        elif strict_startswith("-help", argv[0]):
            return None
        else:
            perror(
                'Option "{}" is unknown, try "{} -help".'.format(argv[0], prog)
            )
            exit(255)

    return opts

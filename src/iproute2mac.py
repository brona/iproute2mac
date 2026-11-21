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

# Version
VERSION = "1.7.6"

# Utilities
SUDO = "/usr/bin/sudo"
IFCONFIG = "/sbin/ifconfig"
ROUTE = "/sbin/route"
NETSTAT = "/usr/sbin/netstat"
NDP = "/usr/sbin/ndp"
ARP = "/usr/sbin/arp"
SYSCTL = "/usr/sbin/sysctl"
NETWORKSETUP = "/usr/sbin/networksetup"

HELP_ADDENDUM = """iproute2mac
Homepage: https://github.com/brona/iproute2mac
This is CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems.
Provided functionality is limited and command output is not fully compatible with iproute2.
For advanced usage use netstat, ifconfig, ndp, arp, route and networksetup directly."""  # noqa: E501


VERBOSE = sys.stdout.isatty() or bool(os.environ.get("IPROUTE2MAC_VERBOSE"))


# Helper functions
def perror(*args):
    sys.stderr.write(*args)
    sys.stderr.write("\n")


def execute_cmd(cmd, check=True):
    """Run a command changing the system.

    On failure, print its error and exit with status 2 like iproute2 when the
    kernel refuses a change, unless check is False: then return False, the
    failure being expected.
    """
    if not isinstance(cmd, list):
        raise TypeError(
            "execute_cmd requires a list of argument strings, got %s"
            % type(cmd).__name__
        )
    if cmd and cmd[0] == SUDO and os.geteuid() == 0:
        cmd = cmd[1:]
    if VERBOSE:
        print("Executing: %s" % " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    # route(8) exits with 0 when the routing socket refuses the change
    tool = cmd[1] if cmd[0] == SUDO and len(cmd) > 1 else cmd[0]
    refused = tool == ROUTE and "writing to routing socket" in res.stderr
    if res.returncode == 0 and not refused:
        if VERBOSE:
            if res.stderr:
                perror(res.stderr.strip())
            if res.stdout:
                print(res.stdout, end="")
        return True
    if check or VERBOSE:
        if res.stderr:
            perror(res.stderr.strip())
        if res.stdout:
            perror(res.stdout.strip())
    if check:
        exit(2)
    return False


def execute_cmd_output(cmd):
    """Run a command changing the system, return its output.

    On failure, print its error and exit with status 2 like execute_cmd().
    """
    if cmd and cmd[0] == SUDO and os.geteuid() == 0:
        cmd = cmd[1:]
    if VERBOSE:
        print("Executing: %s" % " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        perror((res.stderr + res.stdout).strip())
        exit(2)
    return res.stdout


def not_implemented(what, why):
    perror('iproute2mac: "%s" is not implemented, %s.' % (what, why))
    exit(1)


RUNDIR = os.environ.get("IPROUTE2MAC_RUNDIR", "/var/run/iproute2mac")
NAMES_FILE = os.path.join(RUNDIR, "names.json")


def names_load():
    """{name: {"ifname": macOS name, "kind": ..., ...}} of existing links."""
    try:
        with open(NAMES_FILE) as f:
            names = json.load(f)
    except (OSError, ValueError):
        return {}
    res = subprocess.run([IFCONFIG, "-l"], capture_output=True, text=True)
    existing = set(res.stdout.split())
    return {k: v for k, v in names.items() if v.get("ifname") in existing}


def names_save(names):
    data = json.dumps(names, indent=2, sort_keys=True) + "\n"
    if os.geteuid() == 0:
        os.makedirs(RUNDIR, exist_ok=True)
        tmp = NAMES_FILE + ".tmp"
        with open(tmp, "w") as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, NAMES_FILE)
        return
    subprocess.run([SUDO, "/bin/mkdir", "-p", RUNDIR], check=True)
    subprocess.run(
        [SUDO, "/usr/bin/tee", NAMES_FILE],
        input=data,
        text=True,
        stdout=subprocess.DEVNULL,
        check=True,
    )


def kernel_ifname(name, names=None):
    """macOS name of an interface given by its name or its macOS name."""
    if names is None:
        names = names_load()
    entry = names.get(name)
    return entry["ifname"] if entry else name


def ifname_aliases(names=None):
    """{macOS name: name} of the interfaces "ip link add" created."""
    if names is None:
        names = names_load()
    return {v["ifname"]: k for k, v in names.items()}


def hidden_ifnames(names=None):
    """macOS names of the interfaces that "ip link add" uses internally."""
    if names is None:
        names = names_load()
    return {v["hidden"] for v in names.values() if v.get("hidden")}


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
    def wrapper(func):
        def inner(*args, **kwargs):
            if not func(*args, **kwargs):
                if help_func:
                    if isinstance(help_func, types.FunctionType):
                        if args and kwargs:
                            help_func(*args, **kwargs)
                        else:
                            help_func()
                        return False
                    else:
                        raise Exception("Function expected for: " + help_func)
                else:
                    raise Exception(
                        "Function variant not defined: " + help_func
                    )
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
    except (subprocess.CalledProcessError, ValueError):
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
    return colorize(scheme, COLOR_MAC, mac, ljust=0)


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

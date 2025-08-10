#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import json
import random
import re
import subprocess
import sys
import types
import os


# Version
VERSION = "1.6.0"

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
    sys.stderr.write(*args)
    sys.stderr.write("\n")


def execute_cmd(cmd):
    print("Executing: %s" % cmd)
    status, output = subprocess.getstatusoutput(cmd)
    if status == 0:  # unix/linux commands 0 true, 1 false
        print(output)
        return True
    else:
        perror(output)
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
    return int(mask, 16).bit_count()


def any_startswith(words, test):
    for word in words:
        if word.startswith(test):
            return True
    return False


# Handles passsing return value, error messages and program exit on error
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
_COLOR_ATTR = [COLOR_IFNAME, COLOR_MAC, COLOR_INET, COLOR_INET6, COLOR_OPERSTATE_UP, COLOR_OPERSTATE_DOWN, COLOR_NONE]


# light background
# static enum color attr_colors_light[]
_ATTR_COLORS_LIGHT = [
    C_CYAN,
    C_YELLOW,
    C_MAGENTA,
    C_BLUE,
    C_GREEN,
    C_RED,
    C_CLEAR
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
    C_CLEAR
    ]


def get_color_scheme(color_mode, json):
    """
    To be called from main, checks if coloring shoduld be enabled and returns applicable color scheme.

    iproute2 doesn't detect backround color using OSC 11, instead it reads legacy COLORFGBG env var which is rarely used.

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
            if (c >= 0 and c <=6) or c == 8:
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
    if os.getenv('NO_COLOR') is not None:
        return False

    # Not supported if not attached to terminal
    if not sys.stdout.isatty():
        return False

    try:
        # Use tput to check color support
        colors = int(subprocess.check_output(['tput', 'colors'],
                                          stderr=subprocess.DEVNULL).decode().strip())
        return colors >= 8
    except (subprocess.CalledProcessError, ValueError):
        # If tput fails or returns invalid output, fall back to TERM check
        term = os.getenv('TERM', '')
        if term == 'dumb':
            return False

        color_terms = ['xterm', 'xterm-color', 'xterm-256color', 'linux',
                      'screen', 'screen-256color', 'vt100', 'rxvt']
        return any(term.startswith(t) for t in color_terms)


def colorize(scheme, attr, text):
    """
    Wraps text with color according to scheme and attribute type.

    Args:
        scheme (str): "none", "dark" or "light"
        attr (str): Attribute type, see COLOR_ATTR
        text (str): Text to colorize

    Returns:
        str: Colorized text
    """
    if scheme == "none" or scheme is None:
        return text

    if attr not in _COLOR_ATTR:
        raise ValueError("Invalid color attribute")

    if scheme == "light":
        color = _ATTR_COLORS_LIGHT[attr]
    else:
        color = _ATTR_COLORS_DARK[attr]

    return f"{color}{text}{C_CLEAR}"


def colorize_ifname(scheme, ifname):
    return colorize(scheme, COLOR_IFNAME, ifname)


def colorize_mac(scheme, mac):
    return colorize(scheme, COLOR_MAC, mac)


def colorize_inet(scheme, af, inet):
    """
    Matches behavior of ifa_family_color() for addresses.
    But skips coloring when inet is default.
    """
    if inet == "default":
        return inet

    if af == "inet":
        return colorize(scheme, COLOR_INET, inet)
    elif af == "inet6":
        return colorize(scheme, COLOR_INET6, inet)
    else:
        return inet


def colorize_op_state(scheme, state):
    """
    Matches behavior of oper_state_color() for states.
    """
    if state == "UP":
        return colorize(scheme, COLOR_OPERSTATE_UP, state)
    elif state == "DOWN":
        return colorize(scheme, COLOR_OPERSTATE_DOWN, state)
    else:
        return state

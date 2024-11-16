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
import subprocess
import sys
import types
import os

# Version
VERSION = "1.5.4"

# Colors
class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    CYAN = "\033[36m"

# Whether to use colors in output
use_colors = False

def set_color_output(enable=True):
    """
    Set whether to use colors in output
    
    Args:
        enable (bool): True to enable colors, False to disable
    """
    global use_colors
    use_colors = enable

def get_color_output():
    """
    Get current color output setting
    
    Returns:
        bool: True if colors are enabled, False otherwise
    """
    return use_colors

def supports_color():
    """
    Check if the terminal supports color output using tput
    
    Returns:
        bool: True if terminal supports color, False otherwise
    """
    # Check if output is a terminal
    if not sys.stdout.isatty():
        return False
    
    # Check NO_COLOR environment variable
    if os.getenv('NO_COLOR') is not None:
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

def colorize(color, text):
    """
    Wraps text with color if colors are enabled and terminal supports it
    
    Args:
        color (str): Color code from Colors class
        text (str): Text to colorize
        
    Returns:
        str: Colorized text if colors enabled, original text otherwise
    """
    if get_color_output():
        if not hasattr(colorize, '_checked_terminal'):
            colorize._checked_terminal = True
            if not supports_color():
                perror("Warning: Your terminal does not support colors. Color output disabled.")
                set_color_output(False)
                return text
        return f"{color}{text}{Colors.RESET}"
    return text

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


# Generate random MAC address with XenSource Inc. OUI
# http://www.linux-kvm.com/sites/default/files/macgen.py
def randomMAC():
    mac = [
        0x00,
        0x16,
        0x3E,
        random.randint(0x00, 0x7F),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return ":".join(["%02x" % x for x in mac])

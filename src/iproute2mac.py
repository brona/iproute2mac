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

# Version
VERSION = "1.5.2"

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

#!/usr/bin/env python3
# encoding: utf8


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
import string
import subprocess
import sys
import types

# Version
VERSION = "1.5.0"

# Utilities
SUDO = "/usr/bin/sudo"
IFCONFIG = "/sbin/ifconfig"
ROUTE = "/sbin/route"
NETSTAT = "/usr/sbin/netstat"
NDP = "/usr/sbin/ndp"
ARP = "/usr/sbin/arp"
NETWORKSETUP = "/usr/sbin/networksetup"


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
                specific = eval(help_func)
                if specific:
                    if isinstance(specific, types.FunctionType):
                        if args and kwargs:
                            specific(*args, **kwargs)
                        else:
                            specific()
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


# Decode ifconfig output
def parse_ifconfig():
    status, res = subprocess.getstatusoutput(
        IFCONFIG + " -v -a 2>/dev/null"
    )
    if status:  # unix status
        if res != "":
            perror(res)
        return None

    links = []
    count = 1

    for r in res.split("\n"):
        if re.match(r"^\w+:", r):
            if count > 1:
                links.append(link)
            (ifname, flags, mtu, ifindex) = re.findall(
                r"^(\w+): flags=\d+<(.*)> mtu (\d+) index (\d+)", r
            )[0]
            flags = flags.split(",")
            link = {
                "ifindex": int(ifindex),
                "ifname": ifname,
                "flags": flags,
                "mtu": int(mtu),
                "operstate": "UNKNOWN",
                "link_type": "unknown"
            }
            if "LOOPBACK" in flags:
                link["link_type"] = "loopback"
                link["address"] = "00:00:00:00:00:00"
                link["broadcast"] = "00:00:00:00:00:00"
            elif "POINTOPOINT" in flags:
                link["link_type"] = "none"
            count = count + 1
        else:
            if re.match(r"^\s+ether ", r):
                link["link_type"] = "ether"
                link["address"] = re.findall(r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", r)[0]
                link["broadcast"] = "ff:ff:ff:ff:ff:ff"
            elif re.match(r"^\s+status: ", r):
                match re.findall(r"status: (\w+)", r)[0]:
                    case "active":
                        link["operstate"] = "UP"
                    case "inactive":
                        link["operstate"] = "DOWN"
            elif re.match(r"^\s+maxage ", r):
                (maxage, holdcnt, proto, maxaddr, timeout) = re.findall(
                    r"maxage (\d+) holdcnt (\d+) proto (\w+) maxaddr (\d+) timeout (\d+)", r
                )[0]
                link["bridge"] = {
                    "maxage": int(maxage),
                    "holdcnt": int(holdcnt),
                    "proto": proto,
                    "maxaddr": int(maxaddr),
                    "timeout": int(timeout),
                    "members": []
                }
            elif re.match(r"^\s+member: ", r):
                (ifname, flags) = re.findall(r"member: (\w+) flags=\d+<(.*)>", r)[0]
                flags = flags.split(",")
                link["bridge"]["members"].append({
                    "ifname": ifname,
                    "flags": flags,
                })
            elif re.match(r"^\s+ifmaxaddr ", r):
                (ifmaxaddr, ifindex, priority, cost) = re.findall(
                    r"ifmaxaddr (\d+) port (\d+) priority (\d+) path cost (\d+)", r
                )[0]
                link["bridge"]["members"][-1].update({
                    "ifmaxaddr": int(ifmaxaddr),
                    "ifindex": int(ifindex),
                    "priority": int(priority),
                    "cost": int(cost)
                })

    if count > 1:
        links.append(link)

    return links


# Help
def do_help(argv=None, json_print=None, pretty_json=None):
    perror("Usage: bridge [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link }")
    perror("       OPTIONS := { -V[ersion] | -j[son] | -p[retty] }")
    perror("iproute2mac")
    perror("Homepage: https://github.com/brona/iproute2mac")
    perror(
        "This is CLI wrapper for basic network utilities on Mac OS X"
        " inspired with iproute2 on Linux systems."
    )
    perror(
        "Provided functionality is limited and command output is not"
        " fully compatible with iproute2."
    )
    perror(
        "For advanced usage use netstat, ifconfig, ndp, arp, route "
        " and networksetup directly."
    )
    exit(255)


def do_help_link():
    perror("Usage: bridge link show [ dev DEV ]")
    exit(255)


# Link module
@help_msg("do_help_link")
def do_link(argv, json_print, pretty_json):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(argv, json_print, pretty_json)
    elif "set".startswith(argv[0]):
        argv.pop(0)
        return do_link_set(argv)
    else:
        return False
    return True


def do_link_show(argv, json_print, pretty_json):
    links = parse_ifconfig()
    if links is None:
        return False

    dev = None
    bridges = []

    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        dev = argv[0]
        if [l for l in links if l["ifname"] == dev] == []:
            perror("Cannot find device \"{}\"".format(dev))

    for master in [l for l in links if "bridge" in l]:
        for slave in master["bridge"].get("members",[]):
            if dev and slave["ifname"] != dev:
                continue
            link = [l for l in links if l["ifname"] == slave["ifname"]][0]
            bridges.append({
                "ifindex": slave["ifindex"],
                "ifname": slave["ifname"],
                "flags": link["flags"],
                "mtu": link["mtu"],
                "master": master["ifname"],
                "state": "forwarding", #FIXME: how to ensure it is forwarding?
                "priority": slave["priority"],
                "cost": slave["cost"]
            })

    if json_print:
        return json_dump(bridges, pretty_json)

    for b in bridges:
        print("%d: %s: <%s> mtu %d master %s state %s priority %d cost %d" % (
            b["ifindex"],
            b["ifname"],
            ",".join(b["flags"]),
            b["mtu"],
            b["master"],
            b["state"],
            b["priority"],
            b["cost"]
        ))

    return True


def do_link_set(argv):
    perror("iproute2mac: bridge link set is not implemented")
    exit(255)


# Match iproute2 commands
# https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/bridge/bridge.c#n52
cmds = [
    ("link", do_link),
    ("help", do_help),
]


@help_msg("do_help")
def main(argv):
    json_print = False
    pretty_json = False

    while argv and argv[0].startswith("-"):
        # Turn --opt into -opt
        argv[0] = argv[0][1:] if argv[0][1] == "-" else argv[0]
        # Process options
        if argv[0].startswith("-color"):
            perror("iproute2mac: Color option is not implemented")
            argv.pop(0)
        elif "-json".startswith(argv[0]):
            json_print = True
            argv.pop(0)
        elif "-pretty".startswith(argv[0]):
            pretty_json = True
            argv.pop(0)
        elif "-Version".startswith(argv[0]):
            print("iproute2mac, v" + VERSION)
            exit(0)
        elif "-help".startswith(argv[0]):
            return False
        else:
            perror('Option "{}" is unknown, try "bridge help".'.format(argv[0]))
            exit(255)

    if not argv:
        return False

    for cmd, cmd_func in cmds:
        if cmd.startswith(argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(argv, json_print, pretty_json)

    perror('Object "{}" is unknown, try "bridge help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

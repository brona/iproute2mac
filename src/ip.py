#!/usr/bin/env python3
# encoding: utf8


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import ipaddress
import random
import re
import socket
import string
import subprocess
import sys
import types

# Version
VERSION = "1.4.1"

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


# Classful to CIDR conversion
def cidr_from_netstat_dst(target):
    dots = target.count(".")
    if target.find("/") == -1:
        addr = target
        netmask = (dots + 1) * 8
    else:
        [addr, netmask] = target.split("/")

    addr = addr + ".0" * (3 - dots)
    return addr + "/" + str(netmask)


# Converts e.g. ffff0000 into /16
# assumes valid netmask, counts set bits.
# https://wiki.python.org/moin/BitManipulation#bitCount.28.29
# Could be replaced with bin(netmask).count("1") or .bit_count() in Python 3.10
# https://bugs.python.org/issue29882
def addr_repl_netmask(matchobj):
    hexmask = matchobj.group(1)
    netmask = int(hexmask, 16)
    cidr = 0
    while netmask:
        netmask &= netmask - 1
        cidr += 1
    return "/%d" % cidr


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


# Help
def do_help(argv=None, af=None):
    perror("Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link | addr | route | neigh }")
    perror("       OPTIONS := { -V[ersion] |")
    perror("                    -4 | -6 }")
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


def do_help_route():
    perror("Usage: ip route list")
    perror("       ip route get ADDRESS")
    perror("       ip route { add | del | replace } ROUTE")
    perror("       ip route flush cache")
    perror("       ip route flush table main")
    perror("ROUTE := NODE_SPEC [ INFO_SPEC ]")
    perror("NODE_SPEC := [ TYPE ] PREFIX")
    perror("INFO_SPEC := NH")
    perror("TYPE := { blackhole }")
    perror("NH := { via ADDRESS | gw ADDRESS | nexthop ADDRESS | dev STRING }")
    exit(255)


def do_help_addr():
    perror("Usage: ip addr show [ dev STRING ]")
    perror("       ip addr { add | del } PREFIX dev STRING")
    exit(255)


def do_help_link():
    perror("Usage: ip link show [ DEVICE ]")
    perror("       ip link set dev DEVICE")
    perror("                [ { up | down } ]")
    perror("                [ address { LLADDR | factory | random } ]")
    perror("                [ mtu MTU ]")
    exit(255)


def do_help_neigh():
    perror("Usage: ip neighbour show [ [ to ] PREFIX ] [ dev DEV ]")
    perror("       ip neighbour flush [ dev DEV ]")
    exit(255)


# Route Module
@help_msg("do_help_route")
def do_route(argv, af):
    if not argv or (
        any_startswith(["show", "lst", "list"], argv[0]) and len(argv) == 1
    ):
        return do_route_list(af)
    elif "get".startswith(argv[0]) and len(argv) == 2:
        argv.pop(0)
        return do_route_get(argv, af)
    elif "add".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_route_add(argv, af)
    elif "delete".startswith(argv[0]) and len(argv) >= 2:
        argv.pop(0)
        return do_route_del(argv, af)
    elif "replace".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_route_del(argv, af) and do_route_add(argv, af)
    elif "flush".startswith(argv[0]) and len(argv) >= 1:
        argv.pop(0)
        return do_route_flush(argv, af)
    else:
        return False
    return True


def do_route_list(af):
    # ip route prints IPv6 or IPv4, never both
    inet = "inet6" if af == 6 else "inet"
    status, res = subprocess.getstatusoutput(
        NETSTAT + " -nr -f " + inet + " 2>/dev/null"
    )
    if status:
        perror(res)
        return False
    res = res.split("\n")
    res = res[4:]  # Removes first 4 lines
    for r in res:
        ra = r.split()
        if af == 6:
            target = ra[0]
            gw = ra[1]
            flags = ra[2]
            dev = ra[3]
            target = re.sub(r"%[^ ]+/", "/", target)
            if flags.find("W") != -1:
                continue
            if flags.find("B") != -1:
                print("blackhole " + target)
                continue
            if re.match(r"link.+", gw):
                print(target + " dev " + dev + "  scope link")
            else:
                print(target + " via " + gw + " dev " + dev)
        else:
            target = ra[0]
            gw = ra[1]
            flags = ra[2]
            # macOS Catalina
            dev = ra[3]
            if len(ra) >= 6:
                # macOS Mojave and earlier
                dev = ra[5]
            if flags.find("W") != -1:
                continue
            if flags.find("B") != -1:
                print("blackhole " + cidr_from_netstat_dst(target))
                continue
            if target == "default":
                print("default via " + gw + " dev " + dev)
            else:
                cidr = cidr_from_netstat_dst(target)
                if re.match(r"link.+", gw):
                    print(cidr + " dev " + dev + "  scope link")
                else:
                    print(cidr + " via " + gw + " dev " + dev)
    return True


def do_route_add(argv, af):
    options = ""
    if argv[0] == "blackhole":
        argv.pop(0)
        if len(argv) != 1:
            return False
        argv.append("via")
        argv.append("::1" if ":" in argv[0] or af == 6 else "127.0.0.1")
        options = "-blackhole"

    if len(argv) not in (3, 5):
        return False

    if len(argv) == 5:
        perror(
            "iproute2mac: Ignoring last 2 arguments, not implemented: {} {}".format(
                argv[3], argv[4]
            )
        )

    if argv[1] in ["via", "nexthop", "gw"]:
        gw = argv[2]
    elif argv[1] in ["dev"]:
        gw = "-interface " + argv[2]
    else:
        do_help_route()

    prefix = argv[0]
    inet = "-inet6 " if ":" in prefix or af == 6 else ""

    return execute_cmd(
        SUDO + " " + ROUTE + " add " + inet + prefix + " " + gw + " " + options
    )


def do_route_del(argv, af):
    options = ""
    if argv[0] == "blackhole":
        argv.pop(0)
        if len(argv) != 1:
            return False
        if ":" in argv[0] or af == 6:
            options = " ::1 -blackhole"
        else:
            options = " 127.0.0.1 -blackhole"

    prefix = argv[0]
    inet = "-inet6 " if ":" in prefix or af == 6 else ""
    return execute_cmd(
        SUDO + " " + ROUTE + " delete " + inet + prefix + options
    )


def do_route_flush(argv, af):
    if not argv:
        perror('"ip route flush" requires arguments.')
        perror("")
        return False

    # https://github.com/brona/iproute2mac/issues/38
    # http://linux-ip.net/html/tools-ip-route.html
    if argv[0] == "cache":
        print("iproute2mac: There is no route cache to flush in MacOS,")
        print("             returning 0 status code for compatibility.")
        return True
    elif len(argv) == 2 and argv[0] == "table" and argv[1] == "main":
        family = "-inet6" if af == 6 else "-inet"
        print("iproute2mac: Flushing all routes")
        return execute_cmd(SUDO + " " + ROUTE + " -n flush " + family)
    else:
        return False


def do_route_get(argv, af):
    target = argv[0]

    inet = ""
    if ":" in target or af == 6:
        af = 6
        inet = "-inet6 "
        family = socket.AF_INET6
    else:
        family = socket.AF_INET

    status, res = subprocess.getstatusoutput(
        ROUTE + " -n get " + inet + target
    )
    if status:  # unix status or not in table
        perror(res)
        return False
    if res.find("not in table") >= 0:
        perror(res)
        exit(1)

    res = dict(
        re.findall(
            r"^\W*((?:route to|destination|gateway|interface)): (.+)$",
            res,
            re.MULTILINE,
        )
    )

    route_to = res["route to"]
    dev = res["interface"]
    via = res.get("gateway", "")

    try:
        s = socket.socket(family, socket.SOCK_DGRAM)
        s.connect((route_to, 7))
        src_ip = s.getsockname()[0]
        s.close()
        src = "  src " + src_ip
    except Exception:
        src = ""

    if via == "":
        print(route_to + " dev " + dev + src)
    else:
        print(route_to + " via " + via + " dev " + dev + src)
    return True


# Addr Module
@help_msg("do_help_addr")
def do_addr(argv, af):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_addr_show(argv, af)
    elif "add".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_add(argv, af)
    elif "delete".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_del(argv, af)
    else:
        return False
    return True


def do_addr_show(argv, af):
    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        param = argv[0]
    else:
        param = "-a"

    status, res = subprocess.getstatusoutput(
        IFCONFIG + " " + param + " 2>/dev/null"
    )
    if status:
        if res == "":
            perror(param + " not found")
        else:
            perror(res)
        return False
    res = re.sub(r"(%[^ ]+)? prefixlen ([\d+])", "/\\2", res)
    res = re.sub(r" netmask 0x([0-9a-fA-F]+)", addr_repl_netmask, res)
    res = re.sub(r"broadcast", "brd", res)

    SIX = ""
    if af == 6:
        SIX = "6"
    elif af == 4:
        SIX = " "

    address_count = 0
    output = ""
    buff = ""
    ifname = ""
    for r in res.split("\n"):
        if re.match(r"^\w", r):
            if address_count > 0:
                output += buff
            buff = ""
            ifname = re.findall(r"^([^:]+): .+", r)[0]
            address_count = 0
            buff += r.rstrip() + "\n"
        elif re.match(r"^\W+inet" + SIX + ".+", r):
            address_count += 1
            if re.match(r"^\W+inet .+", r):
                buff += r.rstrip() + " " + ifname + "\n"
            else:
                buff += r.rstrip() + "\n"
        elif re.match(r"^\W+ether.+", r):
            buff += r.rstrip() + "\n"

    if address_count > 0:
        output += buff
    print(output.rstrip())
    return True


def do_addr_add(argv, af):
    if len(argv) < 2:
        return False

    dst = ""
    if argv[1] == "peer":
        argv.pop(1)
        dst = argv.pop(1)

    if argv[1] == "dev":
        argv.pop(1)
    else:
        return False
    try:
        addr = argv[0]
        dev = argv[1]
    except IndexError:
        perror("dev not found")
        exit(1)
    inet = ""
    if ":" in addr or af == 6:
        af = 6
        inet = " inet6"
    return execute_cmd(
        SUDO + " " + IFCONFIG + " " + dev + inet + " add " + addr + " " + dst
    )


def do_addr_del(argv, af):
    if len(argv) < 2:
        return False
    if argv[1] == "dev":
        argv.pop(1)
    try:
        addr = argv[0]
        dev = argv[1]
    except IndexError:
        perror("dev not found")
        exit(1)
    inet = "inet"
    if ":" in addr or af == 6:
        af = 6
        inet = "inet6"
    return execute_cmd(
        SUDO + " " + IFCONFIG + " " + dev + " " + inet + " " + addr + " remove"
    )


# Link module
@help_msg("do_help_link")
def do_link(argv, af):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(argv, af)
    elif "set".startswith(argv[0]):
        argv.pop(0)
        return do_link_set(argv, af)
    else:
        return False
    return True


def do_link_show(argv, af):
    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        param = argv[0]
    else:
        param = "-a"

    status, res = subprocess.getstatusoutput(
        IFCONFIG + " " + param + " 2>/dev/null"
    )
    if status:  # unix status
        if res == "":
            perror(param + " not found")
        else:
            perror(res)
        return False
    for r in res.split("\n"):
        if not re.match(r"\s+inet.+", r):
            print(r)
    return True


def do_link_set(argv, af):
    if not argv:
        return False
    elif argv[0] == "dev":
        argv.pop(0)

    if len(argv) < 2:
        return False

    dev = argv[0]

    IFCONFIG_DEV_CMD = SUDO + " " + IFCONFIG + " " + dev
    try:
        args = iter(argv)
        for arg in args:
            if arg == "up":
                if not execute_cmd(IFCONFIG_DEV_CMD + " up"):
                    return False
            elif arg == "down":
                if not execute_cmd(IFCONFIG_DEV_CMD + " down"):
                    return False
            elif arg in ["address", "addr", "lladdr"]:
                addr = next(args)
                if addr in ["random", "rand"]:
                    addr = randomMAC()
                elif addr == "factory":
                    (status, res) = subprocess.getstatusoutput(
                        NETWORKSETUP + " -listallhardwareports"
                    )
                    if status != 0:
                        return False
                    details = re.findall(
                        r"^(?:Device|Ethernet Address): (.+)$",
                        res,
                        re.MULTILINE,
                    )
                    addr = details[details.index(dev) + 1]
                if not execute_cmd(IFCONFIG_DEV_CMD + " lladdr " + addr):
                    return False
            elif arg == "mtu":
                mtu = int(next(args))
                if not execute_cmd(IFCONFIG_DEV_CMD + " mtu " + str(mtu)):
                    return False
    except Exception:
        return False
    return True


# Neigh module
@help_msg("do_help_neigh")
def do_neigh(argv, af):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "list", "lst"], argv[0]) and len(argv) <= 5:
        argv.pop(0)
        return do_neigh_show(argv, af)
    elif "flush".startswith(argv[0]):
        argv.pop(0)
        return do_neigh_flush(argv, af)
    else:
        return False


def do_neigh_show(argv, af):
    prefix = None
    dev = None
    try:
        while argv:
            arg = argv.pop(0)
            if arg == "to":
                prefix = argv.pop(0)
            elif arg == "dev":
                dev = argv.pop(0)
            elif prefix is None:
                prefix = arg
            else:
                return False
        if prefix:
            prefix = ipaddress.ip_network(prefix, strict=False)
    except Exception:
        return False

    nd_ll_states = {
        "R": "REACHABLE",
        "S": "STALE",
        "D": "DELAY",
        "P": "PROBE",
        "I": "INCOMPLETE",
        "N": "INCOMPLETE",
        "W": "INCOMPLETE",
    }

    neighs = []

    if af != 4:
        res = subprocess.run(
            [NDP, "-an"], capture_output=True, text=True, check=True
        )
        for row in res.stdout.splitlines()[1:]:
            cols = row.split()
            entry = {}
            entry["l3a"] = re.sub(r"%.+$", "", cols[0])
            entry["l2a"] = cols[1] if cols[1] != "(incomplete)" else None
            entry["dev"] = cols[2]
            if cols[1] == "(incomplete)" and cols[4] != "R":
                entry["status"] = "INCOMPLETE"
            else:
                entry["status"] = nd_ll_states[cols[4]]
            entry["router"] = len(cols) >= 6 and cols[5] == "R"
            neighs.append(entry)

    if af != 6:
        args = [ARP, "-anl"]
        if dev:
            args += ["-i", dev]

        res = subprocess.run(args, capture_output=True, text=True, check=True)
        for row in res.stdout.splitlines()[1:]:
            cols = row.split()
            entry = {}
            entry["l3a"] = cols[0]
            entry["l2a"] = cols[1] if cols[1] != "(incomplete)" else None
            entry["dev"] = cols[4]
            if cols[1] == "(incomplete)":
                entry["status"] = "INCOMPLETE"
            else:
                entry["status"] = "REACHABLE"
            entry["router"] = False
            neighs.append(entry)

    for nb in neighs:
        if dev and nb["dev"] != dev:
            continue
        if prefix and ipaddress.ip_address(nb["l3a"]) not in prefix:
            continue

        line = nb["l3a"]
        if not dev:
            line += " dev " + nb["dev"]
        if nb["l2a"]:
            line += " lladdr " + nb["l2a"]
        if nb["router"]:
            line += " router"
        line += " " + nb["status"]

        print(line)

    return True


def do_neigh_flush(argv, af):
    if len(argv) != 2:
        perror("Flush requires arguments.")
        exit(1)

    if argv[0] != "dev":
        return False
    dev = argv[1]

    if af != 4:
        print(
            "iproute2mac: NDP doesn't support filtering by interface,"
            "flushing all IPv6 entries."
        )
        execute_cmd(SUDO + " " + NDP + " -cn")
    if af != 6:
        execute_cmd(SUDO + " " + ARP + " -a -d -i " + dev)
    return True


# Match iproute2 commands
# https://git.kernel.org/pub/scm/linux/kernel/git/shemminger/iproute2.git/tree/ip/ip.c#n75
cmds = [
    ("address", do_addr),
    ("route", do_route),
    ("neighbor", do_neigh),
    ("neighbour", do_neigh),
    ("link", do_link),
    ("help", do_help),
]


@help_msg("do_help")
def main(argv):
    af = -1  # default / both

    # Check all the options
    while argv and argv[0].startswith("-"):
        # Detect Address family
        if argv[0] == "-6":
            af = 6
            argv.pop(0)
        elif argv[0] == "-4":
            af = 4
            argv.pop(0)
        elif argv[0].startswith("-color"):
            perror("iproute2mac: Color option is not implemented")
            argv.pop(0)
        elif "-Version".startswith(argv[0]):
            print("iproute2mac, v" + VERSION)
            exit(0)
        elif "-help".startswith(argv[0]):
            return False
        else:
            perror('Option "{}" is unknown, try "ip help".'.format(argv[0]))
            exit(255)

    if not argv:
        return False

    for cmd, cmd_func in cmds:
        if cmd.startswith(argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(argv, af)

    perror('Object "{}" is unknown, try "ip help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

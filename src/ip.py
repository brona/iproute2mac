#!/usr/bin/env python3
# encoding: utf8


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import sys
import subprocess
import re
import string
import random
import types
import socket

# Version
VERSION = "1.3.0"

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
    perror("       ip route { add | del | flush | replace } ROUTE")
    perror("TYPE := { blackhole }")
    perror("ROUTE := [ TYPE ] PREFIX [ nexthop NH ]")
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
    perror("Usage: ip neighbour { show | flush } [ dev DEV ]")  # delete, add
    exit(255)


# Route Module
@help_msg("do_help_route")
def do_route(argv, af):
    if not argv:
        return do_route_list(af)
    elif "add".startswith(argv[0]) and len(argv) >= 3:
        if len(argv) > 0:
            argv.pop(0)
        return do_route_add(argv, af)
    elif "delete".startswith(argv[0]) and len(argv) >= 2:
        if len(argv) > 0:
            argv.pop(0)
        return do_route_del(argv, af)
    elif (
        "list".startswith(argv[0])
        or "show".startswith(argv[0])
        or "lst".startswith(argv[0])
    ):
        # show help if there is an extra argument on show
        if len(argv) > 1:
            return False
        return do_route_list(af)
    elif "get".startswith(argv[0]) and len(argv) == 2:
        argv.pop(0)
        return do_route_get(argv, af)
    elif "flush".startswith(argv[0]) and len(argv) == 2:
        argv.pop(0)
        return do_route_flush(argv, af)
    elif "replace".startswith(argv[0]) and len(argv) >= 4:
        if len(argv) > 0:
            argv.pop(0)
        do_route_del(argv, af)
        return do_route_add(argv, af)
    else:
        return False
    return True


def do_route_list(af):
    if af == 6:
        status, res = subprocess.getstatusoutput(
            NETSTAT + " -nr -f inet6 2>/dev/null"
        )
    else:
        status, res = subprocess.getstatusoutput(
            NETSTAT + " -nr -f inet 2>/dev/null"
        )
    if status:
        perror(res)
        return False
    blackholes = []
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
            if flags.find("B") >= 0:
                blackholes.append(ra)
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
            if flags.find("B") >= 0:
                blackholes.append(ra)
                continue
            if target == "default":
                print("default via " + gw + " dev " + dev)
            else:
                cidr = cidr_from_netstat_target(target)
                if re.match(r"link.+", gw):
                    print(cidr + " dev " + dev + "  scope link")
                else:
                    print(cidr + " via " + gw + " dev " + dev)
    for b in blackholes:
        target = b[0]
        if af == 6:
            target = re.sub(r"%[^ ]+/", "/", target)
            print("blackhole " + target)
        else:
            cidr = cidr_from_netstat_target(target)
            print("blackhole " + cidr)
    return True


def cidr_from_netstat_target(target):
    dots = target.count(".")
    if target.find("/") == -1:
        addr = target
        netmask = 8 + dots * 8
    else:
        [addr, netmask] = target.split("/")

    if dots == 2:
        addr = addr + ".0"
    elif dots == 1:
        addr = addr + ".0.0"
    elif dots == 0:
        addr = addr + ".0.0.0"
    return addr + "/" + str(netmask)


def do_route_add(argv, af):
    target = argv[0]
    via = argv[1]
    options = ""
    if "blackhole" == target:
        target = via
        via = "via"
        gw = "127.0.0.1"
        options = "-blackhole "
    else:
        gw = argv[2]
    if via not in ["via", "nexthop", "gw", "dev"]:
        do_help_route()
    inet = ""
    if ":" in target or af == 6:
        af = 6
        inet = "-inet6 "
    if "dev" == via:
        gw = "-interface " + gw
    return execute_cmd(
        SUDO + " " + ROUTE + " add " + inet + target + " " + gw + " " + options
    )


def do_route_del(argv, af):
    target = argv[0]
    inet = ""
    if "blackhole" == target:
        target = " ".join([argv[1], "127.0.0.1", "-blackhole"])
    if ":" in target or af == 6:
        af = 6
        inet = "-inet6 "
    return execute_cmd(SUDO + " " + ROUTE + " delete " + inet + target)


def do_route_flush(argv, af):
    target = argv[0]
    return execute_cmd(SUDO + " " + ROUTE + " -n flush ")


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
        return do_addr_show(argv, af)
    elif "add".startswith(argv[0]) and len(argv) >= 3:
        if len(argv) > 0:
            argv.pop(0)
        return do_addr_add(argv, af)
    elif "delete".startswith(argv[0]) and len(argv) >= 3:
        if len(argv) > 0:
            argv.pop(0)
        return do_addr_del(argv, af)
    elif (
        "list".startswith(argv[0])
        or "show".startswith(argv[0])
        or "lst".startswith(argv[0])
    ):
        if len(argv) > 0:
            argv.pop(0)
        return do_addr_show(argv, af)
    else:
        return False
    return True


def addr_repl_netmask(matchobj):
    hexmask = matchobj.group(1)
    netmask = int(hexmask, 16)
    cidr = 0
    while netmask:
        cidr += netmask & 0x1
        netmask >>= 1
    return "/%d" % cidr


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
        return False
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
        return False
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
        return do_link_show(argv, af)
    elif (
        "show".startswith(argv[0])
        or "list".startswith(argv[0])
        or "lst".startswith(argv[0])
    ):
        if len(argv) > 0:
            argv.pop(0)
        return do_link_show(argv, af)
    elif "set".startswith(argv[0]):
        if len(argv) > 0:
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

    try:
        args = iter(argv)
        for arg in args:
            if arg == "up":
                if not execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " up"):
                    return False
            elif arg == "down":
                if not execute_cmd(
                    SUDO + " " + IFCONFIG + " " + dev + " down"
                ):
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
                if not execute_cmd(
                    SUDO + " " + IFCONFIG + " " + dev + " lladdr " + addr
                ):
                    return False
            elif arg == "mtu":
                mtu = int(next(args))
                if not execute_cmd(
                    SUDO + " " + IFCONFIG + " " + dev + " mtu " + str(mtu)
                ):
                    return False
    except Exception:
        return False
    return True


# Neigh module
def do_neigh(argv, af):
    statuses = {"R": "REACHABLE", "S": "STALE"}
    idev = None
    if len(argv) > 1:
        if len(argv) < 3 and argv[1] != "dev":
            do_help_neigh()
        idev = argv[2]
    if (not argv) or (argv[0] in ["show", "sh", "s", "list", "lst", "ls"]):
        if af != 4:
            (status, res) = subprocess.getstatusoutput(
                NDP + " -an 2>/dev/null"
            )
            if status != 0:
                return False
            res = res.split("\n")
            res = res[1:]
            for r in res:
                ra = r.split()
                l3a = re.sub(r"%.+$", "", ra[0])  # remove interface
                l2a = ra[1]
                dev = ra[2]
                exp = ra[3]
                if idev and idev != dev:
                    continue
                if ra[4] in statuses:
                    stat = statuses[ra[4]]
                else:
                    stat = "INCOMPLETE"
                if l2a == "(incomplete)" and stat != "REACHABLE":
                    print(l3a + " dev " + dev + " INCOMPLETE")
                else:
                    print(l3a + " dev " + dev + " lladdr " + l2a + " " + stat)
        if af != 6:
            if idev:
                (status, res) = subprocess.getstatusoutput(
                    ARP + " -anli " + idev + " 2>/dev/null"
                )
            else:
                (status, res) = subprocess.getstatusoutput(
                    ARP + " -anl 2>/dev/null"
                )
            if status != 0:
                return False
            res = res.split("\n")
            res = res[1:]
            for r in res:
                ra = r.split()
                l3a = ra[0]
                l2a = ra[1]
                dev = ra[4]
                if l2a == "(incomplete)":
                    print(l3a + " dev " + dev + " INCOMPLETE")
                else:
                    print(
                        l3a + " dev " + dev + " lladdr " + l2a + " REACHABLE"
                    )
    # TODO: delete, add
    elif argv[0] in ["f", "fl", "flush"]:
        if not idev:
            perror("Flush requires arguments.")
            exit(1)
        if af != 4:
            # TODO: dev option for ipv6 (ndp command doesn't support it now)
            if not execute_cmd(SUDO + " " + NDP + " -c"):
                return False
        if af != 6:
            if not execute_cmd(SUDO + " " + ARP + " -a -d -i " + idev):
                return False
    else:
        do_help_neigh()

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

    # Detect Address family
    af = -1  # default / both
    if argv and argv[0] == "-6":
        af = 6
        argv.pop(0)
    elif argv and argv[0] == "-4":
        af = 4
        argv.pop(0)

    if not argv:
        return False

    if argv[0] in ["-V", "-Version"]:
        print("iproute2mac, v" + VERSION)
        exit(0)

    if argv[0] in ["-h", "-help"]:
        return False

    if argv[0].startswith("-"):
        perror('Option "{}" is unknown, try "ip -help".'.format(argv[0]))
        exit(255)

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

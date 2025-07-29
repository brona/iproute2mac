#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

from iproute2mac import *
import ipaddress
import os
import re
import socket
import subprocess
import sys


# Decode ifconfig output
def parse_ifconfig(res, af, address):
    links = []
    count = 1

    for r in res.split("\n"):
        if re.match(r"^\w+:", r):
            if count > 1:
                links.append(link)
            (ifname, flags, mtu, ifindex) = re.findall(
                r"^(\w+): flags=[\da-f]+<(.*)>.+mtu (\d+).+index (\d+)", r)[0]
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
                link["address"] = re.findall(
                    r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", r)[0]
                link["broadcast"] = "ff:ff:ff:ff:ff:ff"
            elif address and re.match(r"^\s+inet ", r) and af != 6:
                (local, peer, netmask) = re.findall(
                    r"inet (\d+\.\d+\.\d+\.\d+)(?: --> (\d+\.\d+\.\d+\.\d+))? netmask (0x[\da-f]+)", r)[0]
                addr = {
                    "family": "inet",
                    "local": local,
                    "prefixlen": netmask_to_length(netmask),
                }
                if peer:
                    addr["address"] = peer
                if re.match(r"^.*broadcast", r):
                    addr["broadcast"] = re.findall(
                        r"broadcast (\d+\.\d+\.\d+\.\d+)", r)[0]
                link["addr_info"] = link.get("addr_info", []) + [addr]
            elif address and re.match(r"^\s+inet6 ", r) and af != 4:
                (local, peer, prefixlen) = re.findall(
                    r"inet6 ([\da-f:]*:[\da-f:]+)%*\w*(?: --> ([\da-f:]*:[\da-f:]+)%*\w*)? prefixlen (\d+)", r)[0]
                addr = {
                  "family": "inet6",
                  "local": local,
                  "prefixlen": int(prefixlen)
                }
                if peer:
                    addr["address"] = peer
                link["addr_info"] = link.get("addr_info", []) + [addr]
            elif re.match(r"^\s+status: ", r):
                match re.findall(r"status: (\w+)", r)[0]:
                    case "active":
                        link["operstate"] = "UP"
                    case "inactive":
                        link["operstate"] = "DOWN"

    if count > 1:
        links.append(link)

    return links


def link_addr_show(argv, af, json_print, pretty_json, color, address):
    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        param = argv[0]
    else:
        param = "-a"

    status, res = subprocess.getstatusoutput(
        IFCONFIG + " -v " + param + " 2>/dev/null"
    )
    if status:  # unix status
        if res == "":
            perror(param + " not found")
        else:
            perror(res)
        return False

    links = parse_ifconfig(res, af, address)

    if json_print:
        return json_dump(links, pretty_json)

    for l in links:
        print("%d: %s: <%s> mtu %d status %s" % (
            l["ifindex"],
            colorize_ifname(color, l["ifname"]),
            ",".join(l["flags"]),
            l["mtu"],
            colorize_op_state(color, l["operstate"])
        ))
        print(
            "    link/" + l["link_type"] +
            ((" " + colorize_mac(color, l["address"])) if "address" in l else "") +
            ((" brd " + colorize_mac(color, l["broadcast"])) if "broadcast" in l else "")
        )
        for a in l.get("addr_info", []):
            print(
                "    %s %s" % (a["family"], colorize_inet(color, a["family"], a["local"])) +
                ((" peer %s" % colorize_inet(color, a["family"], a["address"])) if "address" in a else "") +
                "/%d" % (a["prefixlen"]) +
                ((" brd " + colorize_inet(color, a["family"], a["broadcast"])) if "broadcast" in a else "")
            )

    return True


# Help
def do_help(argv=None, af=None, json_print=None, pretty_json=None, color=None):
    perror("Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link | addr | route | neigh }")
    perror("       OPTIONS := { -V[ersion] | -j[son] | -p[retty] | -c[olor] |")
    perror("                    -4 | -6 }")
    perror(HELP_ADDENDUM)
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
@help_msg(do_help_route)
def do_route(argv, af, json_print, pretty_json, color):
    if not argv or (
        any_startswith(["show", "lst", "list"], argv[0]) and len(argv) == 1
    ):
        return do_route_list(af, json_print, pretty_json, color)
    elif "get".startswith(argv[0]) and len(argv) == 2:
        argv.pop(0)
        return do_route_get(argv, af, json_print, pretty_json, color)
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


def do_route_list(af, json_print, pretty_json, color):
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

    routes = []

    for r in res:
        ra = r.split()
        target = ra[0]
        gw = ra[1]
        flags = ra[2]
        # macOS Mojave and earlier vs Catalina
        dev = ra[5] if len(ra) >= 6 else ra[3]
        if flags.find("W") != -1:
            continue
        if af == 6:
            target = re.sub(r"%[^ ]+/", "/", target)
        else:
            target = cidr_from_netstat_dst(target)
        if flags.find("B") != -1:
            routes.append({"type": "blackhole", "dst": target, "flags": []})
            continue
        if re.match(r"link.+", gw):
            routes.append(
                {"dst": target, "dev": dev, "scope": "link", "flags": []})
        else:
            routes.append(
                {"dst": target, "gateway": gw, "dev": dev, "flags": []})

    if json_print:
        return json_dump(routes, pretty_json)

    for route in routes:
        if "type" in route:
            print("%s %s" % (
                route["type"],
                colorize_inet(color, inet, route["dst"])
                )
            )
        elif "scope" in route:
            print("%s dev %s scope %s" % (
                colorize_inet(color, inet, route["dst"]),
                colorize_ifname(color, route["dev"]),
                route["scope"]
                )
            )
        elif "gateway" in route:
            print("%s via %s dev %s" % (
                colorize_inet(color, inet, route["dst"]),
                colorize_inet(color, inet, route["gateway"]),
                colorize_ifname(color, route["dev"])
                )
            )

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
            "iproute2mac: Ignoring last 2 arguments, not implemented: {} {}"
            .format(argv[3], argv[4])
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


def do_route_get(argv, af, json_print, pretty_json, color):
    target = argv[0]

    inet = ""
    if ":" in target or af == 6:
        inet = "-inet6 "
        family = socket.AF_INET6
        color_af = "inet6"
    else:
        family = socket.AF_INET
        color_af = "inet"

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

    route = {"dst": res["route to"], "dev": res["interface"]}

    if "gateway" in res:
        route["gateway"] = res["gateway"]

    try:
        s = socket.socket(family, socket.SOCK_DGRAM)
        s.connect((route["dst"], 7))
        route["prefsrc"] = src_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    route["flags"] = []
    route["uid"] = os.getuid()
    route["cache"] = []

    if json_print:
        return json_dump([route], pretty_json)

    print(
        colorize_inet(color, color_af, route["dst"]) +
        ((" via " + colorize_inet(color, color_af, route["gateway"])) if "gateway" in route else "") +
        " dev " + colorize_ifname(color, route["dev"]) +
        ((" src " + colorize_inet(color, color_af, route["prefsrc"])) if "prefsrc" in route else "") +
        " uid " + str(route["uid"])
    )

    return True


# Addr Module
@help_msg(do_help_addr)
def do_addr(argv, af, json_print, pretty_json, color):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_addr_show(argv, af, json_print, pretty_json, color)
    elif "add".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_add(argv, af)
    elif "delete".startswith(argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_del(argv, af)
    else:
        return False
    return True


def do_addr_show(argv, af, json_print, pretty_json, color):
    return link_addr_show(argv, af, json_print, pretty_json, color, True)


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
@help_msg(do_help_link)
def do_link(argv, af, json_print, pretty_json, color):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(argv, af, json_print, pretty_json, color)
    elif "set".startswith(argv[0]):
        argv.pop(0)
        return do_link_set(argv, af)
    else:
        return False
    return True


def do_link_show(argv, af, json_print, pretty_json, color):
    return link_addr_show(argv, af, json_print, pretty_json, color, False)


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
@help_msg(do_help_neigh)
def do_neigh(argv, af, json_print, pretty_json, color):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "list", "lst"], argv[0]) and len(argv) <= 5:
        argv.pop(0)
        return do_neigh_show(argv, af, json_print, pretty_json, color)
    elif "flush".startswith(argv[0]):
        argv.pop(0)
        return do_neigh_flush(argv, af)
    else:
        return False


def do_neigh_show(argv, af, json_print, pretty_json, color):
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
            entry = {"dst": re.sub(r"%.+$", "", cols[0])}
            if cols[1] != "(incomplete)":
                entry["lladdr"] = cols[1]
            entry["dev"] = cols[2]
            if dev and entry["dev"] != dev:
                continue
            if prefix and ipaddress.ip_address(entry["dst"]) not in prefix:
                continue
            if cols[1] == "(incomplete)" and cols[4] != "R":
                entry["state"] = ["INCOMPLETE"]
            else:
                entry["state"] = [nd_ll_states[cols[4]]]
            if len(cols) >= 6 and cols[5] == "R":
                # iproute2 outputs null in its json
                entry["router"] = None
            neighs.append(entry)

    if af != 6:
        args = [ARP, "-anl"]
        if dev:
            args += ["-i", dev]

        res = subprocess.run(args, capture_output=True, text=True, check=True)
        for row in res.stdout.splitlines()[1:]:
            cols = row.split()
            entry = {"dst": cols[0]}
            if cols[1] != "(incomplete)":
                entry["lladdr"] = cols[1]
            entry["dev"] = cols[4]
            if dev and entry["dev"] != dev:
                continue
            if prefix and ipaddress.ip_address(entry["dst"]) not in prefix:
                continue
            if cols[1] == "(incomplete)":
                entry["state"] = ["INCOMPLETE"]
            else:
                entry["state"] = ["REACHABLE"]
            # router field is ipv6 feature, iproute2 doesn't include router element if not set
            # entry["router"] = False
            neighs.append(entry)

    if json_print:
        return json_dump(neighs, pretty_json)

    for nb in neighs:
        print(
            colorize_inet(color, "inet6" if ":" in nb["dst"] else "inet", nb["dst"]) +
            ("" if nb["dev"] is None else " dev " + colorize_ifname(color, nb["dev"])) +
            ("" if "lladdr" not in nb else " lladdr " + colorize_mac(color, nb["lladdr"])) +
            (" router" if "router" in nb else "") +
            " %s" % (nb["state"][0])
        )

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
# https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/ip/ip.c#n86
cmds = [
    ("address", do_addr),
    ("route", do_route),
    ("neighbor", do_neigh),
    ("neighbour", do_neigh),
    ("link", do_link),
    ("help", do_help),
]


@help_msg(do_help)
def main(argv):
    af = -1  # default / both
    json_print = False
    pretty_json = False
    color_mode = "never"

    while argv and argv[0].startswith("-"):
        # Turn --opt into -opt
        argv[0] = argv[0][1 if argv[0][1] == '-' else 0:]
        # Process options
        if argv[0] == "-6":
            af = 6
            argv.pop(0)
        elif argv[0] == "-4":
            af = 4
            argv.pop(0)
        elif "-color".startswith(argv[0].split("=")[0]):
            # 'always' is default if -color is set without any value
            color_mode = argv[0].split("=")[1] if "=" in argv[0] else "always"
            if color_mode not in ["never", "always", "auto"]:
                perror('Option "{}" is unknown, try "ip -help".'.format(argv[0]))
                exit(255)
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
            perror('Option "{}" is unknown, try "ip -help".'.format(argv[0]))
            exit(255)

    if not argv:
        return False

    color_scheme = get_color_scheme(color_mode, json_print)

    for cmd, cmd_func in cmds:
        if cmd.startswith(argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(argv, af, json_print, pretty_json, color_scheme)

    perror('Object "{}" is unknown, try "ip help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

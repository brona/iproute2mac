#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
from operator import itemgetter

from iproute2mac import *


# Scope of an address, as iproute2 names it
def addr_scope(local):
    ip = ipaddress.ip_address(local)
    if ip.is_loopback:
        return "host"
    if ip.is_link_local:
        return "link"
    return "global"


# Operational state and carrier flags, as iproute2 shows them
def set_operstate(link, status):
    up = "UP" in link["flags"]
    if status is None:
        # no media status (lo0, gif, stf, utun, ...)
        carrier = "RUNNING" in link["flags"]
        link["operstate"] = "UNKNOWN" if up else "DOWN"
    else:
        carrier = status == "active"
        link["operstate"] = "UP" if up and carrier else "DOWN"
    if up:
        link["flags"].append("LOWER_UP" if carrier else "NO-CARRIER")


# Decode ifconfig output
def parse_ifconfig(res, af, address):
    links = []
    count = 1

    status = None
    for r in res.split("\n"):
        if re.match(r"^\w+:", r):
            if count > 1:
                set_operstate(link, status)
                links.append(link)
            status = None
            (ifname, flags, mtu, ifindex) = re.findall(
                r"^(\w+): flags=[\da-f]+<(.*)>.+mtu (\d+).+index (\d+)", r
            )[0]
            flags = flags.split(",")
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
            count = count + 1
        else:
            if re.match(r"^\s+ether ", r):
                link["link_type"] = "ether"
                link["address"] = re.findall(
                    r"(\w\w:\w\w:\w\w:\w\w:\w\w:\w\w)", r
                )[0]
                link["broadcast"] = "ff:ff:ff:ff:ff:ff"
            elif address and re.match(r"^\s+inet ", r) and af != 6:
                (local, peer, netmask) = re.findall(
                    r"inet (\d+\.\d+\.\d+\.\d+)(?: --> (\d+\.\d+\.\d+\.\d+))? netmask (0x[\da-f]+)",
                    r,
                )[0]
                addr = {
                    "family": "inet",
                    "local": local,
                    "prefixlen": netmask_to_length(netmask),
                }
                if peer:
                    addr["address"] = peer
                if re.match(r"^.*broadcast", r):
                    addr["broadcast"] = re.findall(
                        r"broadcast (\d+\.\d+\.\d+\.\d+)", r
                    )[0]
                addr["scope"] = addr_scope(local)
                link["addr_info"] = link.get("addr_info", []) + [addr]
            elif address and re.match(r"^\s+inet6 ", r) and af != 4:
                (local, peer, prefixlen) = re.findall(
                    r"inet6 ([\da-f:]*:[\da-f:]+)%*\w*(?: --> ([\da-f:]*:[\da-f:]+)%*\w*)? prefixlen (\d+)",
                    r,
                )[0]
                addr = {
                    "family": "inet6",
                    "local": local,
                    "prefixlen": int(prefixlen),
                }
                if peer:
                    addr["address"] = peer
                addr["scope"] = addr_scope(local)
                link["addr_info"] = link.get("addr_info", []) + [addr]
            elif match := re.search(r"^\s+status: (\w+)", r):
                status = match.group(1)

    if count > 1:
        set_operstate(link, status)
        links.append(link)

    return sorted(links, key=itemgetter("ifindex"))


def link_addr_show(
    argv, af, json_print, pretty_json, color, address, brief, oneline
):
    cmd = [IFCONFIG, "-v"]
    if "up" in argv:
        argv.remove("up")
        cmd.append("-u")

    # ip addr show [ dev STRING ] [ to PREFIX ]
    prefix = None
    if address and "to" in argv:
        at = argv.index("to")
        if at + 1 >= len(argv):
            return False
        try:
            prefix = ipaddress.ip_network(argv[at + 1], strict=False)
        except ValueError:
            perror(
                'Error: any valid prefix is expected rather than "%s".'
                % argv[at + 1]
            )
            exit(1)
        del argv[at : at + 2]

    names = names_load()
    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        cmd.append(kernel_ifname(argv[0], names))
    else:
        cmd.append("-a")

    output_separator = "\\" if oneline else "\n"

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        if cmd[-1] != "-a":
            perror('Device "%s" does not exist.' % argv[0])
            exit(1)
        perror((res.stderr + res.stdout).strip())
        return False

    links = parse_ifconfig(res.stdout, af, address)

    # the interfaces that "ip link add" created have the name it was given
    hidden = hidden_ifnames(names)
    aliases = ifname_aliases(names)
    links = [l for l in links if l["ifname"] not in hidden]
    for l in links:
        if aliases.get(l["ifname"], l["ifname"]) != l["ifname"]:
            l["altnames"] = [l["ifname"]]
            l["ifname"] = aliases[l["ifname"]]

    # Keep the addresses that are in the requested prefix
    if prefix is not None:
        for l in links:
            l["addr_info"] = [
                a
                for a in l.get("addr_info", [])
                if ipaddress.ip_address(a["local"]).version == prefix.version
                and ipaddress.ip_address(a["local"]) in prefix
            ]

    # Filter out interfaces with no addresses of the requested family or prefix
    if address and (af in (4, 6) or prefix is not None):
        links = [l for l in links if l.get("addr_info")]

    if json_print:
        return json_dump(links, pretty_json)

    for l in links:
        # Brief format: interface_name STATUS ip_addresses...
        if brief:
            # Interface name and state (right-padded to align)
            line = (
                colorize_ifname(color, l["ifname"], 16)
                + " "
                + colorize_op_state(color, l["operstate"], 8)
            )

            # Add addresses
            addrs = []
            for a in l.get("addr_info", []):
                addrs.append(
                    "%s/%d"
                    % (
                        colorize_inet(color, a["family"], a["local"]),
                        a["prefixlen"],
                    )
                )

            # For `ip link` output
            if not address:
                #  Add MAC address
                if "address" in l:
                    addrs.append(colorize_mac(color, l["address"]))
                # Add state flags if set
                if len(l["flags"]) > 0 and l["flags"] != [""]:
                    addrs.append("<%s>" % ",".join(l["flags"]))

            if addrs:
                line += (" " * 7) + " ".join(addrs)
            print(line)
        # Regular and oneline format
        else:
            lines = []
            # Interface header printed only for `ip link` or `ip address` without -oneline
            if not address or (address and not oneline):
                lines.append(
                    "%d: %s: %smtu %d state %s"
                    % (
                        l["ifindex"],
                        colorize_ifname(color, l["ifname"]),
                        (
                            "<" + ",".join(l["flags"]) + "> "
                            if len(l["flags"]) > 0 and l["flags"] != [""]
                            else ""
                        ),
                        l["mtu"],
                        colorize_op_state(color, l["operstate"]),
                    )
                )
                lines.append(
                    "    link/"
                    + l["link_type"]
                    + (
                        (" " + colorize_mac(color, l["address"]))
                        if "address" in l
                        else ""
                    )
                    + (
                        (" brd " + colorize_mac(color, l["broadcast"]))
                        if "broadcast" in l
                        else ""
                    )
                )
                for altname in l.get("altnames", []):
                    lines.append("    altname " + altname)
                print(output_separator.join(lines))

            for a in l.get("addr_info", []):
                print(
                    (
                        "%d: %s"
                        % (l["ifindex"], colorize_ifname(color, l["ifname"]))
                        if address and oneline
                        else ""
                    )
                    + "    %s %s"
                    % (
                        a["family"],
                        colorize_inet(color, a["family"], a["local"]),
                    )
                    + (
                        (
                            " peer %s"
                            % colorize_inet(color, a["family"], a["address"])
                        )
                        if "address" in a
                        else ""
                    )
                    + "/%d" % (a["prefixlen"])
                    + (
                        (
                            " brd "
                            + colorize_inet(color, a["family"], a["broadcast"])
                        )
                        if "broadcast" in a
                        else ""
                    )
                    + " scope %s" % a["scope"]
                )

    return True


# Help
def do_help(
    argv=None,
    af=None,
    json_print=None,
    pretty_json=None,
    color=None,
    brief=None,
    oneline=None,
):
    perror("Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link | addr | route | neigh }")
    perror("       OPTIONS := { -V[ersion] | -j[son] | -p[retty] | -c[olor] |")
    perror("                    -br[ief] | -o[neline] | -4 | -6 }")
    perror(HELP_ADDENDUM)
    exit(255)


def do_help_route():
    perror("Usage: ip route list [[exact] PREFIX]")
    perror("       ip route get ADDRESS")
    perror("       ip route { add | del | replace | change } ROUTE")
    perror("       ip route flush cache")
    perror("       ip route flush table main")
    perror("ROUTE := NODE_SPEC [ INFO_SPEC ]")
    perror("NODE_SPEC := [ TYPE ] PREFIX [ table main ] [ proto static ]")
    perror("INFO_SPEC := NH [ src ADDRESS ] [ mtu [ lock ] NUMBER ]")
    perror("TYPE := { unicast | blackhole | unreachable | prohibit }")
    perror("NH := { via ADDRESS | gw ADDRESS | nexthop ADDRESS }")
    perror("      [ dev STRING ] | dev STRING")
    exit(255)


def do_help_addr():
    perror("Usage: ip addr show [ dev STRING ] [ to PREFIX ] [up]")
    perror("       ip addr { add | del } PREFIX dev STRING")
    perror("       ip addr flush [ dev ] STRING [ scope SCOPE ] [ to PREFIX ]")
    exit(255)


def do_help_link():
    perror("Usage: ip link add [ link DEV ] [ name ] NAME [ address LLADDR ]")
    perror("                   [ mtu MTU ] type TYPE [ ARGS ]")
    perror("       ip link delete [ dev ] DEVICE")
    perror("       ip link set dev DEVICE")
    perror("                [ { up | down } ]")
    perror("                [ address { LLADDR | factory | random } ]")
    perror("                [ mtu MTU ]")
    perror("                [ master DEVICE | nomaster ]")
    perror("       ip link show [ DEVICE ] [up]")
    perror("TYPE := { dummy | veth [ peer [ name ] NAME ] | vlan id ID |")
    perror("          bridge | bond [ mode 802.3ad ] }")
    exit(255)


def do_help_neigh():
    perror("Usage: ip neighbour { add | del | change | replace }")
    perror("                    ADDR [ lladdr LLADDR ] [ nud STATE ] dev DEV")
    perror("       ip neighbour show [ [ to ] PREFIX ] [ dev DEV ]")
    perror("       ip neighbour flush [ [ to ] PREFIX ] [ dev DEV ]")
    perror("STATE := { permanent | reachable | stale | delay | probe }")
    exit(255)


# Route Module
@help_msg(do_help_route)
def do_route(argv, af, json_print, pretty_json, color, brief, oneline):
    if not argv or (
        any_startswith(["show", "lst", "list"], argv[0]) and len(argv) <= 3
    ):
        if argv:
            argv.pop(0)
        return do_route_list(argv, af, json_print, pretty_json, color)
    elif strict_startswith("get", argv[0]) and len(argv) == 2:
        argv.pop(0)
        return do_route_get(argv, af, json_print, pretty_json, color)
    elif strict_startswith("add", argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_route_add(argv, af)
    elif strict_startswith("delete", argv[0]) and len(argv) >= 2:
        argv.pop(0)
        return do_route_del(argv, af)
    elif strict_startswith("replace", argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_route_replace(argv, af)
    elif strict_startswith("change", argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_route_change(argv, af)
    elif strict_startswith("flush", argv[0]) and len(argv) >= 1:
        argv.pop(0)
        return do_route_flush(argv, af)
    else:
        return False
    return True


def do_route_list(argv, af, json_print, pretty_json, color):
    # argv can have SELECTOR = [[exact] PREFIX]
    argc = len(argv)
    if argc == 0:
        exact = ""
    elif argc == 1:
        exact = argv[0]
    elif argc == 2 and argv[0] == "exact":
        exact = argv[1]
    else:
        return False

    # ip route prints IPv6 or IPv4, never both
    inet = "inet6" if af == 6 else "inet"
    res = subprocess.run(
        [NETSTAT, "-nr", "-f", inet], capture_output=True, text=True
    )
    if res.returncode != 0:
        perror((res.stderr + res.stdout).strip())
        return False
    lines = res.stdout.split("\n")
    lines = lines[4:]  # Removes first 4 lines

    routes = []

    for r in lines:
        if not r.strip():
            continue
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
        if flags.find("R") != -1:
            routes.append({"type": "unreachable", "dst": target, "flags": []})
            continue
        if re.match(r"link.+", gw):
            routes.append(
                {"dst": target, "dev": dev, "scope": "link", "flags": []}
            )
        else:
            routes.append(
                {"dst": target, "gateway": gw, "dev": dev, "flags": []}
            )

    if exact:
        routes = [route for route in routes if route.get("dst") == exact]

    aliases = ifname_aliases()
    for route in routes:
        if route.get("dev") in aliases:
            route["dev"] = aliases[route["dev"]]

    if json_print:
        return json_dump(routes, pretty_json)

    for route in routes:
        if "type" in route:
            print(
                "%s %s"
                % (route["type"], colorize_inet(color, inet, route["dst"]))
            )
        elif "scope" in route:
            print(
                "%s dev %s scope %s"
                % (
                    colorize_inet(color, inet, route["dst"]),
                    colorize_ifname(color, route["dev"]),
                    route["scope"],
                )
            )
        elif "gateway" in route:
            print(
                "%s via %s dev %s"
                % (
                    colorize_inet(color, inet, route["dst"]),
                    colorize_inet(color, inet, route["gateway"]),
                    colorize_ifname(color, route["dev"]),
                )
            )

    return True


ROUTE_TYPES = {"unicast": None, "blackhole": "-blackhole"}
ROUTE_TYPES.update({"unreachable": "-reject", "prohibit": "-reject"})


def parse_route(argv, af):
    """
    Parse ROUTE := [ TYPE ] PREFIX [ INFO_SPEC ] of "ip route add | del |
    replace | change", return the route as a dict, or None.
    """
    argv = list(argv)
    route = {"type": "unicast"}
    if argv and argv[0] in ("throw", "local", "broadcast", "anycast", "nat"):
        not_implemented(argv[0], "macOS has no such route type")
    if argv and argv[0] in ROUTE_TYPES:
        route["type"] = argv.pop(0)
    if not argv:
        return None
    route["prefix"] = argv.pop(0)
    while argv:
        arg = argv.pop(0)
        if arg in ["via", "nexthop", "gw"] and argv:
            gateway = argv.pop(0)
            if arg == "nexthop" and gateway == "via" and argv:
                gateway = argv.pop(0)
            route["via"] = gateway
        elif arg in ["dev", "oif"] and argv:
            route["dev"] = kernel_ifname(argv.pop(0))
        elif arg == "src" and argv:
            route["src"] = argv.pop(0)
        elif arg == "mtu" and argv:
            if argv[0] == "lock":
                argv.pop(0)
                route["mtu_lock"] = True
            if not argv or not argv[0].isdigit():
                return None
            route["mtu"] = argv.pop(0)
        elif arg == "scope" and argv:
            # a route via a device only is scope link already
            argv.pop(0)
        elif arg in ["table", "proto", "protocol"] and argv:
            value = argv.pop(0)
            if arg == "table" and value not in ["main", "254"]:
                not_implemented("table", "macOS has one routing table")
            if arg != "table" and value not in ["static", "boot"]:
                not_implemented(arg, "macOS routes have no protocol")
        elif arg in ["metric", "preference", "priority"] and argv:
            not_implemented(arg, "macOS routes have no metric")
        elif arg == "onlink":
            not_implemented(arg, "macOS checks the gateway")
        else:
            return None
    route["inet6"] = (
        af == 6 or ":" in route["prefix"] or ":" in route.get("via", "")
    )
    return route


def route_gateway(route):
    """Gateway of a route for route(8), a link-local one scoped to dev."""
    gateway = route["via"]
    if route.get("dev") and gateway.lower().startswith("fe80:"):
        gateway += "%" + route["dev"]
    return gateway


def route_add_cmd(route, verb="add"):
    cmd = [SUDO, ROUTE, "-n", verb]
    if route["inet6"]:
        cmd.append("-inet6")
    cmd.append(route["prefix"])
    flag = ROUTE_TYPES[route["type"]]
    if flag:
        # macOS discard and reject routes go to the loopback
        cmd += ["::1" if route["inet6"] else "127.0.0.1", flag]
    elif "via" in route:
        cmd.append(route_gateway(route))
        if route.get("dev"):
            cmd += ["-ifp", route["dev"]]
    elif route.get("dev"):
        cmd += ["-interface", route["dev"]]
    else:
        perror("Error: either via or dev is expected.")
        exit(255)
    if route.get("src"):
        cmd += ["-ifa", route["src"]]
    if route.get("mtu"):
        if route.get("mtu_lock"):
            cmd.append("-lock")
        cmd += ["-mtu", route["mtu"]]
    return cmd


def route_del_cmd(route):
    cmd = [SUDO, ROUTE, "-n", "delete"]
    if route["inet6"]:
        cmd.append("-inet6")
    cmd.append(route["prefix"])
    if route["type"] == "unicast" and "via" in route:
        cmd.append(route_gateway(route))
    return cmd


def do_route_add(argv, af):
    route = parse_route(argv, af)
    if route is None:
        return False
    return execute_cmd(route_add_cmd(route))


def do_route_del(argv, af):
    route = parse_route(argv, af)
    if route is None:
        return False
    return execute_cmd(route_del_cmd(route))


def do_route_replace(argv, af):
    # create the route if it does not exist, like iproute2
    route = parse_route(argv, af)
    if route is None:
        return False
    execute_cmd(route_del_cmd(route), check=False)
    return execute_cmd(route_add_cmd(route))


def do_route_change(argv, af):
    route = parse_route(argv, af)
    if route is None:
        return False
    if route["type"] != "unicast":
        execute_cmd(route_del_cmd(route))
        return execute_cmd(route_add_cmd(route))
    return execute_cmd(route_add_cmd(route, "change"))


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
        return execute_cmd([SUDO, ROUTE, "-n", "flush", family])
    else:
        return False


def do_route_get(argv, af, json_print, pretty_json, color):
    target = argv[0]

    cmd = [ROUTE, "-n", "get"]
    if ":" in target or af == 6:
        cmd.append("-inet6")
        family = socket.AF_INET6
        color_af = "inet6"
    else:
        family = socket.AF_INET
        color_af = "inet"

    cmd.append(target)

    res = subprocess.run(cmd, capture_output=True, text=True)
    res_text = (
        (res.stderr + res.stdout).strip()
        if res.returncode != 0
        else res.stdout
    )
    if res.returncode != 0:
        perror(res_text)
        return False
    if res_text.find("not in table") >= 0:
        perror(res_text)
        exit(1)

    res = dict(
        re.findall(
            r"^\W*((?:route to|destination|gateway|interface)): (.+)$",
            res_text,
            re.MULTILINE,
        )
    )

    route = {"dst": res["route to"], "dev": res["interface"]}
    route["dev"] = ifname_aliases().get(route["dev"], route["dev"])

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
        colorize_inet(color, color_af, route["dst"])
        + (
            (" via " + colorize_inet(color, color_af, route["gateway"]))
            if "gateway" in route
            else ""
        )
        + " dev "
        + colorize_ifname(color, route["dev"])
        + (
            (" src " + colorize_inet(color, color_af, route["prefsrc"]))
            if "prefsrc" in route
            else ""
        )
        + " uid "
        + str(route["uid"])
    )

    return True


# Addr Module
@help_msg(do_help_addr)
def do_addr(argv, af, json_print, pretty_json, color, brief, oneline):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_addr_show(
            argv, af, json_print, pretty_json, color, brief, oneline
        )
    elif strict_startswith("add", argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_add(argv, af)
    elif strict_startswith("delete", argv[0]) and len(argv) >= 3:
        argv.pop(0)
        return do_addr_del(argv, af)
    elif strict_startswith("flush", argv[0]):
        argv.pop(0)
        return do_addr_flush(argv, af)
    else:
        return False
    return True


# Scopes of "ip addr flush ... scope SCOPE", numeric values of iproute2
ADDR_SCOPES = {
    "global": 0,
    "site": 200,
    "link": 253,
    "host": 254,
    "nowhere": 255,
}


def do_addr_flush(argv, af):
    # ip addr flush [ dev ] IFNAME [ scope SCOPE ] [ to PREFIX ]
    dev = None
    scope = None
    prefix = None
    try:
        while argv:
            arg = argv.pop(0)
            if arg == "dev":
                dev = argv.pop(0)
            elif arg == "scope":
                scope = argv.pop(0)
                if scope.isdigit():
                    names = {v: k for k, v in ADDR_SCOPES.items()}
                    scope = names[int(scope)]
                elif scope not in ADDR_SCOPES:
                    return False
            elif arg == "to":
                prefix = ipaddress.ip_network(argv.pop(0), strict=False)
            elif dev is None:
                dev = arg
            else:
                return False
    except (IndexError, KeyError, ValueError):
        return False
    if dev is None and scope is None and prefix is None:
        perror("Flush requires arguments.")
        exit(1)

    cmd = [IFCONFIG, "-v", kernel_ifname(dev) if dev else "-a"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        perror('Device "%s" does not exist.' % dev)
        exit(1)

    for link in parse_ifconfig(res.stdout, af, True):
        for a in link.get("addr_info", []):
            if scope is not None and a["scope"] != scope:
                continue
            local = ipaddress.ip_address(a["local"])
            if prefix is not None and (
                local.version != prefix.version or local not in prefix
            ):
                continue
            inet = "inet6" if local.version == 6 else "inet"
            execute_cmd(
                [SUDO, IFCONFIG, link["ifname"], inet, a["local"], "delete"]
            )
    return True


def do_addr_show(argv, af, json_print, pretty_json, color, brief, oneline):
    return link_addr_show(
        argv, af, json_print, pretty_json, color, True, brief, oneline
    )


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
        dev = kernel_ifname(argv[1])
    except IndexError:
        perror("dev not found")
        exit(1)
    cmd = [SUDO, IFCONFIG, dev]
    if ":" in addr or af == 6:
        af = 6
        cmd.append("inet6")
    cmd.extend(["add", addr])
    if dst:
        cmd.append(dst)
    return execute_cmd(cmd)


def do_addr_del(argv, af):
    if len(argv) < 2:
        return False
    if argv[1] == "dev":
        argv.pop(1)
    try:
        addr = argv[0]
        dev = kernel_ifname(argv[1])
    except IndexError:
        perror("dev not found")
        exit(1)
    inet = "inet"
    if ":" in addr or af == 6:
        af = 6
        inet = "inet6"
    return execute_cmd([SUDO, IFCONFIG, dev, inet, addr, "remove"])


# Link module
@help_msg(do_help_link)
def do_link(argv, af, json_print, pretty_json, color, brief, oneline):
    if not argv:
        argv.append("show")

    if strict_startswith("set", argv[0]):
        argv.pop(0)
        return do_link_set(argv, af)
    elif strict_startswith("add", argv[0]):
        argv.pop(0)
        return do_link_add(argv, af)
    elif strict_startswith("delete", argv[0]):
        argv.pop(0)
        return do_link_del(argv, af)
    elif any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(
            argv, af, json_print, pretty_json, color, brief, oneline
        )
    else:
        return False
    return True


def do_link_show(argv, af, json_print, pretty_json, color, brief, oneline):
    return link_addr_show(
        argv, af, json_print, pretty_json, color, False, brief, oneline
    )


def do_link_set(argv, af):
    if (
        not argv
        or not argv[0]
        or (argv[0] == "dev" and (len(argv) < 2 or not argv[1]))
    ):
        perror('Not enough information: "dev" argument is required.')
        return False

    if argv[0] == "dev":
        argv.pop(0)

    dev = argv[0] = kernel_ifname(argv[0])

    ifconfig_dev_cmd = [SUDO, IFCONFIG, dev]
    try:
        args = iter(argv)
        for arg in args:
            if arg in ["netns", "vrf"]:
                not_implemented(
                    arg, "macOS has no network namespaces nor VRFs"
                )
            elif arg == "name":
                not_implemented(arg, "macOS cannot rename an interface")
            elif arg == "master":
                link_set_master(dev, next(args))
            elif arg == "nomaster":
                link_set_nomaster(dev)
            if arg == "up":
                if not execute_cmd(ifconfig_dev_cmd + ["up"]):
                    return False
            elif arg == "down":
                if not execute_cmd(ifconfig_dev_cmd + ["down"]):
                    return False
            elif arg in ["address", "addr", "lladdr"]:
                addr = next(args)
                if addr in ["random", "rand"]:
                    addr = randomMAC()
                elif addr == "factory":
                    res = subprocess.run(
                        [NETWORKSETUP, "-listallhardwareports"],
                        capture_output=True,
                        text=True,
                    )
                    if res.returncode != 0:
                        return False
                    details = re.findall(
                        r"^(?:Device|Ethernet Address): (.+)$",
                        res.stdout,
                        re.MULTILINE,
                    )
                    addr = details[details.index(dev) + 1]
                if not execute_cmd(ifconfig_dev_cmd + ["lladdr", addr]):
                    return False
            elif arg == "mtu":
                mtu = int(next(args))
                if not execute_cmd(ifconfig_dev_cmd + ["mtu", str(mtu)]):
                    return False
    except Exception:
        return False
    return True


# Interfaces of "ip link add": the driver of macOS that implements a type
LINK_DRIVERS = {
    "dummy": "feth",
    "veth": "feth",
    "vlan": "vlan",
    "bridge": "bridge",
    "bond": "bond",
}


# The interfaces that "ip link add" gave to each name
UNITS_FILE = os.path.join(RUNDIR, "units.json")


def units_load():
    try:
        with open(UNITS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def clone_create(driver, existing, units, name=None):
    """
    Create an interface of a driver, return its name (feth0, ...).

    macOS would take the lowest free unit. Like on Linux, give a name its
    former interface again, and a new name an interface that no other name
    had, so that a routing daemon does not take an interface for another.
    A name of an interface of the driver (feth3) gets that interface.
    """
    ifname = units.get(name, "")
    if name and re.match(r"^%s\d+$" % driver, name) and name not in existing:
        ifname = name
    elif not re.match(r"^%s\d+$" % driver, ifname) or ifname in existing:
        taken = existing | set(units.values())
        unit = 0
        while "%s%d" % (driver, unit) in taken:
            unit += 1
        ifname = "%s%d" % (driver, unit)
    execute_cmd([SUDO, IFCONFIG, ifname, "create"])
    existing.add(ifname)
    if name:
        units[name] = ifname
    return ifname


def random_laa():
    """A random locally administered MAC address, like Linux gives to a new
    dummy or veth (all feth interfaces of macOS start with the same one)."""
    mac = [random.randint(0x00, 0xFF) for _ in range(6)]
    mac[0] = (mac[0] & 0xFC) | 0x02
    return ":".join("%02x" % x for x in mac)


def do_link_add(argv, af):
    # ip link add [ link DEV ] [ name ] NAME [ address LLADDR ] [ mtu MTU ]
    #             type TYPE [ ARGS ]
    names = names_load()
    name = parent = lladdr = mtu = kind = None
    while argv:
        arg = argv.pop(0)
        if arg == "type" and argv:
            kind = argv.pop(0)
            break
        elif arg == "link" and argv:
            parent = kernel_ifname(argv.pop(0), names)
        elif arg in ["name", "dev"] and argv:
            name = argv.pop(0)
        elif arg in ["address", "addr", "lladdr"] and argv:
            lladdr = argv.pop(0)
        elif arg == "mtu" and argv:
            mtu = argv.pop(0)
        elif name is None:
            name = arg
        else:
            return False
    if name is None or kind is None:
        return False
    if kind not in LINK_DRIVERS:
        not_implemented("type " + kind, "macOS has no such interface")

    # ARGS of the type
    peer = vlan_id = None
    while argv:
        arg = argv.pop(0)
        if kind == "veth" and arg == "peer" and argv:
            if argv[0] == "name":
                argv.pop(0)
            if not argv:
                return False
            peer = argv.pop(0)
        elif kind == "vlan" and arg == "id" and argv:
            vlan_id = argv.pop(0)
        elif kind == "vlan" and arg == "protocol" and argv:
            if argv.pop(0).lower() != "802.1q":
                not_implemented("protocol", "macOS VLANs are 802.1Q")
        elif kind == "bond" and arg == "mode" and argv:
            if argv.pop(0) not in ["802.3ad", "4"]:
                not_implemented("mode", "macOS bonds are 802.3ad (LACP)")
        elif kind == "bridge" and arg in ["stp_state", "vlan_filtering"]:
            if not argv or argv.pop(0) != "0":
                not_implemented(arg, "macOS bridges have no such option")
        else:
            not_implemented(
                arg, "macOS %s interfaces have no such option" % kind
            )
    if kind == "vlan" and (parent is None or vlan_id is None):
        perror('Error: "link" and "id" are required for a vlan.')
        exit(255)
    if kind == "veth" and peer is None:
        peer = "veth%d" % len([k for k in names if k.startswith("veth")])

    existing = set(
        subprocess.run([IFCONFIG, "-l"], capture_output=True, text=True)
        .stdout.split()
    )
    for n in [name] + ([peer] if peer else []):
        if len(n) > 15 or not n:
            perror(
                'Error: argument "%s" is wrong: "name" not a valid ifname' % n
            )
            exit(255)
        if n in names or n in existing:
            perror("RTNETLINK answers: File exists")
            exit(2)

    driver = LINK_DRIVERS[kind]
    units = units_load()
    ifname = clone_create(driver, existing, units, name)
    entry = {"ifname": ifname, "kind": kind}
    if kind == "dummy":
        # a feth has a carrier when it has a peer: give it a hidden one
        entry["hidden"] = clone_create("feth", existing, units)
        execute_cmd([SUDO, IFCONFIG, ifname, "peer", entry["hidden"]])
    elif kind == "veth":
        peer_ifname = clone_create("feth", existing, units, peer)
        execute_cmd([SUDO, IFCONFIG, ifname, "peer", peer_ifname])
        entry["peer"] = peer
        names[peer] = {"ifname": peer_ifname, "kind": kind, "peer": name}
    elif kind == "vlan":
        execute_cmd(
            [SUDO, IFCONFIG, ifname, "vlan", vlan_id, "vlandev", parent]
        )
    names[name] = entry
    names_save(names)
    save_state(UNITS_FILE, units)
    if kind in ["dummy", "veth"]:
        execute_cmd([SUDO, IFCONFIG, ifname, "lladdr", lladdr or random_laa()])
        if kind == "veth":
            execute_cmd(
                [SUDO, IFCONFIG, names[peer]["ifname"], "lladdr", random_laa()]
            )
    elif lladdr:
        execute_cmd([SUDO, IFCONFIG, ifname, "lladdr", lladdr])
    if mtu:
        execute_cmd([SUDO, IFCONFIG, ifname, "mtu", mtu])
    return True


def do_link_del(argv, af):
    # ip link del [ dev ] NAME [ type TYPE ]
    if argv and argv[0] == "dev":
        argv.pop(0)
    if not argv:
        return False
    name = argv.pop(0)
    if argv and (argv[0] != "type" or len(argv) != 2):
        return False
    names = names_load()
    entry = names.get(name)
    ifname = entry["ifname"] if entry else name
    existing = subprocess.run(
        [IFCONFIG, "-l"], capture_output=True, text=True
    ).stdout.split()
    if ifname not in existing:
        perror('Cannot find device "%s"' % name)
        exit(1)

    destroy = [ifname]
    if entry:
        if entry.get("hidden"):
            destroy.append(entry["hidden"])
        # deleting an end of a veth deletes the pair
        peer = entry.get("peer")
        if peer in names:
            destroy.append(names.pop(peer)["ifname"])
        names.pop(name)
    for i in destroy:
        execute_cmd([SUDO, IFCONFIG, i, "destroy"])
    if entry:
        names_save(names)
    return True


def master_kind(ifname, names=None):
    """Kind of a bridge or bond interface, by its macOS name."""
    for entry in (names or names_load()).values():
        if entry["ifname"] == ifname and entry["kind"] in ["bridge", "bond"]:
            return entry["kind"]
    for kind in ["bridge", "bond"]:
        if re.match(r"^%s\d+$" % kind, ifname):
            return kind
    return None


def link_set_master(dev, master):
    names = names_load()
    kmaster = kernel_ifname(master, names)
    kind = master_kind(kmaster, names)
    if kind == "bridge":
        execute_cmd([SUDO, IFCONFIG, kmaster, "addm", dev])
    elif kind == "bond":
        execute_cmd([SUDO, IFCONFIG, kmaster, "bonddev", dev])
    else:
        not_implemented(
            "master " + master, "only a bridge or a bond can be a master"
        )


def link_set_nomaster(dev):
    ifnames = subprocess.run(
        [IFCONFIG, "-l"], capture_output=True, text=True
    ).stdout.split()
    for ifname in ifnames:
        kind = master_kind(ifname)
        if kind is None:
            continue
        out = subprocess.run(
            [IFCONFIG, ifname], capture_output=True, text=True
        ).stdout
        if kind == "bridge" and re.search(
            r"member: %s " % re.escape(dev), out
        ):
            execute_cmd([SUDO, IFCONFIG, ifname, "deletem", dev])
        elif kind == "bond" and re.search(
            r"bond interfaces:.* %s\b" % re.escape(dev), out
        ):
            execute_cmd([SUDO, IFCONFIG, ifname, "-bonddev", dev])


# Neigh module
@help_msg(do_help_neigh)
def do_neigh(argv, af, json_print, pretty_json, color, brief, oneline):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "list", "lst"], argv[0]) and len(argv) <= 5:
        argv.pop(0)
        return do_neigh_show(argv, af, json_print, pretty_json, color)
    elif strict_startswith("flush", argv[0]):
        argv.pop(0)
        return do_neigh_flush(argv, af)
    elif strict_startswith("add", argv[0]):
        argv.pop(0)
        return do_neigh_modify("add", argv, af)
    elif strict_startswith("delete", argv[0]):
        argv.pop(0)
        return do_neigh_modify("del", argv, af)
    elif strict_startswith("change", argv[0]) or argv[0] == "chg":
        argv.pop(0)
        return do_neigh_modify("change", argv, af)
    elif strict_startswith("replace", argv[0]):
        argv.pop(0)
        return do_neigh_modify("replace", argv, af)
    else:
        return False


def mac_linux(mac):
    """A MAC address as iproute2 prints it: 2:0:0:0:2:a -> 02:00:00:00:02:0a"""
    try:
        return ":".join("%02x" % int(x, 16) for x in mac.split(":"))
    except ValueError:
        return mac


def neigh_list(af, dev=None, prefix=None):
    """
    Neighbours on dev (a macOS name) with their address in prefix. "_name" is
    the address that arp(8) or ndp(8) takes.
    """
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
                entry["lladdr"] = mac_linux(cols[1])
            entry["dev"] = cols[2]
            if dev and entry["dev"] != dev:
                continue
            if prefix and ipaddress.ip_address(entry["dst"]) not in prefix:
                continue
            if cols[1] == "(incomplete)" and cols[4] != "R":
                entry["state"] = ["INCOMPLETE"]
            elif cols[3] == "permanent":
                entry["state"] = ["PERMANENT"]
            else:
                entry["state"] = [nd_ll_states[cols[4]]]
            if len(cols) >= 6 and cols[5] == "R":
                # iproute2 outputs null in its json
                entry["router"] = None
            entry["_name"] = cols[0]
            neighs.append(entry)

    if af != 6:
        args = [ARP, "-an"]
        if dev:
            args += ["-i", dev]

        res = subprocess.run(args, capture_output=True, text=True, check=True)
        for row in res.stdout.splitlines():
            # ? (192.0.2.2) at 2:0:0:0:2:2 on en0 ifscope permanent [ethernet]
            m = re.match(r"^\S+ \(([\d.]+)\) at (\S+) on (\S+)(.*)$", row)
            if not m:
                continue
            entry = {"dst": m.group(1)}
            if m.group(2) != "(incomplete)":
                entry["lladdr"] = mac_linux(m.group(2))
            entry["dev"] = m.group(3)
            if dev and entry["dev"] != dev:
                continue
            if prefix and ipaddress.ip_address(entry["dst"]) not in prefix:
                continue
            if m.group(2) == "(incomplete)":
                entry["state"] = ["INCOMPLETE"]
            elif "permanent" in m.group(4).split():
                entry["state"] = ["PERMANENT"]
            else:
                entry["state"] = ["REACHABLE"]
            # router field is ipv6 feature, iproute2 doesn't include router element if not set
            # entry["router"] = False
            entry["_name"] = entry["dst"]
            neighs.append(entry)

    return neighs


def neigh_dev(name):
    """macOS name of the device of a neighbour, which must exist."""
    dev = kernel_ifname(name)
    ifnames = subprocess.run(
        [IFCONFIG, "-l"], capture_output=True, text=True
    ).stdout.split()
    if dev not in ifnames:
        perror('Cannot find device "%s"' % name)
        exit(1)
    return dev


def parse_neigh_selector(argv):
    """[ [ to ] PREFIX ] [ dev DEV ] of "ip neigh show" and "flush"."""
    prefix = None
    dev = None
    try:
        while argv:
            arg = argv.pop(0)
            if arg == "to":
                prefix = argv.pop(0)
            elif arg == "dev":
                dev = argv.pop(0)
            elif arg == "nud":
                not_implemented(
                    arg, "neighbours are selected by address and dev"
                )
            elif prefix is None:
                prefix = arg
            else:
                return None
        if prefix:
            prefix = ipaddress.ip_network(prefix, strict=False)
    except (IndexError, ValueError):
        return None
    if dev:
        dev = neigh_dev(dev)
    return (prefix, dev)


def do_neigh_show(argv, af, json_print, pretty_json, color):
    selector = parse_neigh_selector(argv)
    if selector is None:
        return False
    prefix, dev = selector

    neighs = neigh_list(af, dev, prefix)
    aliases = ifname_aliases()
    for nb in neighs:
        nb.pop("_name")
        nb["dev"] = aliases.get(nb["dev"], nb["dev"])

    if json_print:
        return json_dump(neighs, pretty_json)

    for nb in neighs:
        print(
            colorize_inet(
                color, "inet6" if ":" in nb["dst"] else "inet", nb["dst"]
            )
            + (
                ""
                if nb["dev"] is None
                else " dev " + colorize_ifname(color, nb["dev"])
            )
            + (
                ""
                if "lladdr" not in nb
                else " lladdr " + colorize_mac(color, nb["lladdr"])
            )
            + (" router" if "router" in nb else "")
            + " %s" % (nb["state"][0])
        )

    return True


def neigh_delete(nb):
    if ":" in nb["dst"]:
        # ndp(8) deletes the first of the entries of the address
        return execute_cmd([SUDO, NDP, "-d", nb["_name"]])
    return execute_cmd([SUDO, ARP, "-d", nb["_name"], "ifscope", nb["dev"]])


def do_neigh_flush(argv, af):
    if not argv:
        perror("Flush requires arguments.")
        exit(1)
    selector = parse_neigh_selector(argv)
    if selector is None:
        return False
    prefix, dev = selector

    # like iproute2, keep the permanent entries, the addresses of macOS too
    for nb in neigh_list(af, dev, prefix):
        if nb["state"] != ["PERMANENT"]:
            neigh_delete(nb)
    return True


NUD_STATES = {
    "permanent": [],
    "reachable": ["temp"],
    "stale": ["temp"],
    "delay": ["temp"],
    "probe": ["temp"],
}


def do_neigh_modify(cmd, argv, af):
    # ip neigh { add | del | change | replace } [ to ] ADDR
    #          [ lladdr LLADDR ] [ nud STATE ] dev DEV
    dst = lladdr = dev = None
    nud = "permanent"
    while argv:
        arg = argv.pop(0)
        if arg == "lladdr" and argv:
            lladdr = argv.pop(0)
        elif arg == "nud" and argv:
            nud = argv.pop(0)
        elif arg == "dev" and argv:
            dev = argv.pop(0)
        elif arg in ["proxy", "router", "extern_learn", "managed", "use"]:
            not_implemented(arg, "macOS neighbours have no such flag")
        elif arg in ["protocol", "proto"]:
            not_implemented(arg, "macOS neighbours have no protocol")
        elif dst is None:
            if arg == "to" and argv:
                arg = argv.pop(0)
            dst = arg
        else:
            return False
    if dst is None or dev is None:
        perror("Device and destination are required arguments.")
        exit(255)
    try:
        addr = ipaddress.ip_address(dst)
    except ValueError:
        perror('Error: any valid address is expected rather than "%s".' % dst)
        exit(1)
    if af in (4, 6) and af != addr.version:
        return False
    if nud not in NUD_STATES:
        not_implemented("nud " + nud, "macOS has static and expiring entries")
    if cmd != "del" and lladdr is None:
        not_implemented(
            "ip neigh %s without lladdr" % cmd,
            "a neighbour of macOS needs its link layer address",
        )
    dev = neigh_dev(dev)
    prefix = ipaddress.ip_network(addr)

    existing = neigh_list(addr.version, dev, prefix)
    if cmd == "add" and existing:
        perror("RTNETLINK answers: File exists")
        exit(2)
    if cmd in ["del", "change"] and not existing:
        perror("RTNETLINK answers: No such file or directory")
        exit(2)

    if addr.version == 4:
        if cmd == "del":
            return execute_cmd([SUDO, ARP, "-d", dst, "ifscope", dev])
        # arp(8) replaces an existing entry
        return execute_cmd(
            [SUDO, ARP, "-s", dst, lladdr] + NUD_STATES[nud] + ["ifscope", dev]
        )

    for nb in existing:
        neigh_delete(nb)
    if cmd == "del":
        return True
    name = dst
    if addr.is_link_local:
        name += "%" + dev
    else:
        # ndp(8) adds the entry to the interface of the route to dst
        res = subprocess.run(
            [ROUTE, "-n", "get", "-inet6", dst], capture_output=True, text=True
        )
        m = re.search(r"interface: (\S+)", res.stdout)
        if not m or m.group(1) != dev:
            not_implemented(
                "dev", "macOS puts a neighbour on the interface of its route"
            )
    execute_cmd([SUDO, NDP, "-s", name, lladdr] + NUD_STATES[nud])
    # the lookup of ndp(8) leaves an empty entry of dst, which comes first
    # and hides the new one: delete it
    added = neigh_list(6, dev, prefix)
    if [nb for nb in added if "lladdr" not in nb]:
        execute_cmd([SUDO, NDP, "-d", name])
        added = neigh_list(6, dev, prefix)
    if not [nb for nb in added if nb.get("lladdr") == mac_linux(lladdr)]:
        perror("iproute2mac: ndp(8) did not add the neighbour.")
        exit(2)
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
    brief = False
    color_mode = "never"
    oneline = False

    while argv and argv[0].startswith("-"):
        if argv[0] == "-":
            do_help()
        elif argv[0] == "--":
            argv.pop(0)
            break
        # Turn --opt into -opt
        elif argv[0][1] == "-":
            argv[0] = argv[0][1:]

        # Process options
        if argv[0] == "-6":
            af = 6
            argv.pop(0)
        elif argv[0] == "-4":
            af = 4
            argv.pop(0)
        elif strict_startswith("-batch", argv[0]):
            perror('iproute2mac: "ip -batch" is not implemented')
            exit(255)
        elif strict_startswith("-brief", argv[0]):
            brief = True
            argv.pop(0)
        elif strict_startswith("-oneline", argv[0]):
            oneline = True
            argv.pop(0)
        elif strict_startswith("-color", argv[0].split("=")[0]):
            # 'always' is default if -color is set without any value
            color_mode = argv[0].split("=")[1] if "=" in argv[0] else "always"
            if color_mode not in ["never", "always", "auto"]:
                perror(
                    'Option "{}" is unknown, try "ip -help".'.format(argv[0])
                )
                exit(255)
            argv.pop(0)
        elif strict_startswith("-json", argv[0]):
            json_print = True
            argv.pop(0)
        elif strict_startswith("-pretty", argv[0]):
            pretty_json = True
            argv.pop(0)
        elif strict_startswith("-Version", argv[0]):
            print("iproute2mac, v" + VERSION)
            exit(0)
        elif strict_startswith("-help", argv[0]):
            return False
        else:
            perror('Option "{}" is unknown, try "ip -help".'.format(argv[0]))
            exit(255)

    if not argv:
        return False

    color_scheme = get_color_scheme(color_mode, json_print)

    for cmd, cmd_func in cmds:
        if strict_startswith(cmd, argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(
                argv, af, json_print, pretty_json, color_scheme, brief, oneline
            )

    perror('Object "{}" is unknown, try "ip help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

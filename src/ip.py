#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import ipaddress
import os
import re
import signal
import socket
import subprocess
import sys

from iproute2mac import *


# Decode ifconfig output
def parse_ifconfig(res, af, address):
    return parse_ifconfig_links(
        res, af=af, address=address, sort_by_ifindex=True
    )


def link_addr_show(
    argv, af, json_print, pretty_json, color, address, brief, oneline
):
    cmd = [IFCONFIG, "-v"]
    if "up" in argv:
        argv.remove("up")
        cmd.append("-u")

    if len(argv) > 0 and argv[0] == "dev":
        argv.pop(0)
    if len(argv) > 0:
        cmd.append(argv[0])
    else:
        cmd.append("-a")

    output_separator = "\\" if oneline else "\n"

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        out = (res.stderr + res.stdout).strip()
        if out == "":
            perror(" ".join(cmd[2:]) + " not found")
        else:
            perror(out)
        return False

    links = parse_ifconfig(res.stdout, af, address)

    # Filter out interfaces with no addresses of the requested family
    if address and af in (4, 6):
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
                    "%d: %s: %smtu %d status %s"
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
    perror("Usage: ip addr show [ dev STRING ] [up]")
    perror("       ip addr { add | del } PREFIX dev STRING")
    exit(255)


def do_help_link():
    perror("Usage: ip link set dev DEVICE")
    perror("                [ { up | down } ]")
    perror("                [ address { LLADDR | factory | random } ]")
    perror("                [ mtu MTU ]")
    perror("       ip link show [ DEVICE ] [up]")
    exit(255)


def do_help_neigh():
    perror("Usage: ip neighbour show [ [ to ] PREFIX ] [ dev DEV ]")
    perror("       ip neighbour flush [ dev DEV ]")
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
        if len(ra) < 4:
            continue
        target = ra[0]
        gw = ra[1]
        flags = ra[2]
        # macOS Mojave and earlier vs Catalina
        dev = ra[5] if len(ra) >= 6 else ra[3]
        if flags.find("W") != -1:
            continue
        if af == 6:
            target = re.sub(r"%[^ /]+", "", target)
        else:
            target = cidr_from_netstat_dst(target)
        if flags.find("B") != -1:
            routes.append({"type": "blackhole", "dst": target, "flags": []})
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


def do_route_add(argv, af):
    is_blackhole = False
    if argv[0] == "blackhole":
        argv.pop(0)
        if len(argv) != 1:
            return False
        argv.append("via")
        argv.append("::1" if ":" in argv[0] or af == 6 else "127.0.0.1")
        is_blackhole = True

    if len(argv) not in (3, 5):
        return False

    if len(argv) == 5:
        perror(
            "iproute2mac: Ignoring last 2 arguments, not implemented: {} {}".format(
                argv[3], argv[4]
            )
        )

    prefix = argv[0]
    cmd = [SUDO, ROUTE, "add"]
    if ":" in prefix or af == 6:
        cmd.append("-inet6")

    cmd.append(prefix)

    if argv[1] in ["via", "nexthop", "gw"]:
        cmd.append(argv[2])
    elif argv[1] in ["dev"]:
        cmd.extend(["-interface", argv[2]])
    else:
        return False

    if is_blackhole:
        cmd.append("-blackhole")

    return execute_cmd(cmd)


def do_route_replace(argv, af):
    # Validate arguments before deleting any existing route.
    check = list(argv)
    if check[0] == "blackhole":
        if len(check) != 2:
            return False
    elif len(check) not in (3, 5) or check[1] not in [
        "via",
        "nexthop",
        "gw",
        "dev",
    ]:
        return False

    # Delete existing route if present (ignore failure when route is new),
    # passing a copy so blackhole argument parsing does not mutate argv.
    do_route_del(list(argv), af)
    return do_route_add(argv, af)


def do_route_del(argv, af):
    blackhole_args = []
    if argv[0] == "blackhole":
        argv.pop(0)
        if len(argv) != 1:
            return False
        if ":" in argv[0] or af == 6:
            blackhole_args = ["::1", "-blackhole"]
        else:
            blackhole_args = ["127.0.0.1", "-blackhole"]

    prefix = argv[0]
    cmd = [SUDO, ROUTE, "delete"]
    if ":" in prefix or af == 6:
        cmd.append("-inet6")

    cmd.append(prefix)
    cmd.extend(blackhole_args)
    return execute_cmd(cmd)


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

    if "route to" not in res or "interface" not in res:
        perror(res_text.strip())
        return False

    route = {"dst": res["route to"], "dev": res["interface"]}

    if "gateway" in res:
        route["gateway"] = res["gateway"]

    try:
        with socket.socket(family, socket.SOCK_DGRAM) as s:
            s.connect((route["dst"], 7))
            route["prefsrc"] = s.getsockname()[0]
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
    else:
        return False
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
        if len(argv) < 3:
            return False
        argv.pop(1)
        dst = argv.pop(1)

    if len(argv) < 2 or argv[1] != "dev":
        return False
    argv.pop(1)

    try:
        addr = argv[0]
        dev = argv[1]
    except IndexError:
        perror("dev not found")
        exit(1)
    if len(argv) > 2:
        return False

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
    if argv[1] != "dev":
        return False
    argv.pop(1)
    try:
        addr = argv[0]
        dev = argv[1]
    except IndexError:
        perror("dev not found")
        exit(1)
    if len(argv) > 2:
        return False
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

    dev = argv.pop(0)

    ifconfig_dev_cmd = [SUDO, IFCONFIG, dev]
    try:
        args = iter(argv)
        for arg in args:
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
                    addr = None
                    for stanza in res.stdout.split("\n\n"):
                        dev_match = re.search(
                            r"^Device: (.+)$", stanza, re.MULTILINE
                        )
                        mac_match = re.search(
                            r"^Ethernet Address: (.+)$", stanza, re.MULTILINE
                        )
                        if (
                            dev_match
                            and dev_match.group(1) == dev
                            and mac_match
                        ):
                            addr = mac_match.group(1)
                            break
                    if not addr or addr == "N/A":
                        perror(
                            "Factory MAC address not found for {}".format(dev)
                        )
                        return False
                if not execute_cmd(ifconfig_dev_cmd + ["lladdr", addr]):
                    return False
            elif arg == "mtu":
                mtu = int(next(args))
                if not execute_cmd(ifconfig_dev_cmd + ["mtu", str(mtu)]):
                    return False
            else:
                perror('Option "{}" is unknown, try "ip link help".'.format(arg))
                return False
    except StopIteration:
        perror("Missing argument value.")
        return False
    except ValueError as e:
        perror("Invalid argument: {}".format(e))
        return False
    return True


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
        res = subprocess.run([NDP, "-an"], capture_output=True, text=True)
        if res.returncode != 0:
            perror((res.stderr + res.stdout).strip())
            return False
        for row in res.stdout.splitlines()[1:]:
            cols = row.split()
            if len(cols) < 5:
                continue
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
                entry["state"] = [nd_ll_states.get(cols[4], "UNKNOWN")]
            if len(cols) >= 6 and cols[5] == "R":
                # iproute2 outputs null in its json
                entry["router"] = None
            neighs.append(entry)

    if af != 6:
        args = [ARP, "-anl"]
        if dev:
            args += ["-i", dev]

        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode != 0:
            perror((res.stderr + res.stdout).strip())
            return False
        for row in res.stdout.splitlines()[1:]:
            cols = row.split()
            if len(cols) < 5:
                continue
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


def do_neigh_flush(argv, af):
    if len(argv) != 2:
        perror("Flush requires arguments.")
        return False

    if argv[0] != "dev":
        return False
    dev = argv[1]

    ok = True
    if af != 4:
        print(
            "iproute2mac: NDP doesn't support filtering by interface, "
            "flushing all IPv6 entries."
        )
        ok = execute_cmd([SUDO, NDP, "-cn"]) and ok
    if af != 6:
        ok = execute_cmd([SUDO, ARP, "-a", "-d", "-i", dev]) and ok
    return ok


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
    opts = parse_cli_options(
        argv, "ip", do_help, allow_af=True, allow_brief=True, allow_batch=True
    )
    if opts is None or not argv:
        return False

    color_scheme = get_color_scheme(opts["color_mode"], opts["json_print"])

    for cmd, cmd_func in cmds:
        if strict_startswith(cmd, argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(
                argv,
                opts["af"],
                opts["json_print"],
                opts["pretty_json"],
                color_scheme,
                opts["brief"],
                opts["oneline"],
            )

    perror('Object "{}" is unknown, try "ip help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    # Match iproute2: exit silently on SIGPIPE (e.g. `ip route | head`)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(0 if main(sys.argv[1:]) else 1)

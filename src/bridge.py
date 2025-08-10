#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

from iproute2mac import *
import re
import subprocess
import sys


# Decode ifconfig output
def parse_ifconfig(res):
    links = []
    count = 1

    for r in res.split("\n"):
        if re.match(r"^\w+:", r):
            if count > 1:
                links.append(link)
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
            elif re.match(r"^\s+status: ", r):
                match re.findall(r"status: (\w+)", r)[0]:
                    case "active":
                        link["operstate"] = "UP"
                    case "inactive":
                        link["operstate"] = "DOWN"
            elif re.match(r"^\s+maxage ", r):
                (maxage, holdcnt, proto, maxaddr, timeout) = re.findall(
                    r"maxage (\d+) holdcnt (\d+) proto (\w+) maxaddr (\d+) timeout (\d+)",
                    r)[0]
                link["bridge"] = {
                    "maxage": int(maxage),
                    "holdcnt": int(holdcnt),
                    "proto": proto,
                    "maxaddr": int(maxaddr),
                    "timeout": int(timeout),
                    "members": []
                }
            elif re.match(r"^\s+member: ", r):
                (ifname, flags) = re.findall(
                    r"member: (\w+) flags=[\da-f]+<(.*)>", r)[0]
                flags = flags.split(",")
                link["bridge"]["members"].append({
                    "ifname": ifname,
                    "flags": flags,
                })
            elif re.match(r"^\s+ifmaxaddr ", r):
                (ifmaxaddr, ifindex, priority, cost) = re.findall(
                    r"ifmaxaddr (\d+) port (\d+) priority (\d+) path cost (\d+)",
                    r)[0]
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
def do_help(argv=None, json_print=None, pretty_json=None, color=None):
    perror("Usage: bridge [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link }")
    perror("       OPTIONS := { -V[ersion] | -j[son] | -p[retty] | -c[olor] }")
    perror(HELP_ADDENDUM)
    exit(255)


def do_help_link():
    perror("Usage: bridge link show [ dev DEV ]")
    exit(255)


# Link module
@help_msg(do_help_link)
def do_link(argv, json_print, pretty_json, color):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(argv, json_print, pretty_json, color)
    elif "set".startswith(argv[0]):
        argv.pop(0)
        return do_link_set(argv)
    else:
        return False
    return True


def do_link_show(argv, json_print, pretty_json, color):
    if len(argv) > 1:
        if argv[0] != "dev":
            return False
        else:
            argv.pop(0)
    if len(argv) > 0:
        dev = argv[0]
    else:
        dev = None

    status, res = subprocess.getstatusoutput(
        IFCONFIG + " -v -a 2>/dev/null"
    )
    if status:  # unix status
        if res == "":
            perror(param + " not found")
        else:
            perror(res)
        return False

    bridges = []
    links = parse_ifconfig(res)

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
            colorize_ifname(color, b["ifname"]),
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


@help_msg(do_help)
def main(argv):
    json_print = False
    pretty_json = False
    color_mode = "never"

    while argv and argv[0].startswith("-"):
        # Turn --opt into -opt
        argv[0] = argv[0][1 if argv[0][1] == '-' else 0:]
        # Process options
        if "-color".startswith(argv[0].split("=")[0]):
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
            perror('Option "{}" is unknown, try "bridge help".'.format(
                argv[0]))
            exit(255)

    if not argv:
        return False

    color_scheme = get_color_scheme(color_mode, json_print)

    for cmd, cmd_func in cmds:
        if cmd.startswith(argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(argv, json_print, pretty_json, color_scheme)

    perror('Object "{}" is unknown, try "bridge help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

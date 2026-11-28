#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import signal
import subprocess
import sys

from iproute2mac import *


# Decode ifconfig output
def parse_ifconfig(res):
    return parse_ifconfig_links(res, parse_bridge=True)


# Help
def do_help(
    argv=None, json_print=None, pretty_json=None, color=None, oneline=None
):
    perror("Usage: bridge [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { link }")
    perror(
        "       OPTIONS := { -V[ersion] | -j[son] | -p[retty] | -c[olor] | -o[neline] }"
    )
    perror(HELP_ADDENDUM)
    exit(255)


def do_help_link():
    perror("Usage: bridge link show [ dev DEV ]")
    exit(255)


# Link module
@help_msg(do_help_link)
def do_link(argv, json_print, pretty_json, color, oneline):
    if not argv:
        argv.append("show")

    if strict_startswith("set", argv[0]):
        argv.pop(0)
        perror("iproute2mac: 'bridge link set' is not implemented")
        exit(255)
    elif any_startswith(["show", "lst", "list"], argv[0]):
        argv.pop(0)
        return do_link_show(argv, json_print, pretty_json, color, oneline)
    else:
        return False
    return True


def do_link_show(argv, json_print, pretty_json, color, oneline):
    if len(argv) > 1:
        if argv[0] != "dev" or len(argv) > 2:
            return False
        argv.pop(0)
    if len(argv) > 0:
        dev = argv[0]
    else:
        dev = None

    res = subprocess.run(
        [IFCONFIG, "-v", "-a"], capture_output=True, text=True
    )
    if res.returncode != 0:
        out = (res.stderr + res.stdout).strip()
        if out:
            perror(out)
        return False

    bridges = []
    links = parse_ifconfig(res.stdout)

    for master in [l for l in links if "bridge" in l]:
        for slave in master["bridge"].get("members", []):
            if dev and slave["ifname"] != dev:
                continue
            link = next(
                (l for l in links if l["ifname"] == slave["ifname"]), None
            )
            if link is None:
                continue
            bridges.append(
                {
                    "ifindex": slave.get("ifindex", link["ifindex"]),
                    "ifname": slave["ifname"],
                    "flags": link["flags"],
                    "mtu": link["mtu"],
                    "master": master["ifname"],
                    "state": "forwarding",  # FIXME: how to ensure it is forwarding?
                    "priority": slave.get("priority", 0),
                    "cost": slave.get("cost", 0),
                }
            )

    if json_print:
        return json_dump(bridges, pretty_json)

    lines = [
        "%d: %s: <%s> mtu %d master %s state %s priority %d cost %d"
        % (
            b["ifindex"],
            colorize_ifname(color, b["ifname"]),
            ",".join(b["flags"]),
            b["mtu"],
            b["master"],
            b["state"],
            b["priority"],
            b["cost"],
        )
        for b in bridges
    ]

    # oneline doesn't do anything in this case
    for l in lines:
        print(l)

    return True


# Match iproute2 commands
# https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/bridge/bridge.c#n52
cmds = [
    ("link", do_link),
    ("help", do_help),
]


@help_msg(do_help)
def main(argv):
    opts = parse_cli_options(argv, "bridge", do_help)
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
                opts["json_print"],
                opts["pretty_json"],
                color_scheme,
                opts["oneline"],
            )

    perror('Object "{}" is unknown, try "bridge help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    # Match iproute2: exit silently on SIGPIPE (e.g. `ip route | head`)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(0 if main(sys.argv[1:]) else 1)

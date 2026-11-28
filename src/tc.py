#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2026 Vincent Jardin <vjardin@free.fr>
"""

import json
import math
import os
import re
import socket
import subprocess
import sys

from iproute2mac import *

DNCTL = "/usr/sbin/dnctl"
PFCTL = "/sbin/pfctl"
PF_ANCHOR = "com.apple/iproute2mac"
TC_FILE = os.path.join(RUNDIR, "tc.json")
PIPE_BASE = 30000

# Units of tc, case insensitive: times in microseconds, rates in bits per
# second, sizes in bytes
TIME_UNITS = {"": 1, "us": 1, "usec": 1, "usecs": 1, "ms": 1e3}
TIME_UNITS.update({"msec": 1e3, "msecs": 1e3, "s": 1e6, "sec": 1e6})
TIME_UNITS.update({"secs": 1e6})
RATE_UNITS = {"": 1, "bit": 1, "bps": 8}
for i, prefix in enumerate(["k", "m", "g", "t"]):
    RATE_UNITS[prefix + "bit"] = 1000 ** (i + 1)
    RATE_UNITS[prefix + "ibit"] = 1024 ** (i + 1)
    RATE_UNITS[prefix + "bps"] = 8 * 1000 ** (i + 1)
    RATE_UNITS[prefix + "ibps"] = 8 * 1024 ** (i + 1)
SIZE_UNITS = {"": 1, "b": 1, "k": 1024, "kb": 1024, "m": 1024**2}
SIZE_UNITS.update({"mb": 1024**2, "g": 1024**3, "gb": 1024**3})
SIZE_UNITS.update({"kbit": 128, "mbit": 128 * 1024, "gbit": 128 * 1024**2})


def parse_unit(value, units, what):
    m = re.match(r"^(\d+(?:\.\d+)?)([a-z]*)$", value.lower())
    if not m or m.group(2) not in units:
        perror('Illegal "%s"' % what)
        exit(1)
    return float(m.group(1)) * units[m.group(2)]


def is_time(value):
    m = re.match(r"^\d+(?:\.\d+)?([a-z]*)$", value.lower())
    return bool(m) and m.group(1) in TIME_UNITS


def parse_percent(value, what):
    m = re.match(r"^(\d+(?:\.\d+)?)%?$", value)
    if not m:
        perror('Illegal "%s"' % what)
        exit(1)
    return float(m.group(1))


def is_percent(value):
    return bool(re.match(r"^\d+(?:\.\d+)?%?$", value))


def format_time(usec):
    if usec % 1000000 == 0:
        return "%ds" % (usec // 1000000)
    if usec % 1000 == 0:
        return "%dms" % (usec // 1000)
    return "%dus" % usec


def format_rate(bits):
    for unit, scale in [("Gbit", 1e9), ("Mbit", 1e6), ("Kbit", 1e3)]:
        if bits >= scale:
            return "%g%s" % (bits / scale, unit)
    return "%gbit" % bits


def parse_netem(args):
    """netem [ delay TIME ] [ loss [ random ] PERCENT ] [ rate RATE ]
    [ limit PACKETS ]"""
    params = {}
    while args:
        arg = args.pop(0)
        if arg == "delay" and args:
            params["delay"] = round(parse_unit(args.pop(0), TIME_UNITS, arg))
            if args and is_time(args[0]):
                jitter = parse_unit(args.pop(0), TIME_UNITS, "jitter")
                if args and is_percent(args[0]):
                    args.pop(0)
                if jitter:
                    not_implemented(
                        "jitter", "dummynet delays all the packets the same"
                    )
        elif arg in ["loss", "drop"] and args:
            if args[0] == "random":
                args.pop(0)
            if not args or not is_percent(args[0]):
                not_implemented(
                    "loss " + " ".join(args[:1]), "dummynet drops at random"
                )
            params["loss"] = parse_percent(args.pop(0), "loss")
            if args and is_percent(args[0]):
                if parse_percent(args.pop(0), "loss"):
                    not_implemented(
                        "loss correlation", "dummynet drops at random"
                    )
        elif arg == "rate" and args:
            params["rate"] = parse_unit(args.pop(0), RATE_UNITS, arg)
        elif arg == "limit" and args and args[0].isdigit():
            params["limit"] = int(args.pop(0))
        else:
            not_implemented(
                "netem " + arg, "dummynet only delays, drops and limits"
            )
    return params


def parse_tbf(args):
    """tbf rate RATE burst BYTES { limit BYTES | latency TIME }"""
    params = {}
    while args:
        arg = args.pop(0)
        if arg == "rate" and args:
            params["rate"] = parse_unit(args.pop(0), RATE_UNITS, arg)
        elif arg in ["burst", "buffer", "maxburst"] and args:
            burst = args.pop(0).split("/")[0]
            params["burst"] = parse_unit(burst, SIZE_UNITS, arg)
        elif arg == "limit" and args:
            params["limit"] = parse_unit(args.pop(0), SIZE_UNITS, arg)
        elif arg == "latency" and args:
            params["latency"] = parse_unit(args.pop(0), TIME_UNITS, arg)
        else:
            not_implemented(
                "tbf " + arg, "dummynet limits the rate of a queue only"
            )
    if "rate" not in params or "burst" not in params:
        perror('"rate" and "burst" are required.')
        exit(1)
    if "limit" not in params and "latency" not in params:
        perror('Either "limit" or "latency" are required.')
        exit(1)
    return params


QDISC_KINDS = {"netem": parse_netem, "tbf": parse_tbf}


def pipe_config(qdiscs):
    """The configuration of a dummynet pipe doing what qdiscs do."""
    netem = {}
    tbf = {}
    for q in qdiscs:
        if q["kind"] == "netem":
            netem = q["params"]
        else:
            tbf = q["params"]
    config = []
    rate = tbf.get("rate", netem.get("rate"))
    if rate:
        if rate >= 2**31:
            not_implemented("rate", "dummynet rates are below 2Gbit")
        config += ["bw", "%d" % rate]
    if netem.get("delay"):
        if netem["delay"] % 1000:
            not_implemented("delay", "dummynet delays are milliseconds")
        config += ["delay", "%d" % (netem["delay"] // 1000)]
    if netem.get("loss"):
        config += ["plr", "%g" % (netem["loss"] / 100)]
    if tbf:
        size = tbf.get("limit")
        if size is None:
            size = tbf["rate"] / 8 * tbf["latency"] / 1e6 + tbf["burst"]
        kbytes = max(1, math.ceil(size / 1024))
        if kbytes >= 1024:
            not_implemented("limit", "dummynet queues are below 1MB")
        config += ["queue", "%dKbytes" % kbytes]
    elif "limit" in netem:
        if not 2 <= netem["limit"] <= 100:
            not_implemented("limit", "dummynet queues have 2 to 100 packets")
        config += ["queue", "%d" % netem["limit"]]
    return config


def root_cmd(cmd, input=None):
    """Run a command as root like execute_cmd(), return its output."""
    if os.geteuid() != 0:
        cmd = [SUDO] + cmd
    if VERBOSE:
        print("Executing: %s" % " ".join(cmd))
    res = subprocess.run(cmd, input=input, capture_output=True, text=True)
    if res.returncode != 0:
        perror((res.stderr + res.stdout).strip())
        exit(2)
    return res.stdout + res.stderr


def tc_load():
    """{"token": of pf, "links": {macOS name: {"pipe": N, "qdiscs": []}}}"""
    try:
        with open(TC_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    state.setdefault("links", {})
    return state


def tc_apply(state):
    """Give the pipes to pf, which is enabled while it shapes a link."""
    existing = subprocess.run(
        [IFCONFIG, "-l"], capture_output=True, text=True
    ).stdout.split()
    links = state["links"]
    for ifname in [i for i in links if i not in existing]:
        root_cmd([DNCTL, "pipe", "%d" % links.pop(ifname)["pipe"], "delete"])
    rules = "".join(
        "dummynet out quick on %s all pipe %d\n" % (ifname, link["pipe"])
        for ifname, link in sorted(links.items())
    )
    if rules:
        root_cmd([PFCTL, "-a", PF_ANCHOR, "-f", "-"], input=rules)
        if not state.get("token"):
            m = re.search(r"Token : (\d+)", root_cmd([PFCTL, "-E"]))
            state["token"] = m.group(1) if m else None
    else:
        root_cmd([PFCTL, "-a", PF_ANCHOR, "-F", "all"])
        if state.get("token"):
            root_cmd([PFCTL, "-X", state["token"]])
        state.pop("token", None)
    save_state(TC_FILE, state)


def handle_major(handle):
    """1: or 1:2 -> 1"""
    try:
        return int(handle.split(":")[0], 16)
    except ValueError:
        perror('Invalid handle "%s"' % handle)
        exit(1)


# Help
def do_help(argv=None, json_print=None, pretty_json=None):
    perror("Usage: tc [ OPTIONS ] OBJECT { COMMAND | help }")
    perror("where  OBJECT := { qdisc }")
    perror("       OPTIONS := { -V[ersion] }")
    perror(HELP_ADDENDUM)
    exit(255)


def do_help_qdisc():
    perror("Usage: tc qdisc { add | del | replace | change } dev STRING")
    perror("       { root | parent CLASSID } [ handle QHANDLE ]")
    perror("       [ QDISC_KIND [ OPTIONS ] ]")
    perror("")
    perror("       tc qdisc { show | list } [ dev STRING ]")
    perror("QDISC_KIND := { netem | tbf }")
    perror("netem OPTIONS := [ delay TIME ] [ loss PERCENT ] [ rate RATE ]")
    perror("                 [ limit PACKETS ]")
    perror("tbf OPTIONS := rate RATE burst BYTES")
    perror("               { limit BYTES | latency TIME }")
    perror("dummynet shapes the packets sent, a link has a qdisc at its root,")
    perror("which can have one child of the other kind.")
    exit(255)


# Qdisc module
@help_msg(do_help_qdisc)
def do_qdisc(argv, json_print, pretty_json):
    if not argv:
        argv.append("show")

    if any_startswith(["show", "list", "lst"], argv[0]):
        argv.pop(0)
        return do_qdisc_show(argv, json_print, pretty_json)
    for verb in ["add", "delete", "replace", "change"]:
        if strict_startswith(verb, argv[0]):
            argv.pop(0)
            return do_qdisc_modify(verb, argv)
    return False


def do_qdisc_show(argv, json_print, pretty_json):
    if json_print:
        not_implemented("tc -json", "tc of iproute2mac shows text only")
    dev = None
    if argv and argv[0] == "dev" and len(argv) == 2:
        dev = argv[1]
    elif argv:
        return False
    names = names_load()
    links = tc_load()["links"]
    aliases = ifname_aliases(names)
    for ifname, link in sorted(links.items()):
        name = aliases.get(ifname, ifname)
        if dev and kernel_ifname(dev, names) != ifname:
            continue
        for q in link["qdiscs"]:
            line = "qdisc %s %s" % (q["kind"], q["handle"])
            if not dev:
                line += " dev " + name
            if q["parent"] == "root":
                line += " root"
            else:
                line += " parent " + q["parent"]
            p = q["params"]
            if "rate" in p:
                line += " rate " + format_rate(p["rate"])
            if "burst" in p:
                line += " burst %db" % p["burst"]
            if "limit" in p:
                unit = "b" if q["kind"] == "tbf" else ""
                line += " limit %d%s" % (p["limit"], unit)
            if "latency" in p:
                line += " lat " + format_time(p["latency"])
            if "delay" in p:
                line += " delay " + format_time(p["delay"])
            if "loss" in p:
                line += " loss %g%%" % p["loss"]
            print(line)
    return True


def do_qdisc_modify(verb, argv):
    # tc qdisc { add | del | replace | change } dev DEV
    #    { root | parent CLASSID } [ handle QHANDLE ] [ KIND [ OPTIONS ] ]
    dev = parent = handle = kind = None
    params = {}
    while argv:
        arg = argv.pop(0)
        if arg == "dev" and argv:
            dev = argv.pop(0)
        elif arg == "root":
            parent = "root"
        elif arg == "parent" and argv:
            parent = argv.pop(0)
        elif arg == "handle" and argv:
            handle = argv.pop(0)
        elif arg in ["ingress", "clsact"]:
            not_implemented(arg, "dummynet shapes the packets sent")
        elif arg in QDISC_KINDS:
            kind = arg
            params = QDISC_KINDS[kind](argv)
        elif arg in ["estimator", "stab", "ingress_block", "egress_block"]:
            not_implemented(arg, "dummynet has no such option")
        else:
            not_implemented(
                "qdisc " + arg, "dummynet can do what netem and tbf do"
            )
    if dev is None:
        perror('Cannot find device ""')
        exit(1)
    if parent is None:
        perror('Error: "root" or "parent" is required.')
        exit(1)
    if verb != "delete" and kind is None:
        return False
    ifname = kernel_ifname(dev)
    try:
        index = socket.if_nametoindex(ifname)
    except OSError:
        perror('Cannot find device "%s"' % dev)
        exit(1)

    state = tc_load()
    link = state["links"].get(ifname, {"pipe": PIPE_BASE + index})
    qdiscs = link.get("qdiscs", [])
    if parent == "root":
        at = 0
    elif qdiscs and handle_major(parent) == handle_major(qdiscs[0]["handle"]):
        at = 1
    else:
        perror("RTNETLINK answers: No such file or directory")
        exit(2)
    exists = len(qdiscs) > at

    if verb == "delete":
        if not exists:
            perror("RTNETLINK answers: No such file or directory")
            exit(2)
        # deleting a qdisc deletes its child
        del qdiscs[at:]
    else:
        if verb == "add" and exists:
            perror("RTNETLINK answers: File exists")
            exit(2)
        if verb == "change" and not exists:
            perror("RTNETLINK answers: No such file or directory")
            exit(2)
        if verb == "change" and qdiscs[at]["kind"] != kind:
            perror("RTNETLINK answers: Invalid argument")
            exit(2)
        if at == 1 and qdiscs[0]["kind"] == kind:
            not_implemented(
                "%s under %s" % (kind, kind), "a link has one pipe"
            )
        if handle is None:
            handle = qdiscs[at]["handle"] if exists else "%x:" % (0x8001 + at)
        elif not handle.endswith(":"):
            handle += ":"
        qdisc = {"kind": kind, "handle": handle, "parent": parent}
        qdisc["params"] = params
        # a qdisc of another kind replaces the qdisc and its child
        if exists and qdiscs[at]["kind"] != kind:
            qdiscs = qdiscs[:at] + [qdisc]
        else:
            qdiscs = qdiscs[:at] + [qdisc] + qdiscs[at + 1 :]
        if len(qdiscs) == 2 and qdiscs[0]["kind"] == qdiscs[1]["kind"]:
            not_implemented(
                "%s under %s" % (kind, kind), "a link has one pipe"
            )

    pipe = "%d" % link["pipe"]
    if qdiscs:
        root_cmd([DNCTL, "pipe", pipe, "config"] + pipe_config(qdiscs))
        link["qdiscs"] = qdiscs
        state["links"][ifname] = link
    elif ifname in state["links"]:
        root_cmd([DNCTL, "pipe", pipe, "delete"])
        del state["links"][ifname]
    tc_apply(state)
    return True


def do_class(argv, json_print, pretty_json):
    not_implemented("tc class", "dummynet has no classes")


def do_filter(argv, json_print, pretty_json):
    not_implemented("tc filter", "dummynet shapes all the packets of a link")


# Match iproute2 commands
cmds = [
    ("qdisc", do_qdisc),
    ("class", do_class),
    ("filter", do_filter),
    ("help", do_help),
]


@help_msg(do_help)
def main(argv):
    json_print = False
    pretty_json = False

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
        if strict_startswith("-json", argv[0]):
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
            perror('Option "{}" is unknown, try "tc -help".'.format(argv[0]))
            exit(255)

    if not argv:
        return False

    for cmd, cmd_func in cmds:
        if strict_startswith(cmd, argv[0]):
            argv.pop(0)
            # Functions return true or terminate with exit(255)
            # See help_msg and do_help*
            return cmd_func(argv, json_print, pretty_json)

    perror('Object "{}" is unknown, try "tc help".'.format(argv[0]))
    exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

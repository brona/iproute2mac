#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilities on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import argparse
import subprocess
import sys

from iproute2mac import *


def parse_netstat(
    res,
    include_listening=False,
    resolve=False,
    only_tcp=False,
    only_udp=False,
    only_unix=False,
    only_raw=False,
    ipv4_only=False,
    ipv6_only=False,
):
    """
    Parse netstat output into structured socket information

    Args:
        res (str): Output from netstat command
        include_listening (bool): Include listening sockets
        resolve (bool): Resolve hostnames
        only_tcp (bool): Show only TCP sockets
        only_udp (bool): Show only UDP sockets
        only_unix (bool): Show only Unix sockets
        only_raw (bool): Show only Raw sockets
        ipv4_only (bool): Show only IPv4 sockets
        ipv6_only (bool): Show only IPv6 sockets

    Returns:
        list: List of socket dictionaries
    """
    sockets = []

    # Split by lines and skip header
    lines = res.strip().split("\n")

    for line in lines:
        if not line or line.startswith("Active") or line.startswith("Proto"):
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        proto = parts[0].lower()

        # Filter by protocol type
        if only_tcp and not proto.startswith("tcp"):
            continue
        if only_udp and not proto.startswith("udp"):
            continue
        if only_unix and not proto.startswith("unix"):
            continue
        if only_raw and not "raw" in proto:
            continue

        # Filter by IP version
        if ipv4_only and not "4" in proto:
            continue
        if ipv6_only and not "6" in proto:
            continue

        # Filter by state (listening or established)
        state = parts[-1] if len(parts) >= 6 else "UNKNOWN"
        if not include_listening and state == "LISTEN":
            continue

        local = parts[3]
        peer = parts[4]

        # Split address and port
        local_addr, local_port = (
            local.rsplit(".", 1) if "." in local else (local, "*")
        )
        peer_addr, peer_port = (
            peer.rsplit(".", 1) if "." in peer else (peer, "*")
        )

        # Format state to match ss conventions
        if state == "ESTABLISHED":
            state = "ESTAB"
        elif state == "CLOSE_WAIT":
            state = "CLOSE-WAIT"

        socket = {
            "netid": proto,
            "state": state,
            "recv_q": parts[1],
            "send_q": parts[2],
            "local_addr": local_addr,
            "local_port": local_port,
            "peer_addr": peer_addr,
            "peer_port": peer_port,
        }

        sockets.append(socket)

    return sockets


def format_socket_line(socket, color, numeric=False):
    """
    Format a socket for display

    Args:
        socket (dict): Socket information dictionary
        color: Color scheme from get_color_scheme
        numeric (bool): Show numeric values only

    Returns:
        str: Formatted line for display
    """
    netid = socket["netid"]
    state = socket["state"]
    recv_q = socket["recv_q"]
    send_q = socket["send_q"]

    local = f"{socket['local_addr']}:{socket['local_port']}"
    peer = f"{socket['peer_addr']}:{socket['peer_port']}"

    # Color the output using master branch color scheme
    state_colored = colorize(
        color,
        COLOR_OPERSTATE_UP if state == "ESTAB" else COLOR_OPERSTATE_DOWN,
        state,
    )
    local_colored = colorize_ifname(color, local)
    peer_colored = colorize_inet(color, "inet", peer)

    # Format for display, adjust field spacing
    return f"{netid}\t{state_colored}\t{recv_q}\t{send_q}\t{local_colored}\t{peer_colored}"


def print_header():
    """Print the table header"""
    print(
        f"Netid\tState\tRecv-Q\tSend-Q\tLocal Address:Port\tPeer Address:Port"
    )


def do_summary():
    """
    Show socket statistics summary

    Returns:
        bool: Success or failure
    """
    # Run netstat to get socket info
    try:
        status, res = subprocess.getstatusoutput(f"{NETSTAT} -s")
        if status:
            perror("Cannot get socket statistics")
            return False

        # Just print netstat output for now
        print(res)
        return True
    except Exception as e:
        perror(str(e))
        return False


def main(argv):
    """
    Main function for ss command

    Args:
        argv (list): Command line arguments

    Returns:
        bool: Success or failure
    """
    parser = argparse.ArgumentParser(
        prog="ss",
        description="Dump socket statistics (iproute2mac wrapper for netstat on macOS).",
        epilog=HELP_ADDENDUM,
        usage="ss [ OPTIONS ] [ FILTER ]",
    )
    parser.add_argument(
        "-V",
        "-v",
        "--version",
        action="version",
        version="iproute2mac, v" + VERSION,
    )
    parser.add_argument(
        "-n",
        "--numeric",
        action="store_true",
        help="Do not try to resolve service names.",
    )
    parser.add_argument(
        "-r",
        "--resolve",
        action="store_true",
        help="Try to resolve numeric address/ports.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Display both listening and non-listening sockets.",
    )
    parser.add_argument(
        "-l",
        "--listening",
        action="store_true",
        help="Display only listening sockets.",
    )
    parser.add_argument(
        "-p",
        "--processes",
        action="store_true",
        help="Show process using socket.",
    )
    parser.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="Print summary statistics.",
    )
    parser.add_argument(
        "-4",
        "--ipv4",
        action="store_true",
        help="Display only IP version 4 sockets.",
    )
    parser.add_argument(
        "-6",
        "--ipv6",
        action="store_true",
        help="Display only IP version 6 sockets.",
    )
    parser.add_argument(
        "-t", "--tcp", action="store_true", help="Display TCP sockets."
    )
    parser.add_argument(
        "-u", "--udp", action="store_true", help="Display UDP sockets."
    )
    parser.add_argument(
        "-w", "--raw", action="store_true", help="Display RAW sockets."
    )
    parser.add_argument(
        "-x",
        "--unix",
        action="store_true",
        help="Display Unix domain sockets.",
    )

    # iproute2mac specific options
    parser.add_argument(
        "-c",
        "--color",
        nargs="?",
        choices=["never", "always", "auto"],
        const="always",
        default="never",
        help="Colorize output (iproute2mac).",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format (iproute2mac).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        dest="pretty_json",
        help="Pretty-print JSON output (iproute2mac).",
    )

    # filter positional arguments if any
    parser.add_argument(
        "filter",
        nargs=argparse.REMAINDER,
        help="FILTER := [ state STATE-FILTER ] [ EXPRESSION ]",
    )

    args = parser.parse_args(argv)

    if args.filter:
        perror(
            "iproute2mac: FILTER for ss command is not yet implemented. Use available flags or netstat directly."
        )
        exit(1)

    # Get color scheme
    color_scheme = get_color_scheme(args.color, args.json)

    # Summary mode - show socket statistics
    if args.summary:
        return do_summary()

    # Run netstat with appropriate options
    cmd = [NETSTAT, "-na"]

    # Execute command
    try:
        status, res = subprocess.getstatusoutput(" ".join(cmd))
        if status:
            if res == "":
                perror("Cannot get socket information")
            else:
                perror(res)
            return False
    except Exception as e:
        perror(str(e))
        return False

    # Parse socket info
    sockets = parse_netstat(
        res,
        include_listening=args.all or args.listening,
        resolve=args.resolve,
        only_tcp=args.tcp,
        only_udp=args.udp,
        only_unix=args.unix,
        only_raw=args.raw,
        ipv4_only=args.ipv4,
        ipv6_only=args.ipv6,
    )

    # JSON output
    if args.json:
        return json_dump(sockets, args.pretty_json)

    # Display results as table
    print_header()
    for socket in sockets:
        print(format_socket_line(socket, color_scheme, numeric=args.numeric))

    return True


if __name__ == "__main__":
    main(sys.argv[1:])

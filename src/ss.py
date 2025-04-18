#!/usr/bin/env python3


"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

from iproute2mac import *
from utils.color import Colors, colorize, perror, init_color

import subprocess
import sys

# Help message
def do_help(argv=None, json_print=None, pretty_json=None):
    perror("Usage: ss [ OPTIONS ] [ FILTER ]")
    perror("       OPTIONS := { -h[elp] | -V[ersion] | -v[erbose] | -n[umeric] | -r[resolve] }")
    perror("                  { -a[ll] | -l[istening] | -o[options] | -e[stablished] | -c[onnected] }")
    perror("                  { -p[processes] | -i[info] | -s[ummary] | -j[son] | -p[retty] | -c[olor][=auto|always|never] }")
    perror("                  { -4 | -6 | -t[cp] | -u[dp] | -w[raw] | -x[unix] }")
    perror("       FILTER := [ state TCP-STATE ] [ EXPRESSION ]")
    perror(HELP_ADDENDUM)
    exit(255)


def parse_netstat(res, include_listening=False, resolve=False, only_tcp=False,
                  only_udp=False, only_unix=False, only_raw=False,
                  ipv4_only=False, ipv6_only=False):
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
    lines = res.strip().split('\n')
    
    for line in lines:
        if not line or line.startswith('Active') or line.startswith('Proto'):
            continue
            
        parts = line.split()
        if len(parts) < 5:
            continue
            
        proto = parts[0].lower()
        
        # Filter by protocol type
        if only_tcp and not proto.startswith('tcp'):
            continue
        if only_udp and not proto.startswith('udp'):
            continue
        if only_unix and not proto.startswith('unix'):
            continue
        if only_raw and not 'raw' in proto:
            continue
            
        # Filter by IP version
        if ipv4_only and not '4' in proto:
            continue
        if ipv6_only and not '6' in proto:
            continue
            
        # Filter by state (listening or established)
        state = parts[-1] if len(parts) >= 6 else "UNKNOWN"
        if not include_listening and state == "LISTEN":
            continue
            
        local = parts[3]
        peer = parts[4]
        
        # Split address and port
        local_addr, local_port = local.rsplit('.', 1) if '.' in local else (local, '*')
        peer_addr, peer_port = peer.rsplit('.', 1) if '.' in peer else (peer, '*')
    
        # Format state to match ss conventions
        if state == "ESTABLISHED":
            state = "ESTAB"
        elif state == "CLOSE_WAIT":
            state = "CLOSE-WAIT"
            
        socket = {
            'netid': proto,
            'state': state,
            'recv_q': parts[1],
            'send_q': parts[2],
            'local_addr': local_addr,
            'local_port': local_port,
            'peer_addr': peer_addr,
            'peer_port': peer_port
        }
        
        sockets.append(socket)
        
    return sockets


def format_socket_line(socket, numeric=False):
    """
    Format a socket for display
    
    Args:
        socket (dict): Socket information dictionary
        numeric (bool): Show numeric values only
        
    Returns:
        str: Formatted line for display
    """
    netid = socket['netid']
    state = socket['state']
    recv_q = socket['recv_q']
    send_q = socket['send_q']
    
    local = f"{socket['local_addr']}:{socket['local_port']}"
    peer = f"{socket['peer_addr']}:{socket['peer_port']}"
    
    # Color the output
    state_colored = colorize(Colors.YELLOW, state)
    local_colored = colorize(Colors.CYAN, local)
    peer_colored = colorize(Colors.GREEN, peer)
    
    # Format for display, adjust field spacing
    return f"{netid}\t{state_colored}\t{recv_q}\t{send_q}\t{local_colored}\t{peer_colored}"


def print_header():
    """Print the table header"""
    print(f"Netid\tState\tRecv-Q\tSend-Q\tLocal Address:Port\tPeer Address:Port")


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


@help_msg(do_help)
def main(argv, json_print=False, pretty_json=False):
    """
    Main function for ss command
    
    Args:
        argv (list): Command line arguments
        json_print (bool): Print output as JSON
        pretty_json (bool): Format JSON output
        
    Returns:
        bool: Success or failure
    """
    # Options
    all_sockets = False
    listening = False
    numeric = False
    resolve = False
    processes = False
    summary = False
    only_tcp = False
    only_udp = False
    only_unix = False
    only_raw = False
    ipv4_only = False
    ipv6_only = False
    
    # Process options
    while argv and argv[0].startswith('-'):
        # Turn --opt into -opt
        argv[0] = argv[0][1 if argv[0][1] == '-' else 0:]
        
        # Process options
        if "-color".startswith(argv[0].split("=")[0]):
            init_color(argv[0])
            argv.pop(0)
        elif "-json".startswith(argv[0]):
            json_print = True
            argv.pop(0)
        elif "-pretty".startswith(argv[0]):
            pretty_json = True
            argv.pop(0)
        elif "-help".startswith(argv[0]):
            return do_help(None, json_print, pretty_json)
        elif "-Version".startswith(argv[0]):
            print("iproute2mac, v" + VERSION)
            exit(0)
        elif "-all".startswith(argv[0]):
            all_sockets = True
            argv.pop(0)
        elif "-listening".startswith(argv[0]):
            listening = True
            argv.pop(0)
        elif "-numeric".startswith(argv[0]):
            numeric = True
            argv.pop(0)
        elif "-resolve".startswith(argv[0]):
            resolve = True
            argv.pop(0)
        elif "-processes".startswith(argv[0]):
            processes = True
            argv.pop(0)
        elif "-summary".startswith(argv[0]):
            summary = True
            argv.pop(0)
        elif argv[0] == "-4":
            ipv4_only = True
            argv.pop(0)
        elif argv[0] == "-6":
            ipv6_only = True
            argv.pop(0)
        elif "-tcp".startswith(argv[0]):
            only_tcp = True
            argv.pop(0)
        elif "-udp".startswith(argv[0]):
            only_udp = True
            argv.pop(0)
        elif "-unix".startswith(argv[0]):
            only_unix = True
            argv.pop(0)
        elif "-raw".startswith(argv[0]):
            only_raw = True
            argv.pop(0)
        else:
            perror(f'Option "{argv[0]}" is unknown, try "ss -help".')
            exit(255)
    
    # Summary mode - show socket statistics
    if summary:
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
        include_listening=all_sockets or listening,
        resolve=resolve, 
        only_tcp=only_tcp,
        only_udp=only_udp, 
        only_unix=only_unix,
        only_raw=only_raw, 
        ipv4_only=ipv4_only,
        ipv6_only=ipv6_only
    )
    
    # JSON output
    if json_print:
        return json_dump(sockets, pretty_json)
    
    # Display results as table
    print_header()
    for socket in sockets:
        print(format_socket_line(socket, numeric=numeric))
    
    return True

if __name__ == "__main__":
    main(sys.argv[1:]) 

#!/usr/bin/env python3
"""Unit tests for iproute2mac using recorded macOS command output fixtures."""

import io
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import bridge  # noqa: E402
import ip  # noqa: E402
import iproute2mac  # noqa: E402
import ss  # noqa: E402

IFCONFIG_FIXTURE = """\
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384 index 1
\toptions=1203<RXCSUM,TXCSUM,TXSTATUS,SW_TIMESTAMP>
\tinet 127.0.0.1 netmask 0xff000000
\tinet6 ::1 prefixlen 128
\tinet6 fe80::1%lo0 prefixlen 64 scopeid 0x1
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500 index 6
\tether 00:11:22:33:44:55
\tinet 192.168.1.10 netmask 0xffffff00 broadcast 192.168.1.255
\tinet6 fe80::1234:5678:9abc:def0%en0 prefixlen 64 secured scopeid 0x6
\tstatus: active
utun0: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1380 index 12
\tinet 10.8.0.2 --> 10.8.0.1 netmask 0xffffffff
bridge0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500 index 15
\tether 02:00:00:00:00:01
\tmaxage 20 holdcnt 6 proto rstp maxaddr 100 timeout 1200
\tmember: en0 flags=3<LEARNING,DISCOVER>
\t\tifmaxaddr 0 port 6 priority 128 path cost 20000
\tstatus: active
"""

NETSTAT_NA_FIXTURE = """\
Active Internet connections (including servers)
Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)
tcp4       0      0  127.0.0.1.8080         *.*                    LISTEN
tcp4       0      0  192.168.1.10.54321     93.184.216.34.443      ESTABLISHED
udp4       0      0  *.5353                 *.*
udp6       0      0  *.*                    *.*
Active LOCAL (UNIX) domain sockets
Address          Type   Recv-Q Send-Q            Inode             Conn             Refs          Nextref Addr
9988ddb9edff6c80 stream      0      0                0                0                0                0 /var/run/mDNSResponder
12f94f4cef6131da stream      0      0                0 9988ddb9edff6c80                0                0
"""

NETWORKSETUP_FIXTURE = """\
Hardware Port: Thunderbolt Bridge
Device: bridge0

Hardware Port: Wi-Fi
Device: en0
Ethernet Address: aa:bb:cc:dd:ee:ff
"""


class TestIproute2macHelpers(unittest.TestCase):
    def test_colorize_mac_respects_ljust(self):
        res = iproute2mac.colorize_mac("none", "00:11:22:33:44:55", ljust=20)
        self.assertEqual(res, "00:11:22:33:44:55   ")

    def test_help_msg_rejects_non_function(self):
        with self.assertRaises(TypeError):
            iproute2mac.help_msg(None)

    def test_check_enable_color_handles_missing_tput(self):
        with (
            patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True),
            patch("sys.stdout.isatty", return_value=True),
            patch(
                "iproute2mac.subprocess.check_output",
                side_effect=FileNotFoundError("tput"),
            ),
        ):
            self.assertTrue(iproute2mac._check_enable_color("auto", False))

    def test_parse_ifconfig_links(self):
        links = iproute2mac.parse_ifconfig_links(
            IFCONFIG_FIXTURE,
            af=-1,
            address=True,
            parse_bridge=True,
            sort_by_ifindex=True,
        )
        self.assertEqual(
            [l["ifname"] for l in links], ["lo0", "en0", "utun0", "bridge0"]
        )
        utun = links[2]
        self.assertEqual(utun["addr_info"][0]["address"], "10.8.0.1")
        br = links[3]
        self.assertEqual(br["bridge"]["members"][0]["ifname"], "en0")
        self.assertEqual(br["bridge"]["members"][0]["cost"], 20000)


class TestIpModule(unittest.TestCase):
    def test_route_replace_adds_when_delete_fails_and_preserves_blackhole(
        self,
    ):
        calls = []

        def fake_exec(cmd):
            calls.append(cmd)
            return "delete" not in cmd

        with patch("ip.execute_cmd", side_effect=fake_exec):
            ok = ip.do_route_replace(["blackhole", "192.0.2.0/24"], -1)
        self.assertTrue(ok)
        self.assertEqual(
            calls,
            [
                [
                    "/usr/bin/sudo",
                    "/sbin/route",
                    "delete",
                    "192.0.2.0/24",
                    "127.0.0.1",
                    "-blackhole",
                ],
                [
                    "/usr/bin/sudo",
                    "/sbin/route",
                    "add",
                    "192.0.2.0/24",
                    "127.0.0.1",
                    "-blackhole",
                ],
            ],
        )

    def test_route_list_strips_ipv6_host_scope(self):
        netstat_out = (
            "Routing tables\n\nInternet6:\n"
            "Destination        Gateway        Flags  Netif Expire\n"
            "fe80::1%lo0        link#1         UHL    lo0\n"
        )
        fake_res = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=netstat_out, stderr=""
        )
        buf = io.StringIO()
        with (
            patch("ip.subprocess.run", return_value=fake_res),
            patch("sys.stdout", buf),
        ):
            ok = ip.do_route_list([], 6, False, False, "none")
        self.assertTrue(ok)
        self.assertIn("fe80::1 dev lo0 scope link", buf.getvalue())

    def test_addr_add_and_del_validate_args(self):
        self.assertFalse(ip.do_addr_add(["10.0.0.1", "peer"], -1))
        self.assertFalse(
            ip.do_addr_add(["10.0.0.1", "dev", "en0", "extra"], -1)
        )
        self.assertFalse(ip.do_addr_del(["10.0.0.1", "notdev", "en0"], -1))

    def test_link_set_rejects_unknown_option(self):
        with patch("ip.perror") as mock_err:
            ok = ip.do_link_set(["dev", "en0", "mtus", "1500"], -1)
        self.assertFalse(ok)
        mock_err.assert_called_once()

    def test_link_set_factory_mac_stanza_parsing(self):
        fake_res = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=NETWORKSETUP_FIXTURE, stderr=""
        )
        with (
            patch("ip.subprocess.run", return_value=fake_res),
            patch("ip.execute_cmd", return_value=True) as mock_exec,
        ):
            ok = ip.do_link_set(["dev", "en0", "address", "factory"], -1)
        self.assertTrue(ok)
        mock_exec.assert_called_once_with(
            [
                "/usr/bin/sudo",
                "/sbin/ifconfig",
                "en0",
                "lladdr",
                "aa:bb:cc:dd:ee:ff",
            ]
        )

    def test_neigh_show_handles_subprocess_error(self):
        fake_res = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="ndp failed"
        )
        with (
            patch("ip.subprocess.run", return_value=fake_res),
            patch("ip.perror") as mock_err,
        ):
            ok = ip.do_neigh_show([], 6, False, False, "none")
        self.assertFalse(ok)
        mock_err.assert_called_once_with("ndp failed")

    def test_neigh_flush_propagates_failure(self):
        with patch("ip.execute_cmd", return_value=False):
            self.assertFalse(ip.do_neigh_flush(["dev", "en0"], 4))


class TestBridgeModule(unittest.TestCase):
    def test_bridge_invalid_color_mentions_bridge_not_ip(self):
        stderr = io.StringIO()
        with patch("sys.stderr", stderr), self.assertRaises(SystemExit) as ctx:
            bridge.main(["-color=bogus", "link"])
        self.assertEqual(ctx.exception.code, 255)
        self.assertIn("bridge -help", stderr.getvalue())


class TestSsModule(unittest.TestCase):
    def test_parse_netstat_unix_sockets(self):
        unix_only = ss.parse_netstat(
            NETSTAT_NA_FIXTURE, only_unix=True, show_all=True
        )
        self.assertEqual(len(unix_only), 2)
        self.assertEqual(unix_only[0]["netid"], "u_str")
        self.assertEqual(unix_only[0]["local_addr"], "/var/run/mDNSResponder")

    def test_parse_netstat_default_skips_unix_and_headers(self):
        default_socks = ss.parse_netstat(NETSTAT_NA_FIXTURE)
        netids = [s["netid"] for s in default_socks]
        self.assertEqual(netids, ["tcp4", "udp4", "udp6"])
        self.assertEqual(default_socks[1]["state"], "UNCONN")

    def test_parse_netstat_listening_includes_bound_udp(self):
        listening = ss.parse_netstat(NETSTAT_NA_FIXTURE, listening_only=True)
        self.assertEqual(
            [(s["netid"], s["local_port"]) for s in listening],
            [("tcp4", "8080"), ("udp4", "5353")],
        )

    def test_ss_unimplemented_flags_exit_255(self):
        with (
            patch("sys.stderr", io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            ss.main(["-r"])
        self.assertEqual(ctx.exception.code, 255)


if __name__ == "__main__":
    unittest.main()

iproute2mac
===========

*CLI wrapper for basic network utilities on macOS, inspired by iproute2 on Linux systems – `ip`, `bridge` and `ss` commands*

Provided functionality is limited and command output is not fully compatible with [iproute2].\
Goal of this project is to make basic network configuration/debug tasks on macOS easy for admins who already use Linux systems.\
For advanced usage use `netstat`, `ifconfig`, `ndp`, `arp`, `route` and `networksetup` directly.

If you are interested in contributing, please see our [Contribution Guidelines](./CONTRIBUTING.md).

## Installation

A) [Preferred] Using [Homebrew](http://brew.sh) (Maintained by [@brona](https://github.com/brona)):

```bash
# [Optional] Install Homebrew first, see http://brew.sh for options
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install iproute2mac
brew install iproute2mac
```

See https://formulae.brew.sh/formula/iproute2mac and [iproute2mac.rb](https://github.com/Homebrew/homebrew-core/blob/main/Formula/i/iproute2mac.rb) for mode details.

B) Manual installation from HEAD:

```bash
sudo mkdir /usr/local/iproute2mac
sudo chown -R $(whoami):admin /usr/local/iproute2mac
cd /usr/local/
git clone https://github.com/brona/iproute2mac.git
ln -s iproute2mac/src/ip.py /usr/local/bin/ip
ln -s iproute2mac/src/bridge.py /usr/local/bin/bridge
ln -s iproute2mac/src/ss.py /usr/local/bin/ss
```

C) Using [MacPorts](https://www.macports.org/) (Maintained by [@i0ntempest](https://github.com/i0ntempest)):

See https://ports.macports.org/port/iproute2mac/ and [Portfile](https://github.com/macports/macports-ports/blob/master/net/iproute2mac/Portfile)

D) Using [NixOS](https://nixos.org/) (Maintained by [@jiegec](https://github.com/jiegec)):

See https://search.nixos.org/packages?show=iproute2mac&type=packages&query=iproute2mac and [package.nix](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ip/iproute2mac/package.nix)


## Scripting

When its output is not a terminal, `ip` behaves like iproute2 for scripts:

* It prints nothing when a change succeeds, set `IPROUTE2MAC_VERBOSE=1` to see the macOS commands it runs.
* It exits with status 2 when macOS refuses a change, 1 when a device does not exist and 255 on a usage error.
* It runs the macOS commands without `sudo` when it is run as root.
* `ip link` shows the `state` of an interface and the `LOWER_UP` or `NO-CARRIER` flag like iproute2.

## Supported commands / Example usage

Goal of this utility is to provide compatible CLI with [iproute2], supporting same command shortcuts and user experience.

* Help
  * `ip help`
  * `ip link help`
  * `ip addr help`
  * `ip route help`
  * `ip neigh help`
  * `bridge help`
  * `bridge link help`
  * `ss help`
* Link module (Interfaces)
  * List local interfaces `ip link`
  * List interfaces in brief format `ip -br link`
  * Show one interface `ip link show en0`
  * Shutdown interface `ip link set dev en0 down`
  * Start interface `ip link set dev en0 up`
  * Set custom MAC address `ip link set dev en0 address 00:12:34:45:78:90`
  * Set **random MAC** address `ip link set en0 address random`
  * Set **factory default MAC** address `ip link set en0 address factory`
  * Set MTU `ip link set dev en0 mtu 9000`
  * Show the statistics of the links `ip -s link`: the packets, bytes and errors received, and the packets, bytes, errors, drops and collisions sent, the counters that macOS has
  * Add a dummy interface `ip link add dummy0 type dummy`, a pair of virtual Ethernet interfaces `ip link add veth0 type veth peer name veth1`, a VLAN `ip link add link en0 name en0.100 type vlan id 100`, a bridge `ip link add br0 type bridge`, an 802.3ad bond `ip link add bond0 type bond`
  * Add an interface to a bridge or a bond `ip link set dev veth1 master br0`, remove it `ip link set dev veth1 nomaster`
  * Delete an interface `ip link del dummy0`
  * macOS names these interfaces `feth`N, `vlan`N, `bridge`N and `bond`N, and cannot rename them: iproute2mac keeps the name given in `/var/run/iproute2mac/names.json`, accepts it everywhere and shows it, with the macOS name as `altname`. Like on Linux, a name given again gets its former interface, and a new name an interface that no other name had (macOS would reuse the lowest free one), so that a routing daemon does not take an interface for another. A dummy interface is a `feth` with a hidden peer, so that it has a carrier.
* Neighbour module (ARP/NDP)
  * Show all neighbours `ip neigh`
  * Show all IPv4 (ARP) neighbours `ip -4 neigh`
  * Show all IPv6 (NDP) neighbours `ip -6 neigh`
  * Show all IPv4 (ARP) neighbours for a specific interface `ip -4 neigh show dev en0`
  * Show neighbours filtered by prefix `ip -4 neigh show 192.0.2.0/24`
  * Add a static neighbour `ip neigh add 192.0.2.2 lladdr 02:00:00:00:00:02 dev en0`, or an expiring one `ip neigh add 2001:db8::2 lladdr 02:00:00:00:00:02 dev en0 nud reachable`
  * Replace or change a neighbour `ip neigh replace 192.0.2.2 lladdr 02:00:00:00:00:03 dev en0`
  * Delete a neighbour `ip neigh del 192.0.2.2 dev en0`
  * Flush the neighbours of an interface, except the permanent ones like iproute2 `ip neigh flush dev en0`, or of a prefix `ip -6 neigh flush 2001:db8::/64 dev en0`
  * macOS puts an IPv6 neighbour on the interface of the route to its address, and has no `proxy`, `router` or `extern_learn` neighbour
* Address module
  * List all addresses `ip addr`
  * List all addresses in brief format `ip -br addr`
  * List IPv4 addresses `ip -4 addr`
  * List IPv6 addresses `ip -6 addr`
  * List the addresses of an interface that are in a prefix `ip addr show dev en0 to 192.0.2.0/24`
  * Add address to interface `ip addr add 10.0.0.5/24 dev en0`
  * Add an IPv6 address without duplicate address detection `ip -6 addr add 2001:db8::5/64 dev en0 nodad`, with lifetimes `ip -6 addr add 2001:db8::5/64 dev en0 valid_lft 3600 preferred_lft 1800`
  * Change or replace an address `ip -6 addr change 2001:db8::5/64 dev en0 preferred_lft 0`
  * macOS has no `noprefixroute`, labels, nor lifetimes of IPv4 addresses, and sets the scope from the address
  * Remove address from interface `ip addr del 10.0.0.5 dev en0`
  * Remove the addresses of an interface `ip addr flush dev en0`, the global IPv6 ones `ip -6 addr flush dev en0 scope global`
* Route module
  * List IPv4 addresses `ip route`
  * List IPv6 addresses `ip -6 route`
  * Flush route cache (no-op on MacOS) `ip route flush cache`
  * Flush routes `ip route flush table main`
  * Match for specific route `ip route show default`
  * Get route for destination `ip route get 8.8.8.8`
  * Add static route `ip route add 192.168.0.0/16 nexthop 10.0.0.1`
  * Add default route `ip route add default nexthop 10.0.0.1`
  * Replace static route `ip route replace 192.0.2.0/24 dev utun1`
  * Change the gateway of a static route `ip route change 192.168.0.0/16 via 10.0.0.2`
  * Add a route with a source address (an address of the outgoing interface on macOS) and an MTU `ip route add 192.0.2.0/24 via 10.0.0.1 src 10.0.0.5 mtu 1400`
  * Add a route rejecting the packets `ip route add unreachable 192.0.2.0/24`, or discarding them `ip route add blackhole 192.0.2.0/24`
  * Remove static route `ip route del 192.168.0.0/16`
  * macOS routes have no metric and macOS has one routing table: `metric`, `table` other than `main` and `proto` other than `static` are not implemented
* Bridge module
  * List bridge interfaces `bridge link`
  * List one bridged interface `bridge link show dev en2`
* Socket Statistics (ss)
  * Show all sockets `ss`
  * Show listening sockets `ss -l`
  * Show TCP sockets `ss -t`
  * Show UDP sockets `ss -u`
  * Show IPv4 sockets `ss -4`
  * Show IPv6 sockets `ss -6`
  * Show socket statistics `ss -s`
  * Show all sockets (including listening) `ss -a`
* JSON output
  * List interfaces: `ip -j link show`
  * List addresses: `ip -j addr show`
  * List neighbours: `ip -j neigh show`
  * List routes: `ip -j route show`
  * List bridges (with pretty print): `bridge -j -p link show`
  * List sockets: `ss -j`
* Color output
  * Enable colors: `ip -color link show`
  * Force colors: `ip -color=always link show`
  * Auto colors: `ip -color=auto link show`
  * Disable colors: `ip -color=never link show`
  * Same options work for `bridge` and `ss` commands

## Changelog
<details open>
  <summary><b>HEAD</b></summary>

  - No changes yet

</details>

<details open>
  <summary><b>v1.7.6</b></summary>

  - Fix https://github.com/brona/iproute2mac/issues/81, `ss -l` now shows only LISTENING sockets.

</details>

<details open>
  <summary><b>v1.7.5</b></summary>

  - Address https://github.com/brona/iproute2mac/issues/80, migrate to `subprocess.run()`

</details>

<details open>
  <summary><b>v1.7.4</b></summary>

  - `ss -H` is now supported (`--no-header`)

</details>

<details open>
  <summary><b>v1.7.3</b></summary>

  - Fixed https://github.com/brona/iproute2mac/issues/77, improved `ip` command parsing for degenerate cases.
  - Fixed https://github.com/brona/iproute2mac/issues/76, `ss` now correctly parses getopt style arguments (e.g. `ss -nat`).
  - Fixed https://github.com/brona/iproute2mac/issues/73, `ip -4 addr` shows only interfaces that have ipv4 address assigned (thanks [@pluharok](https://github.com/pluharok))
  - Fixed `--` and `-` parsing (https://github.com/brona/iproute2mac/pull/74, thanks [@rrotter](https://github.com/rrotter))

</details>

<details open>
  <summary><b>v1.7.2</b></summary>

- Fixed `ip route` crashing with `IndexError: pop from empty list` bug introduced in v1.7.1

</details>

<details open>
  <summary><b>v1.7.1</b></summary>

- `ip addr` and `ip link` returns results in `ifindex` order (https://github.com/brona/iproute2mac/issues/72)
- `ip addr` and `ip link` support `up` filter (https://github.com/brona/iproute2mac/issues/71)
- Added `ip route list [[exact] PREFIX]` selector (https://github.com/brona/iproute2mac/issues/66)

</details>

<details open>
  <summary><b>v1.7.0</b></summary>

- Added `ss` command (https://github.com/brona/iproute2mac/issues/20 ,https://github.com/brona/iproute2mac/pull/70, thanks [@luoling8192](https://github.com/luoling8192))
- Added `-brief` option for link and address modules (https://github.com/brona/iproute2mac/issues/42 ,https://github.com/brona/iproute2mac/pull/69 thanks [@xraystyle](https://github.com/xraystyle))
- Added `-oneline` option for `link` and `addr` modules (https://github.com/brona/iproute2mac/issues/17 ,https://github.com/brona/iproute2mac/pull/62 thanks [@waketzheng](https://github.com/waketzheng))

</details>

<details>
  <summary><b>v1.0 ~ v1.6</b></summary>

  <details open>
    <summary><b>v1.6.0</b></summary>

  - Added `--color` with `auto`, `always` and `never` modes for show commands (https://github.com/brona/iproute2mac/issues/21 and https://github.com/brona/iproute2mac/issues/42, PR https://github.com/brona/iproute2mac/pull/63)
  - Fixed https://github.com/brona/iproute2mac/issues/68 `ip neigh show` not displaying lladdr in the output
  - Fixed `ip neigh show` json output not matching iproute2 (`state` and `router` fields)

  </details>

  <details open>
    <summary><b>v1.5.4</b></summary>

  - Fixed https://github.com/brona/iproute2mac/issues/56 address parsing for ptp links

  </details>

  <details open>
    <summary><b>v1.5.3</b></summary>

  - Fixed https://github.com/brona/iproute2mac/issues/21 `--color` option parsing

  </details>

  <details open>
    <summary><b>v1.5.2</b></summary>

  - Fixed https://github.com/brona/iproute2mac/issues/57

  </details>

  <details open>
    <summary><b>v1.5.1</b></summary>

  - Fixed https://github.com/brona/iproute2mac/issues/56

  </details>

  <details open>
    <summary><b>v1.5.0</b></summary>

  - Added `-json` option
    (https://github.com/brona/iproute2mac/issues/49)
  - Added `bridge` command
  - Internal reworking of `ip ... show` functions

  </details>

  <details open>
    <summary><b>v1.4.2</b></summary>

  - `-color` option is now being ignored
    (https://github.com/brona/iproute2mac/issues/47, thanks [@lexhuismans](https://github.com/lexhuismans))
  - Added support for double dashed options,\
    e.g. `--color` as well as `-color`
  - `ip route add` now ignores 2 additional arguments,\
    e.g. `ip r a 1.1.1.1 via 2.2.2.2 dev utun5` is interpreted as `ip r a 1.1.1.1 via 2.2.2.2` (https://github.com/brona/iproute2mac/issues/45)

  </details>

  <details open>
    <summary><b>v1.4.1</b></summary>

  - Fixed `ip neigh show dev en0`
    (https://github.com/brona/iproute2mac/issues/43, thanks [@SimonTate](https://github.com/SimonTate))

  </details>

  <details open>
    <summary><b>v1.4.0</b></summary>

  - Internal cleanup and code style changes
  - Added support for blackhole routes `ip route add blackhole 192.0.2.0/24`
    (thanks [@mhio](https://github.com/mhio))
  - :warning: `ip route flush cache` no longer flushes anything
  - `ip route flush table main` flushes all routes
  - `ip neigh show 192.0.2.0/24` filters neighbours
  - Flag compatibility for `-help` and `-Version`
  - Uniform matching for show command alternatives

  </details>

  <details open>
    <summary><b>v1.3.0</b></summary>

  - Migrated to Python 3

  </details>

  <details open>
    <summary><b>v1.2.3</b></summary>

  - Fixed issues with `ip route` on macOS Catalina
    (thanks [@jiegec](https://github.com/jiegec))
  - `ip route` now returns host addresses
    (thanks [@crvv](https://github.com/crvv))
  - Added `ip route flush cache`
    (thanks [@npeters](https://github.com/npeters))
  - Added `ip route replace 192.0.2.0/24 dev utun1`
    (thanks [@npeters](https://github.com/npeters))
  - Added `ip addr add 192.0.2.1/32 peer 192.0.2.1 dev utun1`
    (thanks [@npeters](https://github.com/npeters))

  </details>

  <details open>
    <summary><b>v1.2.2</b></summary>

  - Fixed argument handling while using `ip -4`
    (thanks [@bsholdice](https://github.com/bsholdice))
  - Fixed `ip help`
    (thanks [@KireinaHoro](https://github.com/KireinaHoro))

  </details open>

  <details open>
    <summary><b>v1.2.1</b></summary>

  - Fixed error return codes and test script
  - `ip neigh flush` now requires specific device
    (consistent behaviour with iproute2)

  </details>

  <details open>
    <summary><b>v1.2.0</b></summary>

  - Enhanced input parsing to support arbitrary length commands
    (thanks [@deployable](https://github.com/deployable))
  - Added simple test script
    (thanks [@deployable](https://github.com/deployable))
  - Fixed error return codes to simulate iproute2\
    (currently, help messages are inconsistently printed to stderr for all errors, unlike in iproute2)

  </details>

  <details open>
    <summary><b>v1.1.2</b></summary>

  - `ip route get` now correctly shows `src` for IPv6 addresses (thanks [@codeaholics](https://github.com/codeaholics))

  </details>

  <details open>
    <summary><b>v1.1.1</b></summary>

  - Added `dev` option to `ip route add` command (thanks [@ThangCZ](https://github.com/ThangCZ))

  </details>

  <details open>
    <summary><b>v1.1.0</b></summary>

  - Added source IP address to `ip route get` command
  - Accepted to Homebrew master branch, tap is no longer supported

  </details>

  <details open>
    <summary><b>v1.0.9</b></summary>

  - Fixed versioning

  </details>

  <details open>
    <summary><b>v1.0.8</b></summary>

  - Better error handling and error messages (thanks [@rgcr](https://github.com/rgcr))

  </details>

  <details open>
    <summary><b>v1.0.7</b></summary>

  - Help messages are now sent to stderr (thanks [@rgcr](https://github.com/rgcr))

  </details>

  <details open>
    <summary><b>v1.0.6</b></summary>

  - Fixed `ip -6 neigh` failing for N status flag

  </details>

  <details open>
    <summary><b>v1.0.5</b></summary>

  - Added `s` shortcuts to `show` commands (thanks [@vmoutoussamy](https://github.com/vmoutoussamy))

  </details>

  <details open>
    <summary><b>v1.0.4</b></summary>

  - Added `ip neigh flush` (thanks [@ThangCZ](https://github.com/ThangCZ))
  - Added `dev` option to `ip neigh show` and `ip neigh flush`

  </details>

  <details open>
    <summary><b>v1.0.3</b></summary>

  - Fixed `ifconfig: dev: bad value` in `ip addr del`

  </details>

  <details open>
    <summary><b>v1.0.2</b></summary>

  - Interface name is concatenated to `ip addr` inet rows

  </details>
</details>

## Authors

See [AUTHORS](./AUTHORS).

Used software/code:

* [macgen.py](http://www.linux-kvm.com/sites/default/files/macgen.py) - Function for generating random MAC address
* [SpoofMAC](https://github.com/feross/SpoofMAC) - Code for obtaining factory default MAC address for interface

## License

* [The MIT License](./LICENSE) (MIT)


[iproute2]: http://www.policyrouting.org/iproute2.doc.html

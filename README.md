iproute2mac
===========

CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems - `ip` and `bridge` commands.

Provided functionality is limited and command output is not fully compatible with [iproute2](http://www.policyrouting.org/iproute2.doc.html).

Goal of this project is to make basic network configuration/debug tasks on Mac OS X easy for admins who already use Linux systems.

For advanced usage use `netstat`, `ifconfig`, `ndp`, `arp`, `route` and `networksetup` directly.

If you are interested in contributing, please see our [Contribution Guidelines](./CONTRIBUTING.md).

## Installation

A) [Preferred] Using [Homebrew](http://brew.sh):

    # [Optional] Install Homebrew first, see http://brew.sh for options
    $ /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Install iproute2mac
    $ brew install iproute2mac

B) Manual installation from HEAD:

    $ sudo mkdir /usr/local/iproute2mac
    $ sudo chown -R $(whoami):admin /usr/local/iproute2mac
    $ cd /usr/local/
    $ git clone https://github.com/brona/iproute2mac.git
    $ ln -s iproute2mac/src/ip.py /usr/local/bin/ip
    $ ln -s iproute2mac/src/bridge.py /usr/local/bin/bridge

## Supported commands / Example usage

Goal of this utility is to provide compatible CLI with [iproute2](http://www.policyrouting.org/iproute2.doc.html), supporting same command shortcuts and user experience.

* Help
  * `ip help`
  * `ip link help`
  * `ip addr help`
  * `ip route help`
  * `ip neigh help`
  * `bridge help`
  * `bridge link help`
* Link module (Interfaces)
  * List local interfaces `ip link`
  * Show one interface `ip link show en0`
  * Shutdown interface `ip link set dev en0 down`
  * Start interface `ip link set dev en0 up`
  * Set custom MAC address `ip link set dev en0 address 00:12:34:45:78:90`
  * Set **Random MAC** address `ip link set en0 address random`
  * Set **Factory default MAC** address `ip link set en0 address factory`
  * Set MTU `ip link set dev en0 mtu 9000`
* Neighbour module (ARP/NDP)
  * Show all neighbours `ip neigh`
  * Show all IPv4 (ARP) neighbours `ip -4 neigh`
  * Show all IPv6 (NDP) neighbours `ip -6 neigh`
  * Show all IPv4 (ARP) neighbours for a specific interface `ip -4 neigh show dev en0`
  * Show neighbours filtered by prefix `ip -4 neigh show 192.0.2.0/24`
  * IPv6 (NDP) neighbours cannot be currently shown for a specific interface
  * Flush all neighbours (IPv4 + IPv6) for a specific interface `ip neigh flush dev en0`
  * Flush all IPv4 (ARP) neighbours for a specific interface `ip -4 neigh flush dev en0`
  * IPv6 (NDP) neighbours are being flushed for all interfaces
* Address module
  * List all addresses `ip addr`
  * List IPv4 addresses `ip -4 addr`
  * List IPv6 addresses `ip -6 addr`
  * Add address to interface `ip addr add 10.0.0.5/24 dev en0`
  * Remove address to interface `ip addr del 10.0.0.5 dev en0`
* Route module
  * List IPv4 addresses `ip route`
  * List IPv6 addresses `ip -6 route`
  * Flush route cache (no-op on MacOS) `ip route flush cache`
  * Flush routes `ip route flush table main`
  * Get route for destination `ip route get 8.8.8.8`
  * Add static route `ip route add 192.168.0.0/16 nexthop 10.0.0.1`
  * Add default route `ip route add default nexthop 10.0.0.1`
  * Replace static route `ip route replace 192.0.2.0/24 dev utun1`
  * Remove static route `ip route del 192.168.0.0/16`
* Bridge module
  * List bridge interfaces `bridge link`
  * List one bridged interface `bridge link show dev en2`
* JSON output
  * List interfaces: `ip -j link show`
  * List addresses: `ip -j addr show`
  * List neighbours: `ip -j neigh show`
  * List routes: `ip -j route show`
  * List bridges (whith pretty print): `bridge -j -p link show`

## Changelog

**v1.5.0**
* Added `-json` option (Issue #49)
* Added `bridge` command
* Internal reworking of `ip ... show` functions

**v1.4.2**
* Ignores `-color` option (Issue #47, Thanks @lexhuismans)
* Accepts double dashed options, e.g. `--color` as well as `-color`
* `ip route add` ignores 2 additional arguments, e.g. `ip r a 1.1.1.1 via 2.2.2.2 dev utun5` is interpreted as `ip r a 1.1.1.1 via 2.2.2.2` (Issue #45)

**v1.4.1**
* Fixed `ip neigh show dev en0` (Issue #43, Thanks @SimonTate)

**v1.4.0**
* Internal cleanup and code style changes
* Added blackhole routes `ip route add blackhole 192.0.2.0/24` (Thanks @mhio)
* :warning: `ip route flush cache` no longer flushes anything
* `ip route flush table main` flushes all routes
* `ip neigh show 192.0.2.0/24` filters neighbours
* Flag compatibility for `-help` and `-Version`
* Uniform matching for show command alternatives

**v1.3.0**
* Migrated to Python 3

**v1.2.3**
* Fixed `ip route` for Mac OS X Catalina (Thanks @jiegec)
* `ip route` now returns host addresses (Thanks @crvv)
* Added `ip route flush cache` (Thanks @npeters)
* Added `ip route replace 192.0.2.0/24 dev utun1` (Thanks @npeters)
* Added `ip addr add 192.0.2.1/32 peer 192.0.2.1 dev utun1` (Thanks @npeters)

**v1.2.2**
* Fixed handling arguments while using `ip -4` (Thanks @bsholdice)
* Fixed `ip help` (Thanks @KireinaHoro)

**v1.2.1**
* Fixed error return codes and test script
* `ip neigh flush` now requires specific device (consistent behaviour with iproute2)

**v1.2.0**
* Enhanced input parsing to support arbitrary length commands (Thanks @deployable)
* Simple test script added (Thanks @deployable)
* Fixed error return codes to simulate iproute2 (At this moment help messages are inconsistently printed to stderr for all errors unlinke iproute2 behaviour)

**v1.1.2**
* Correctly show `src` for `ip route get` on IPv6 addresses (Thanks @codeaholics)

**v1.1.1**
* Added `dev` option to `ip route add` command (Thanks @ThangCZ)

**v1.1.0**
* Added source IP address to `ip route get` command
* Accepted to Homebrew master branch, tap is no longer supported

**v1.0.9**
* Fixed versioning

**v1.0.8**
* Better error handling and error messages (Thanks @rgcr)

**v1.0.7**
* Help messages are sent to stderr (Thanks @rgcr)

**v1.0.6**
* Fixed `ip -6 neigh` failing for N status flag

**v1.0.5**
* Added `s` shortcuts to `show` commands (Thanks @vmoutoussamy)

**v1.0.4**
* Added `ip neigh flush` (Thanks @ThangCZ)
* Added 'dev' option for `ip neigh show` and `ip neigh flush`

**v1.0.3**
* Fixed `ifconfig: dev: bad value` in `ip addr del`

**v1.0.2**
* Interface name is concatenated to `ip addr` inet rows

## Authors

See AUTHORS.

Used software/code:

* [macgen.py](http://www.linux-kvm.com/sites/default/files/macgen.py) - Function for generating random MAC address
* [SpoofMAC](https://github.com/feross/SpoofMAC) - Code for obtaining factory default MAC address for interface

## License

* The MIT License (MIT)

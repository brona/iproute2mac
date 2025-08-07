iproute2mac
===========

*CLI wrapper for basic network utilities on macOS, inspired by iproute2 on Linux systems – `ip` and `bridge` commands*

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
```

C) Using [MacPorts](https://www.macports.org/) (Maintained by [@i0ntempest](https://github.com/i0ntempest)):

See https://ports.macports.org/port/iproute2mac/ and [Portfile](https://github.com/macports/macports-ports/blob/master/net/iproute2mac/Portfile)

D) Using [NixOS](https://nixos.org/) (Maintained by [@jiegec](https://github.com/jiegec)):

See https://search.nixos.org/packages?show=iproute2mac&type=packages&query=iproute2mac and [package.nix](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ip/iproute2mac/package.nix)


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
* Link module (Interfaces)
  * List local interfaces `ip link`
  * Show one interface `ip link show en0`
  * Shutdown interface `ip link set dev en0 down`
  * Start interface `ip link set dev en0 up`
  * Set custom MAC address `ip link set dev en0 address 00:12:34:45:78:90`
  * Set **random MAC** address `ip link set en0 address random`
  * Set **factory default MAC** address `ip link set en0 address factory`
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
  * Remove address from interface `ip addr del 10.0.0.5 dev en0`
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
  * List bridges (with pretty print): `bridge -j -p link show`

## Changelog
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

<details>
  <summary><b>v1.0 ~ v1.4</b></summary>
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

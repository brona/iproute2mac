iproute2mac
===========

CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems - `ip` command.

Provided functionality is limited and command output is not fully compatible with [iproute2](http://www.policyrouting.org/iproute2.doc.html).

Goal of this project is to make basic network configuration/debug tasks on Mac OS X easy for admins who already use Linux systems.

For advanced usage use `netstat`, `ifconfig`, `ndp`, `arp`, `route` and `networksetup` directly.

## Supported Mac OS X versions (Tested)

* Mac OS X Maverics 10.9.5 (Python 2.7.5)

## Supported commands / Example usage

Goal of this utility is to provide compatible CLI with iproute2, supporting same command shortcuts and user experience.

* Help
  * `ip help`
  * `ip link help`
  * `ip addr help`
  * `ip route help`
  * `ip neigh help`
* Link module (Interfaces)
  * List local interfaces `ip link`
  * Show one interface `ip link show en0`
  * Shutdown interface `ip link set dev en0 down`
  * Start interface `ip link set dev en0 up`
  * Set custom MAC address `ip link set dev en0 address 00:12:34:45:78`
  * Set random MAC address `ip link set en0 address random`
  * Set factory default MAC address `ip link set en0 address factory`
  * Set MTU `ip link set dev en0 mtu 9000`
* Neighbour module (ARP/NDP)
  * Show all neighbors `ip neigh`
  * Show all IPv4 (ARP) neighbors `ip -4 neigh`
  * Show all IPv6 (NDP) neighbors `ip -6 neigh`
* Address module
  * List all addresses `ip addr`
  * List IPv4 addresses `ip -4 addr`
  * List IPv6 addresses `ip -6 addr`
  * Add address to interface `ip addr add 10.0.0.5/24 dev en0`
  * Remove address to interface `ip addr del 10.0.0.5 dev en0`
* Route module
  * List IPv4 addresses `ip route`
  * List IPv6 addresses `ip -6 route`
  * Get route for destination `ip route get 8.8.8.8`
  * Add static route `ip route add 192.168.0.0/16 nexthop 10.0.0.1`
  * Remote static route `ip route del 192.168.0.0/16`

## Installation

A) Manual installation:

    $ wget https://github.com/brona/iproute2mac/raw/master/src/ip.py
    $ chmod +x ip.py
    $ mv ip.py /usr/local/bin/ip

B) Using homebrew:

    # Install Homebrew first - see http://brew.sh
    $ brew install iproute2mac

## Authors

* Bronislav Robenek <brona@robenek.me>

Used software/code:

* [macgen.py](http://www.linux-kvm.com/sites/default/files/macgen.py) - Function for generating random MAC address
* [SpoofMAC](https://github.com/feross/SpoofMAC) - Code for obtaining factory default MAC address for interface

## License

* The MIT License (MIT)


#!/bin/sh

set -uex
rundir=$(cd -P -- "$(dirname -- "$0")" && printf '%s\n' "$(pwd -P)")

ip_cmd="$rundir"/../src/ip.py
bridge_cmd="$rundir"/../src/bridge.py
ss_cmd="$rundir"/../src/ss.py
ip_prefix=192.0.2
ip_dest=$ip_prefix.99/32
ip_via=$ip_prefix.98

# basics

$ip_cmd -V
$bridge_cmd -V
$ss_cmd -V

$ip_cmd --V
$bridge_cmd --V

$ip_cmd -color -V
$ip_cmd -color=always -V
$ip_cmd -color=auto -V
$ip_cmd -color=never -V

$bridge_cmd -color -V
$bridge_cmd -color=always -V
$bridge_cmd -color=auto -V
$bridge_cmd -color=never -V

$ss_cmd -c -V
$ss_cmd --color=always -V
$ss_cmd --color=auto -V
$ss_cmd --color=never -V

! $ip_cmd help
! $bridge_cmd help
! $ss_cmd help

$ip_cmd help 2>&1 >/dev/null | grep -i "Usage: ip "
$bridge_cmd help 2>&1 >/dev/null | grep -i "Usage: bridge "
$ss_cmd -h | grep -i "Usage: ss "

! $ip_cmd asdf sh
! $bridge_cmd asdf sh
! $ss_cmd asdf sh

! $ip_cmd -M route sh
! $bridge_cmd -N link sh
! $ss_cmd -X socket sh

# route

! $ip_cmd route help

$ip_cmd route help 2>&1 >/dev/null | grep -i "Usage: ip route"

$ip_cmd route

$ip_cmd route show

$ip_cmd route show default

$ip_cmd route show exact default

! $ip_cmd route show match unimplemented

$ip_cmd -c route show

$ip_cmd -j route show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -4 route show

$ip_cmd -4 -j route show | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -4 -j -p route show | tee | grep '"dev": "lo0"'

$ip_cmd -6 route show

$ip_cmd -c -6 route show

$ip_cmd -6 -j route show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -j -p -6 route show | grep "fe80::/64"

$ip_cmd ro sho

$ip_cmd r s

! $ip_cmd r asdf

## get

$ip_cmd rou get 127.0.0.1

$ip_cmd -c rou get 127.0.0.1

## add/delete

# like iproute2, silent on success when the output is not a terminal
test -z "$($ip_cmd route add $ip_dest via $ip_via)"
netstat -anr | grep "$ip_dest" | grep "$ip_via"

$ip_cmd route delete $ip_dest via $ip_via
! netstat -anr | grep "$ip_dest"

IPROUTE2MAC_VERBOSE=1 $ip_cmd route add $ip_dest via $ip_via | grep "^Executing: "
netstat -anr | grep "$ip_dest" | grep "$ip_via"

# exit status 2 when the change is refused, without the usage
set +e
$ip_cmd route add $ip_dest via $ip_via 2>/tmp/iproute2mac-test.err
rc=$?
set -e
test $rc -eq 2
! grep -i "usage" /tmp/iproute2mac-test.err
rm -f /tmp/iproute2mac-test.err

$ip_cmd route delete $ip_dest via $ip_via
! netstat -anr | grep "$ip_dest"

$ip_cmd ro add $ip_dest via $ip_via
netstat -anr | grep "$ip_dest" | grep "$ip_via"

$ip_cmd rou de $ip_dest via $ip_via
! netstat -anr | grep "$ip_dest"


## add/show/delete blackhole

$ip_cmd route add blackhole $ip_dest
netstat -anr | grep "$ip_dest" | grep "B"

$ip_cmd -c ro show

$ip_cmd ro sh | grep -E "^blackhole $ip_dest"

$ip_cmd route delete blackhole $ip_dest
! netstat -anr | grep "$ip_dest"

## unreachable and prohibit (macOS reject routes)

$ip_cmd route add unreachable $ip_dest
netstat -anr | grep "$ip_dest" | grep "R"
$ip_cmd route show $ip_dest | grep -x "unreachable $ip_dest"
$ip_cmd route del unreachable $ip_dest
! netstat -anr | grep "$ip_dest"

$ip_cmd route add prohibit $ip_dest
netstat -anr | grep "$ip_dest" | grep "R"
$ip_cmd route del $ip_dest
! netstat -anr | grep "$ip_dest"

## replace creates a missing route, change modifies it

test -z "$($ip_cmd route replace $ip_dest via $ip_via 2>&1)"
netstat -anr | grep "$ip_dest" | grep "$ip_via"
$ip_cmd route replace $ip_dest via $ip_prefix.97
netstat -anr | grep "$ip_dest" | grep "$ip_prefix.97"
$ip_cmd route change $ip_dest via $ip_via
netstat -anr | grep "$ip_dest" | grep "$ip_via"
$ip_cmd route del $ip_dest
! netstat -anr | grep "$ip_dest"

## attributes

$ip_cmd route add $ip_dest via $ip_via mtu 1300 table main proto static
route -n get $ip_prefix.99 | grep -E "^ +[0-9]+ +[0-9]+ +[0-9]+ +[0-9]+ +[0-9]+ +[0-9]+ +1300 "
$ip_cmd route del $ip_dest

$ip_cmd route add $ip_dest dev lo0 src 127.0.0.1
netstat -anr | grep "$ip_dest" | grep "lo0"
$ip_cmd route del $ip_dest

# no metric, no other table, nothing done
set +e
$ip_cmd route add $ip_dest via $ip_via metric 10 2>/tmp/iproute2mac-test.err
rc=$?
set -e
test $rc -eq 1
grep 'not implemented' /tmp/iproute2mac-test.err
rm -f /tmp/iproute2mac-test.err
! $ip_cmd route add $ip_dest via $ip_via table 100
! netstat -anr | grep "$ip_dest"

# address

$ip_cmd addr help 2>&1 >/dev/null | grep "Usage: ip addr"

$ip_cmd address

$ip_cmd address show

$ip_cmd address show up | grep '127.0.0.1'

$ip_cmd address show dev lo0 up  | grep '127.0.0.1'

$ip_cmd -c address show

$ip_cmd -o address show

$ip_cmd -j addr show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -4 addr show

$ip_cmd -4 -j addr show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -4 -j -p addr show dev lo0 | grep '"local": "127.0.0.1"'

$ip_cmd -6 addr show

$ip_cmd -6 -j addr show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -j -p -6 addr show dev lo0 | grep '"local": "::1"'

$ip_cmd -4 addr show dev lo0 | grep 'inet 127.0.0.1/8 scope host'

$ip_cmd -6 addr show dev lo0 | grep 'inet6 ::1/128 scope host'

$ip_cmd -6 addr show dev lo0 | grep 'inet6 fe80::1/64 scope link'

$ip_cmd -j -p -6 addr show dev lo0 | grep '"scope": "link"'

$ip_cmd addr show dev lo0 to 127.0.0.0/8 | grep 'inet 127.0.0.1/8'

! $ip_cmd addr show dev lo0 to 127.0.0.0/8 | grep 'inet6'

$ip_cmd -6 addr show to ::1/128 | grep 'inet6 ::1/128'

! $ip_cmd -6 addr show to ::1/128 | grep 'fe80::'

$ip_cmd -j addr show to 127.0.0.1 | grep '"local":"127.0.0.1"'

test -z "$($ip_cmd addr show dev lo0 to 192.0.2.0/24)"

! $ip_cmd addr show to asdf

! $ip_cmd addr show dev lo0 to

$ip_cmd ad sho

$ip_cmd a s

! $ip_cmd addr asdf

## flush

$ip_cmd addr add 192.0.2.201/32 dev lo0
$ip_cmd addr add 192.0.2.202/32 dev lo0
$ip_cmd -6 addr add 2001:db8:ffff::1/128 dev lo0
$ip_cmd addr show dev lo0 | grep 'inet 192.0.2.201/32'

$ip_cmd -4 addr flush lo0 to 192.0.2.201/32
! $ip_cmd addr show dev lo0 | grep '192.0.2.201'
$ip_cmd addr show dev lo0 | grep 'inet 192.0.2.202/32'

$ip_cmd addr flush dev lo0 scope global to 192.0.2.0/24
! $ip_cmd addr show dev lo0 | grep '192.0.2.202'

$ip_cmd -6 addr flush dev lo0 scope link to 2001:db8:ffff::/64
$ip_cmd addr show dev lo0 | grep 'inet6 2001:db8:ffff::1/128'

$ip_cmd -6 addr flush dev lo0 scope global to 2001:db8:ffff::/64
! $ip_cmd addr show dev lo0 | grep '2001:db8:ffff::1'
$ip_cmd addr show dev lo0 | grep 'inet 127.0.0.1/8'

! $ip_cmd addr flush

! $ip_cmd addr flush dev iproute2mac0

## brief format tests

# Test basic -br addr show
$ip_cmd -br addr show | grep -E "^lo[0-9]* +[A-Z]+ +"

# Test -br a shorthand
$ip_cmd -br a | grep -E "^lo[0-9]* +[A-Z]+ +"

# Test -br with specific device
$ip_cmd -br addr show dev lo0 | grep -E "^lo0 +[A-Z]+ +"

# Test -br with -4 (IPv4 only)
$ip_cmd -4 -br addr show | grep -E "^lo[0-9]* +[A-Z]+ +" | grep "127.0.0.1"

# Test -br with -6 (IPv6 only)
$ip_cmd -6 -br addr show | grep -E "^lo[0-9]* +[A-Z]+ +" | grep "::1"

# Test -br with -j (JSON output should override brief)
$ip_cmd -br -j addr show | perl -MJSON -e 'decode_json(<STDIN>)'

# Test order: -br before command
$ip_cmd -br addr show | grep -E "^lo[0-9]* +[A-Z]+ +"


# link

$ip_cmd link help 2>&1 >/dev/null | grep "Usage: ip link"

$ip_cmd lin hel 2>&1 >/dev/null | grep "Usage: ip link"

$ip_cmd -c link show

$ip_cmd -o link show

$ip_cmd link

$ip_cmd link show | grep mtu

$ip_cmd link show up | grep lo0

$ip_cmd link show dev lo0 up | grep lo0

$ip_cmd -j link show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -j -p link show dev lo0 | grep '"link_type": "loopback"'

$ip_cmd link show dev lo0 | grep -E '^1: lo0: <.*LOWER_UP.*> mtu [0-9]+ state UNKNOWN$'

$ip_cmd -j link show dev lo0 | grep '"LOWER_UP"'

! $ip_cmd link show | grep ' status '

$ip_cmd li sho | grep mtu

$ip_cmd li ls | grep mtu

$ip_cmd lin lst | grep mtu

! $ip_cmd l s

! $ip_cmd link asdf

set +e
$ip_cmd link show dev iproute2mac0 2>/tmp/iproute2mac-test.err
rc=$?
set -e
test $rc -eq 1
grep -x 'Device "iproute2mac0" does not exist.' /tmp/iproute2mac-test.err
rm -f /tmp/iproute2mac-test.err

## add/del, master

$ip_cmd link add ipr2mdummy0 type dummy
$ip_cmd link show dev ipr2mdummy0 | grep -E '^[0-9]+: ipr2mdummy0: <.*> mtu 1500 state DOWN$'
$ip_cmd link show dev ipr2mdummy0 | grep -E '^    altname feth[0-9]+$'
$ip_cmd -j link show dev ipr2mdummy0 | grep '"ifname":"ipr2mdummy0"'
# a random locally administered address, not the one of every feth
$ip_cmd link show dev ipr2mdummy0 | grep -E 'link/ether [0-9a-f][26ae]:'
! $ip_cmd link show dev ipr2mdummy0 | grep 'link/ether 66:65:74:68'
$ip_cmd link set dev ipr2mdummy0 up
$ip_cmd link show dev ipr2mdummy0 | grep -E 'LOWER_UP.* state UP$'
$ip_cmd addr add 192.0.2.211/24 dev ipr2mdummy0
$ip_cmd addr show dev ipr2mdummy0 | grep 'inet 192.0.2.211/24'
$ip_cmd route show | grep 'dev ipr2mdummy0'
! $ip_cmd link add ipr2mdummy0 type dummy
$ip_cmd link del ipr2mdummy0
! $ip_cmd link show dev ipr2mdummy0

$ip_cmd link add ipr2mveth0 type veth peer name ipr2mveth1
$ip_cmd link set ipr2mveth0 up
$ip_cmd link set ipr2mveth1 up
$ip_cmd link show dev ipr2mveth1 | grep 'LOWER_UP'
$ip_cmd link add link ipr2mveth0 name ipr2mveth0.100 type vlan id 100
$ip_cmd link set dev ipr2mveth0.100 up
$ip_cmd -j link show dev ipr2mveth0.100 | grep '"ifname":"ipr2mveth0.100"'
$ip_cmd link add name ipr2mbr0 type bridge stp_state 0
$ip_cmd link set ipr2mveth1 master ipr2mbr0
$bridge_cmd link show | grep 'ipr2mveth1: .* master ipr2mbr0 '
$ip_cmd link set ipr2mveth1 nomaster
! $bridge_cmd link show | grep 'ipr2mveth1'
$ip_cmd link del ipr2mbr0
$ip_cmd link del ipr2mveth0.100
$ip_cmd link del dev ipr2mveth0
! $ip_cmd link show dev ipr2mveth1

$ip_cmd link add ipr2mbond0 type bond mode 802.3ad
$ip_cmd link del ipr2mbond0

# a new name gets an interface that no other name had, a name given again
# its former interface
$ip_cmd link add ipr2mdumA type dummy
kdevA=$($ip_cmd link show dev ipr2mdumA | awk '/altname/ {print $2}')
$ip_cmd link del ipr2mdumA
$ip_cmd link add ipr2mdumB type dummy
test "$($ip_cmd link show dev ipr2mdumB | awk '/altname/ {print $2}')" != "$kdevA"
$ip_cmd link add ipr2mdumA type dummy
test "$($ip_cmd link show dev ipr2mdumA | awk '/altname/ {print $2}')" = "$kdevA"
$ip_cmd link del ipr2mdumA
$ip_cmd link del ipr2mdumB
# the name of a macOS interface gets that interface
$ip_cmd link add $kdevA type dummy
$ip_cmd link show dev $kdevA | grep -E "^[0-9]+: $kdevA: "
! $ip_cmd link show dev $kdevA | grep altname
$ip_cmd link del $kdevA

! $ip_cmd link add ipr2mvrf0 type vrf table 10
! $ip_cmd link add ipr2mtoolongname0 type dummy
! $ip_cmd link set dev lo0 name ipr2mlo
! $ip_cmd link del ipr2mnone0

## statistics

$ip_cmd -s link show dev lo0 | grep -E '^    RX:  +bytes +packets +errors$'
$ip_cmd -s link show dev lo0 | grep -E '^    TX:  +bytes +packets +errors +dropped +collsns$'
$ip_cmd -s link show dev lo0 | grep -A1 'RX:' | tail -1 | grep -E '^ +[0-9]+ +[0-9]+ +[0-9]+ $'
$ip_cmd -stats link show dev lo0 | grep 'RX:'
$ip_cmd -s addr show dev lo0 | grep 'TX:'
$ip_cmd -j -s link show dev lo0 | grep -E '"stats64":\{"rx":\{"bytes":[0-9]+,"packets":[0-9]+,"errors":[0-9]+\},"tx":\{"bytes":[0-9]+,'
! $ip_cmd link show dev lo0 | grep 'RX:'

## link brief format tests

# Test basic -br link show
$ip_cmd -br link show | grep -E "^lo[0-9]* +[A-Z]+ +"

# Test -br l shorthand
$ip_cmd -br l | grep -E "^lo[0-9]* +[A-Z]+ +"

# Test -br with specific device
$ip_cmd -br link show lo0 | grep -E "^lo0 +[A-Z]+ +"

# Test -br with -j (JSON output should override brief)
$ip_cmd -br -j link show | perl -MJSON -e 'decode_json(<STDIN>)'

# neigh

$ip_cmd nei help 2>&1 >/dev/null | grep "Usage: ip neighbour"

$ip_cmd nei

$ip_cmd nei show

$ip_cmd -c nei show

$ip_cmd -j neigh show | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ip_cmd -j -p neigh show dev lo0 | grep '"dev": "lo0"'

! $ip_cmd neigh asdf

## add, replace, change, del, flush

$ip_cmd link add ipr2mveth0 type veth peer name ipr2mveth1
$ip_cmd link set ipr2mveth0 up
$ip_cmd link set ipr2mveth1 up
$ip_cmd addr add 192.0.2.231/24 dev ipr2mveth0
$ip_cmd -6 addr add 2001:db8:231::1/64 dev ipr2mveth0

$ip_cmd neigh add 192.0.2.232 lladdr 02:00:00:00:02:32 dev ipr2mveth0
$ip_cmd neigh show dev ipr2mveth0 | grep -x '192.0.2.232 dev ipr2mveth0 lladdr 02:00:00:00:02:32 PERMANENT'
! $ip_cmd neigh add 192.0.2.232 lladdr 02:00:00:00:02:33 dev ipr2mveth0
$ip_cmd neigh replace 192.0.2.232 lladdr 02:00:00:00:02:33 dev ipr2mveth0
$ip_cmd neigh show 192.0.2.232 | grep 'lladdr 02:00:00:00:02:33 PERMANENT'
$ip_cmd neigh change 192.0.2.232 lladdr 02:00:00:00:02:32 dev ipr2mveth0 nud reachable
$ip_cmd neigh show 192.0.2.232 | grep 'lladdr 02:00:00:00:02:32 REACHABLE'
$ip_cmd neigh del 192.0.2.232 dev ipr2mveth0
! $ip_cmd neigh show dev ipr2mveth0 | grep 192.0.2.232
! $ip_cmd neigh del 192.0.2.232 dev ipr2mveth0
! $ip_cmd neigh change 192.0.2.232 lladdr 02:00:00:00:02:32 dev ipr2mveth0

$ip_cmd -6 neigh add 2001:db8:231::2 lladdr 02:00:00:00:02:34 dev ipr2mveth0
$ip_cmd -6 neigh show dev ipr2mveth0 | grep -x '2001:db8:231::2 dev ipr2mveth0 lladdr 02:00:00:00:02:34 PERMANENT'
test "$($ip_cmd -6 neigh show 2001:db8:231::2)" = "2001:db8:231::2 dev ipr2mveth0 lladdr 02:00:00:00:02:34 PERMANENT"
$ip_cmd neigh replace 2001:db8:231::2 lladdr 02:00:00:00:02:35 dev ipr2mveth0
test "$($ip_cmd -6 neigh show 2001:db8:231::2)" = "2001:db8:231::2 dev ipr2mveth0 lladdr 02:00:00:00:02:35 PERMANENT"
$ip_cmd neigh add fe80::2 lladdr 02:00:00:00:02:36 dev ipr2mveth0
$ip_cmd -6 neigh show dev ipr2mveth0 | grep -x 'fe80::2 dev ipr2mveth0 lladdr 02:00:00:00:02:36 PERMANENT'
$ip_cmd neigh del 2001:db8:231::2 dev ipr2mveth0
$ip_cmd neigh del fe80::2 dev ipr2mveth0
! $ip_cmd -6 neigh show dev ipr2mveth0 | grep -E '^(2001:db8:231::2|fe80::2) '

# flush keeps the permanent entries
$ip_cmd neigh add 192.0.2.233 lladdr 02:00:00:00:02:37 dev ipr2mveth0 nud reachable
$ip_cmd neigh add 192.0.2.234 lladdr 02:00:00:00:02:38 dev ipr2mveth0
$ip_cmd neigh flush dev ipr2mveth0
! $ip_cmd neigh show dev ipr2mveth0 | grep 192.0.2.233
$ip_cmd neigh show dev ipr2mveth0 | grep 192.0.2.234
$ip_cmd -6 neigh show dev ipr2mveth0 | grep '^2001:db8:231::1 .* PERMANENT'

! $ip_cmd neigh add 192.0.2.235 lladdr 02:00:00:00:02:39 dev ipr2mveth0 extern_learn
! $ip_cmd neigh add 192.0.2.235 lladdr 02:00:00:00:02:39 dev ipr2mveth0 nud noarp
! $ip_cmd neigh add 192.0.2.235 lladdr 02:00:00:00:02:39 dev ipr2mnone0
! $ip_cmd neigh show dev ipr2mveth0 | grep 192.0.2.235
$ip_cmd link del ipr2mveth0

# bridge

! $bridge_cmd help

! $bridge_cmd link help 2>&1 >/dev/null | grep "Usage: bridge link"

$bridge_cmd link

$bridge_cmd link show

$bridge_cmd -c link show

$bridge_cmd -o link show

# ss

$ss_cmd

$ss_cmd -H

$ss_cmd -c

$ss_cmd -j | tee | perl -MJSON -e 'decode_json(<STDIN>)'

$ss_cmd -4

$ss_cmd -6

$ss_cmd -t

$ss_cmd -u

$ss_cmd -l

$ss_cmd -a

$ss_cmd -s

$ss_cmd -x

$ss_cmd -j -p | grep '"netid"'

$ss_cmd -nat

$ss_cmd --unix

! $ss_cmd asdf

echo "Tests passed!!"

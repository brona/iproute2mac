#!/bin/sh

set -uex
rundir=$(cd -P -- "$(dirname -- "$0")" && printf '%s\n' "$(pwd -P)")

cmd="$rundir"/../src/ip.py
ip_prefix=192.0.2
ip_dest=$ip_prefix.99/32
ip_via=$ip_prefix.98

# basics

$cmd -V

$cmd --V

$cmd -color=never -V

! $cmd help

$cmd help 2>&1 >/dev/null | grep "Usage: ip "

! $cmd asdf sh

! $cmd -M route sh

# route

! $cmd route help

$cmd route help 2>&1 >/dev/null | grep "Usage: ip route"

$cmd route show

$cmd -4 route show

$cmd -6 route show

$cmd ro sho

$cmd r s

! $cmd r asdf

## add/delete

$cmd route add $ip_dest via $ip_via
netstat -anr | grep "$ip_dest" | grep "$ip_via"

$cmd route delete $ip_dest via $ip_via
! netstat -anr | grep "$ip_dest"

$cmd ro add $ip_dest via $ip_via
netstat -anr | grep "$ip_dest" | grep "$ip_via"

$cmd rou de $ip_dest via $ip_via
! netstat -anr | grep "$ip_dest"


## add/show/delete blackhole

$cmd route add blackhole $ip_dest
netstat -anr | grep "$ip_dest" | grep "B"

$cmd ro sh | grep -E "^blackhole $ip_dest"

$cmd route delete blackhole $ip_dest
! netstat -anr | grep "$ip_dest"

# address

$cmd addr help 2>&1 >/dev/null | grep "Usage: ip addr"

$cmd address show

$cmd ad sho

$cmd a s

! $cmd addr asdf


# link

$cmd link help 2>&1 >/dev/null | grep "Usage: ip link"

$cmd lin hel 2>&1 >/dev/null | grep "Usage: ip link"

$cmd link show | grep mtu

$cmd li sho | grep mtu

$cmd li ls | grep mtu

$cmd lin lst | grep mtu

$cmd l s | grep mtu

! $cmd link asdf

# neigh

$cmd nei help 2>&1 >/dev/null | grep "Usage: ip neighbour"

$cmd nei show

! $cmd neigh asdf

echo "Tests passed!!"


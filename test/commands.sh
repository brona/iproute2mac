#!/bin/sh

set -uex
rundir=$(cd -P -- "$(dirname -- "$0")" && printf '%s\n' "$(pwd -P)")

cmd="$rundir"/../src/ip.py
ip_prefix=10.197.92
ip_dest=$ip_prefix.99/32
ip_via=$ip_prefix.98

# ## route

! $cmd route help

$cmd route show

$cmd ro sho

$cmd r s


# ## add/delete

$cmd route add $ip_dest via $ip_via
$cmd route delete $ip_dest via $ip_via

$cmd ro add $ip_dest via $ip_via
$cmd rou de $ip_dest via $ip_via


# ## blackhole

$cmd route add blackhole $ip_dest
$cmd ro sh | tail -n 5 | grep -E "^blackhole $ip_dest"
$cmd route delete blackhole $ip_dest


# ## address

$cmd address show

$cmd ad sho

$cmd a s

$cmd -V

! $cmd adii sh

# ## link

$cmd link help 2>&1| grep 'Usage: ip link show'

$cmd lin hel 2>&1| grep 'Usage: ip link show'

$cmd link show | grep mtu

$cmd li sho | grep mtu

$cmd li ls | grep mtu

$cmd lin lst | grep mtu

$cmd l s | grep mtu

# ## neigh

$cmd nei show

echo "Tests passed!!"


#!/usr/bin/python
# encoding: utf8

"""
  iproute2mac
  CLI wrapper for basic network utilites on Mac OS X.
  Homepage: https://github.com/brona/iproute2mac

  The MIT License (MIT)
  Copyright (c) 2015 Bronislav Robenek <brona@robenek.me>
"""

import sys
import commands
import re
import string
import random

# Version
VERSION = '1.0.3'

# Utilities
SUDO = '/usr/bin/sudo'
IFCONFIG = '/sbin/ifconfig'
ROUTE = '/sbin/route'
NETSTAT = '/usr/sbin/netstat'
NDP = '/usr/sbin/ndp'
ARP = '/usr/sbin/arp'
NETWORKSETUP = '/usr/sbin/networksetup'

# Helper functions
def execute_cmd(cmd):
  print 'Executing: %s' % cmd
  print commands.getoutput(cmd)

# Generate random MAC address with XenSource Inc. OUI
# http://www.linux-kvm.com/sites/default/files/macgen.py
def randomMAC():
  mac = [ 0x00, 0x16, 0x3e,
    random.randint(0x00, 0x7f),
    random.randint(0x00, 0xff),
    random.randint(0x00, 0xff) ]
  return ':'.join(map(lambda x: "%02x" % x, mac))

# Help
def do_help():
  print "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }"
  print "       ip -V"
  print "where  OBJECT := { link | addr | route | neigh }"
  print "       OPTIONS := { -4 | -6 }"
  print ""
  print "iproute2mac"
  print "Homepage: https://github.com/brona/iproute2mac"
  print "This is CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems."
  print "Provided functionality is limited and command output is not fully compatible with iproute2."
  print "For advanced usage use netstat, ifconfig, ndp, arp, route and networksetup directly."

def do_help_route():
  print "Usage: ip route list"
  print "       ip route get ADDRESS"
  print "       ip route { add | del } ROUTE"
  print "ROUTE := PREFIX [ nexthop NH ]"

def do_help_addr():
  print "Usage: ip addr show [ dev STRING ]"
  print "       ip addr { add | del } PREFIX dev STRING"

def do_help_link():
  print "Usage: ip link show [ DEVICE ]"
  print "       ip link set dev DEVICE"
  print "                [ { up | down } ]"
  print "                [ address { LLADDR | factory | random } ]"
  print "                [ mtu MTU ]"

def do_help_neigh():
  print "Usage: ip neighbour { show }" # flush, delete, add

# Route Module
def do_route(argv,af):
  if (not argv) or (argv[0] in ['show','list','lst','sh','ls','l']):
    do_route_list(af)
  elif argv[0] in ['add','a'] and len(argv) >= 4:
    if len(argv)>0:
      argv.pop(0)
    do_route_add(argv,af)
  elif argv[0] in ['delete','del','d'] and len(argv) >= 2:
    if len(argv)>0:
      argv.pop(0)
    do_route_del(argv,af)
  elif argv[0] in ['get','g'] and len(argv)==2:
    argv.pop(0)
    do_route_get(argv,af)
  else:
    do_help_route()
    exit(1)

def do_route_list(af):
  if af==6:
    res=commands.getoutput(NETSTAT + " -nr -f inet6 2>/dev/null")
  else:
    res=commands.getoutput(NETSTAT + " -nr -f inet 2>/dev/null")
  res=res.split('\n')
  res=res[4:] # Removes first 4 lines
  for r in res:
    ra=r.split()
    if af == 6:
      target = ra[0]
      gw     = ra[1]
      flags  = ra[2]
      dev    = ra[3]
      target = re.sub('%[^ ]+/','/',target)
      if flags.find('W') != -1 or flags.find('H') != -1:
        continue
      if re.match("link.+",gw):
        print target + ' dev ' + dev + '  scope link'
      else:
        print target + ' via ' + gw + ' dev ' + dev
    else:
      target = ra[0]
      gw     = ra[1]
      flags  = ra[2]
      dev    = ra[5]
      if flags.find('W') != -1 or flags.find('H') != -1:
        continue
      if target == 'default':
        print 'default via ' + gw + ' dev ' + dev
      else:
        dots=target.count('.')
        if target.find('/') == -1:
          addr=target
          netmask=8+dots*8
        else:
          [addr,netmask] = target.split('/')

        if dots == 2:
          addr = addr + '.0'
        elif dots == 1:
          addr = addr + '.0.0'
        elif dots == 0:
          addr = addr + '.0.0.0'

        if re.match("link.+",gw):
          print addr + '/' + str(netmask)+ ' dev ' + dev + '  scope link'
        else:
          print addr + '/' + str(netmask) + ' via ' + gw + ' dev ' + dev

def do_route_add(argv,af):
  target=argv[0]
  via=argv[1]
  gw=argv[2]
  if via not in ['via','nexthop','gw']:
    do_help_route()
    exit(1)
  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "
  execute_cmd(SUDO + " " + ROUTE + " add " + inet + target + " " + gw)

def do_route_del(argv,af):
  target=argv[0]
  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "
  execute_cmd(SUDO + " " + ROUTE + " delete " + inet + target)

def do_route_get(argv,af):
  target=argv[0]

  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "

  res=commands.getoutput(ROUTE + " -n get " + inet + target)
  res=dict(re.findall('^\W*((?:route to|destination|gateway|interface)): (.+)$',res, re.MULTILINE))

  route_to=res['route to']
  dev=res['interface']
  via=res.get('gateway',"")

  if via=="":
    print route_to + " dev " + dev
  else:
    print route_to + " via " + via + " dev " + dev

# Addr Module
def do_addr(argv,af):
  if (not argv) or (argv[0] in ['show','list','lst','sh','ls','l']):
    if len(argv)>0:
      argv.pop(0)
    do_addr_show(argv,af)
  elif argv[0] in ['add','a'] and len(argv) >= 3:
    if len(argv)>0:
      argv.pop(0)
    do_addr_add(argv,af)
  elif argv[0] in ['delete','del','d'] and len(argv) >= 3:
    if len(argv)>0:
      argv.pop(0)
    do_addr_del(argv,af)
  else:
    do_help_addr()
    exit(1)

def addr_repl_netmask(matchobj):
  hexmask=matchobj.group(1)
  netmask=int(hexmask, 16)
  cidr = 0
  while netmask:
    cidr += netmask & 0x1
    netmask >>= 1
  return "/%d" % cidr

def do_addr_show(argv,af):
  if len(argv) > 0 and argv[0]=='dev':
    argv.pop(0)
  if len(argv) > 0:
    param=argv[0]
  else:
    param="-a"

  res=commands.getoutput(IFCONFIG + " " + param + " 2>/dev/null")
  res=re.sub('(%[^ ]+)? prefixlen ([\d+])','/\\2',res)
  res=re.sub(' netmask 0x([0-9a-fA-F]+)', addr_repl_netmask, res)
  res=re.sub('broadcast', 'brd', res)

  SIX=""
  if af == 6:
    SIX="6"
  elif af == 4:
    SIX=" "

  address_count=0
  output=""
  buff=""
  ifname=""
  for r in res.split('\n'):
    if re.match('^\w',r):
      if address_count > 0:
        output += buff
      buff=""
      ifname=re.findall("^([^:]+): .+",r)[0]
      address_count=0
      buff += r.rstrip() + "\n"
    elif re.match('^\W+inet' + SIX + '.+',r):
      address_count+=1
      if re.match('^\W+inet .+',r):
        buff += r.rstrip() + " " + ifname + "\n"
      else:
        buff += r.rstrip() + "\n"
    elif re.match('^\W+ether.+',r):
      buff += r.rstrip() + "\n"

  if address_count > 0:
    output += buff
  print output.rstrip()

def do_addr_add(argv,af):
  if len(argv) < 2:
    do_help_addr()
    exit(1)
  if argv[1]=="dev":
    argv.pop(1)
  addr=argv[0]
  dev=argv[1]
  inet=""
  if ":" in addr or af==6:
    af=6
    inet=" inet6"
  execute_cmd(SUDO + " " + IFCONFIG + " " + dev + inet + " add " + addr)

def do_addr_del(argv,af):
  if len(argv) < 2:
    do_help_addr()
    exit(1)
  if argv[1]=="dev":
    argv.pop(1)
  addr=argv[0]
  dev=argv[1]
  inet="inet"
  if ":" in addr or af==6:
    af=6
    inet="inet6"
  execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " " + inet + " " + addr + " remove")

# Link module
def do_link(argv,af):
  if (not argv) or (argv[0] in ['show','list','lst','sh','ls','l']):
    if len(argv)>0:
      argv.pop(0)
    do_link_show(argv,af)
  elif argv[0] == 'set':
    if len(argv)>0:
      argv.pop(0)
    do_link_set(argv,af)
  else:
    do_help_link()
    exit(1)

def do_link_show(argv,af):
  if len(argv) > 0 and argv[0]=='dev':
    argv.pop(0)
  if len(argv) > 0:
    param=argv[0]
  else:
    param="-a"

  res=commands.getoutput(IFCONFIG + " " + param + " 2>/dev/null").split('\n')
  for r in res:
    if not re.match('\s+inet.+',r):
      print r

def do_link_set(argv,af):
  if not argv:
    do_help_link()
    exit(1)
  elif argv[0]=='dev':
    argv.pop(0)

  if len(argv) < 2:
    do_help_link()
    exit(1)

  dev = argv[0]

  try:
    args=iter(argv)
    for arg in args:
      if arg=='up':
        execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " up")
      elif arg=='down':
        execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " down")
      elif arg in ['address','addr','lladdr']:
        addr=args.next()
        if addr in ['random','rand']:
          addr=randomMAC()
        elif addr=='factory':
          details=re.findall('^(?:Device|Ethernet Address): (.+)$',commands.getoutput(NETWORKSETUP + " -listallhardwareports"), re.MULTILINE)
          addr=details[details.index(dev)+1]
        execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " lladdr " + addr)
      elif arg=='mtu':
        mtu=int(args.next())
        execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " mtu " + str(mtu))
  except:
      do_help_link()
      exit(1)

# Neigh module
def do_neigh(argv,af):
  statuses = {'R': 'REACHABLE', 'S': 'STALE'}  # D = DELAY | F = FAILED
  if (not argv) or (argv[0] in ['show','list','ls','sh']):
    if af != 4:
      res=commands.getoutput(NDP + " -an 2>/dev/null")
      res=res.split('\n')
      res=res[1:]
      for r in res:
        ra=r.split()
        l3a=re.sub('%.+$','',ra[0]) # remove interface
        l2a=ra[1]
        dev=ra[2]
        exp=ra[3]
        stat=statuses[ra[4]]
        if l2a=='(incomplete)' and stat!='REACHABLE':
          print l3a + ' dev ' + dev + ' INCOMPLETE'
        else:
          print l3a + ' dev ' + dev + ' lladdr ' + l2a + ' ' + stat
    if af != 6:
      res=commands.getoutput(ARP + " -anl 2>/dev/null")
      res=res.split('\n')
      res=res[1:]
      for r in res:
        ra=r.split()
        l3a=ra[0]
        l2a=ra[1]
        dev=ra[4]
        if l2a=='(incomplete)':
          print l3a + ' dev ' + dev + ' INCOMPLETE'
        else:
          print l3a + ' dev ' + dev + ' lladdr ' + l2a + ' REACHABLE'
  # TODO: flush, delete, add
  else:
    do_help_neigh()
    exit(1)

# Main
def main(argv):
  argc=len(argv)
  if argc == 0:
    do_help()
    exit(1)

  # Address family
  af=-1 # default / both
  if argv[0] == '-6':
    af=6
    argv.pop(0)
  elif argv[0] == '-4':
    af=4
    argv.pop(0)

  if argv[0] == '-V':
    print "iproute2mac, v" + VERSION
    exit(0)

  # Module selection
  if argv[0] in ['address', 'addr', 'a']:
    argv.pop(0)
    do_addr(argv,af)
  elif argv[0] in ['route', 'ro', 'r']:
    argv.pop(0)
    do_route(argv,af)
  elif argv[0] in ['link','l']:
    argv.pop(0)
    do_link(argv,af)
  elif argv[0] in ['neighbour', 'neighbor', 'neigh', 'n']:
    argv.pop(0)
    do_neigh(argv,af)
  else:
    do_help()
    exit(1)

if __name__ == '__main__':
  main(sys.argv[1:])

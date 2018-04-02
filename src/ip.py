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
import types
import socket

# Version
VERSION = '1.2.1'

# Utilities
SUDO = '/usr/bin/sudo'
IFCONFIG = '/sbin/ifconfig'
ROUTE = '/sbin/route'
NETSTAT = '/usr/sbin/netstat'
NDP = '/usr/sbin/ndp'
ARP = '/usr/sbin/arp'
NETWORKSETUP = '/usr/sbin/networksetup'

# Helper functions
def perror(*args):
    sys.stderr.write(*args)
    sys.stderr.write("\n")

def execute_cmd(cmd):
  print 'Executing: %s' % cmd
  status, output = commands.getstatusoutput(cmd)
  if status == 0:  # unix/linux commands 0 true, 1 false
    print output
    return True
  else:
    perror(output)
    return False

def matches(arg, command):
  return command.startswith(arg)

# Handles passsing return value, error messages and program exit on error
def help_msg(help_func):
  def wrapper(func):
    def inner(*args, **kwargs):
      if not func(*args, **kwargs):
        specific = eval(help_func)
        if specific:
          if type(specific) == types.FunctionType:
            if args and kwargs:
              specific(*args, **kwargs)
            else:
              specific()
            return False
          else:
            raise Exception("Function expected for: " + help_func)
        else:
          raise Exception("Function variant not defined: " + help_func)
      return True
    return inner
  return wrapper

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
  perror("Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }")
  perror("       ip -V")
  perror("where  OBJECT := { link | addr | route | neigh }")
  perror("       OPTIONS := { -4 | -6 }")
  perror("")
  perror("iproute2mac")
  perror("Homepage: https://github.com/brona/iproute2mac")
  perror("This is CLI wrapper for basic network utilities on Mac OS X inspired with iproute2 on Linux systems.")
  perror("Provided functionality is limited and command output is not fully compatible with iproute2.")
  perror("For advanced usage use netstat, ifconfig, ndp, arp, route and networksetup directly.")
  exit(255)

def do_help_route():
  perror( "Usage: ip route list")
  perror( "       ip route get ADDRESS")
  perror( "       ip route { add | del } ROUTE")
  perror( "ROUTE := PREFIX [ nexthop NH ]")
  exit(255)

def do_help_addr():
  perror( "Usage: ip addr show [ dev STRING ]")
  perror( "       ip addr { add | del } PREFIX dev STRING")
  exit(255)

def do_help_link():
  perror( "Usage: ip link show [ DEVICE ]")
  perror( "       ip link set dev DEVICE")
  perror( "                [ { up | down } ]")
  perror( "                [ address { LLADDR | factory | random } ]")
  perror( "                [ mtu MTU ]")
  exit(255)

def do_help_neigh():
  perror( "Usage: ip neighbour { show | flush } [ dev DEV ]") # delete, add
  exit(255)

# Route Module
@help_msg('do_help_route')
def do_route(argv,af):
  if not argv:
    return do_route_list(af)
  elif 'add'.startswith(argv[0]) and len(argv) >= 4:
    if len(argv) > 0:
      argv.pop(0)
    return do_route_add(argv,af)
  elif 'delete'.startswith(argv[0]) and len(argv) >= 2:
    if len(argv) > 0:
      argv.pop(0)
    return do_route_del(argv,af)
  elif 'list'.startswith(argv[0]) or 'show'.startswith(argv[0]) or 'lst'.startswith(argv[0]):
    # show help if there is an extra argument on show
    if len(argv) > 1: return False
    return do_route_list(af)
  elif 'get'.startswith(argv[0]) and len(argv) == 2:
    argv.pop(0)
    return do_route_get(argv,af)
  else:
    return False
  return True

def do_route_list(af):
  if af==6:
    status,res = commands.getstatusoutput(NETSTAT + " -nr -f inet6 2>/dev/null")
  else:
    status,res = commands.getstatusoutput(NETSTAT + " -nr -f inet 2>/dev/null")
  if status:
      perror(res)
      return False
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
  return True

def do_route_add(argv,af):
  target=argv[0]
  via=argv[1]
  gw=argv[2]
  if via not in ['via','nexthop','gw','dev']:
    do_help_route()
  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "
  if "dev"==via: gw = "-interface " + gw
  return execute_cmd(SUDO + " " + ROUTE + " add " + inet + target + " " + gw)

def do_route_del(argv,af):
  target=argv[0]
  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "
  return execute_cmd(SUDO + " " + ROUTE + " delete " + inet + target)

def do_route_get(argv,af):
  target=argv[0]

  inet=""
  if ":" in target or af==6:
    af=6
    inet="-inet6 "
    family=socket.AF_INET6
  else:
    family=socket.AF_INET

  status,res = commands.getstatusoutput(ROUTE + " -n get " + inet + target)
  if status: # unix status or not in table
    perror(res)
    return False
  if res.find('not in table') >= 0:
      perror(res)
      exit(1)

  res=dict(re.findall('^\W*((?:route to|destination|gateway|interface)): (.+)$',res, re.MULTILINE))

  route_to=res['route to']
  dev=res['interface']
  via=res.get('gateway',"")

  try:
    s = socket.socket(family, socket.SOCK_DGRAM)
    s.connect((route_to, 7))
    src_ip = s.getsockname()[0]
    s.close()
    src = "  src " + src_ip
  except:
    src = ""

  if via=="":
    print route_to + " dev " + dev + src
  else:
    print route_to + " via " + via + " dev " + dev + src
  return True

# Addr Module
@help_msg('do_help_addr')
def do_addr(argv,af):
  if not argv:
    return do_addr_show(argv,af)
  elif 'add'.startswith(argv[0]) and len(argv) >= 3:
    if len(argv)>0:
      argv.pop(0)
    return do_addr_add(argv,af)
  elif 'delete'.startswith(argv[0]) and len(argv) >= 3:
    if len(argv)>0:
      argv.pop(0)
    return do_addr_del(argv,af)
  elif 'list'.startswith(argv[0]) or 'show'.startswith(argv[0]) or 'lst'.startswith(argv[0]):
    if len(argv)>0:
      argv.pop(0)
    return do_addr_show(argv,af)
  else:
    return False
  return True

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

  status,res = commands.getstatusoutput(IFCONFIG + " " + param + " 2>/dev/null")
  if status:
    if res == "": perror(param + ' not found')
    else: perror(res)
    return False
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
  return True

def do_addr_add(argv,af):
  if len(argv) < 2:
    return False
  if argv[1]=="dev":
    argv.pop(1)
  else:
    return False
  try:
    addr=argv[0]
    dev=argv[1]
  except IndexError:
    perror('dev not found')
    exit(1)
    return False
  inet=""
  if ":" in addr or af==6:
    af=6
    inet=" inet6"
  return execute_cmd(SUDO + " " + IFCONFIG + " " + dev + inet + " add " + addr)

def do_addr_del(argv,af):
  if len(argv) < 2:
    return False
  if argv[1]=="dev":
    argv.pop(1)
  try:
    addr=argv[0]
    dev=argv[1]
  except IndexError:
    perror('dev not found')
    exit(1)
    return False
  inet="inet"
  if ":" in addr or af==6:
    af=6
    inet="inet6"
  return execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " " + inet + " " + addr + " remove")

# Link module
@help_msg('do_help_link')
def do_link(argv,af):
  if (not argv):
    return do_link_show(argv,af)
  elif 'show'.startswith(argv[0]) or 'list'.startswith(argv[0]) or 'lst'.startswith(argv[0]):
    if len(argv) > 0:
      argv.pop(0)
    return do_link_show(argv,af)
  elif 'set'.startswith(argv[0]):
    if len(argv) > 0:
      argv.pop(0)
    return do_link_set(argv,af)
  else:
    return False
  return True

def do_link_show(argv,af):
  if len(argv) > 0 and argv[0]=='dev':
    argv.pop(0)
  if len(argv) > 0:
    param=argv[0]
  else:
    param="-a"

  status,res = commands.getstatusoutput(IFCONFIG + " " + param + " 2>/dev/null")
  if status: # unix status
    if res == "": perror(param + ' not found')
    else: perror(res)
    return False
  for r in res.split('\n'):
    if not re.match('\s+inet.+',r):
      print r
  return True

def do_link_set(argv,af):
  if not argv:
    return False
  elif argv[0]=='dev':
    argv.pop(0)

  if len(argv) < 2:
    return False

  dev = argv[0]

  try:
    args=iter(argv)
    for arg in args:
      if arg=='up':
        if not execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " up"): return False
      elif arg=='down':
        if not execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " down"): return False
      elif arg in ['address','addr','lladdr']:
        addr=args.next()
        if addr in ['random','rand']:
          addr=randomMAC()
        elif addr=='factory':
          (status,res)=commands.getstatusoutput(NETWORKSETUP + " -listallhardwareports")
          if status != 0:
            return False
          details=re.findall('^(?:Device|Ethernet Address): (.+)$', res, re.MULTILINE)
          addr=details[details.index(dev)+1]
        if not execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " lladdr " + addr): return False
      elif arg=='mtu':
        mtu=int(args.next())
        if not execute_cmd(SUDO + " " + IFCONFIG + " " + dev + " mtu " + str(mtu)): return False
  except:
    return False
  return True

# Neigh module
def do_neigh(argv,af):
  statuses = {'R': 'REACHABLE', 'S': 'STALE'}
  idev = None
  if len(argv) > 1:
    if len(argv) < 3 and argv[1] != 'dev':
      do_help_neigh()
    idev = argv[2]
  if (not argv) or (argv[0] in ['show','sh','s','list','lst','ls']):
    if af != 4:
      (status,res) = commands.getstatusoutput(NDP + " -an 2>/dev/null")
      if status != 0:
        return False
      res=res.split('\n')
      res=res[1:]
      for r in res:
        ra=r.split()
        l3a=re.sub('%.+$','',ra[0]) # remove interface
        l2a=ra[1]
        dev=ra[2]
        exp=ra[3]
        if ra[4] in statuses:
          stat=statuses[ra[4]]
        else:
          stat='INCOMPLETE'
        if l2a=='(incomplete)' and stat!='REACHABLE':
          print l3a + ' dev ' + dev + ' INCOMPLETE'
        else:
          print l3a + ' dev ' + dev + ' lladdr ' + l2a + ' ' + stat
    if af != 6:
      if idev:
        (status,res)=commands.getstatusoutput(ARP + " -anli " + idev +" 2>/dev/null")
      else:
        (status,res)=commands.getstatusoutput(ARP + " -anl 2>/dev/null")
      if status != 0:
        return False
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
  # TODO: delete, add
  elif argv[0] in ['f', 'fl', 'flush']:
    if not idev:
        perror('Flush requires arguments.')
        exit(1)
    if af != 4:
      # TODO: dev option for ipv6 (ndp command doesn't support it now)
      if not execute_cmd(SUDO + " " + NDP + " -c"): return False
    if af != 6:
      if not execute_cmd(SUDO + " " + ARP + " -a -d -i " + idev): return False
  else:
    do_help_neigh()

  return True

# Match iproute2 commands
# https://git.kernel.org/pub/scm/linux/kernel/git/shemminger/iproute2.git/tree/ip/ip.c#n75
cmds = [
  [ "address",    do_addr ],
  [ "route",      do_route ],
  [ "neighbor",   do_neigh ],
  [ "neighbour",  do_neigh ],
  [ "link",       do_link ],
]

# Main
@help_msg('do_help')
def main(argv):
  argc=len(argv)

  if argc == 0:
    return False

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

  if argv[0] == 'help':
    do_help()
    exit(0)

  for cmd, cmd_func in cmds:
    if cmd.startswith(argv[0]):
      argv.pop(0)
      # Functions return true or terminate with exit(255) see help_msg and do_help*
      return cmd_func(argv, af)

  perror('Object "{}" is unknown, try "ip help".'.format(argv[0]))
  exit(1)

if __name__ == '__main__':
  main(sys.argv[1:])

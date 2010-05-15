#!/usr/bin/env python
from servers import stop_servers

ips = []
ips.append( open('server.ip').read() )
ips.extend( open('clients.ip').read().split('\n') )

stop_servers(ips)

print "Done."
#!/usr/bin/env python
from servers import start_server, start_clients, shell
from settings import NUM_CLIENTS

server = start_server()
clients = start_clients(NUM_CLIENTS)

open("test_client/server.ip", "w").write(server.public_ip[0])
open("server.ip", "w").write(server.public_ip[0])
open("clients.ip", "w").write("\n".join(c.public_ip[0] for c in clients))

shell('rsync -qazr test_server root@%s:/www/services' % server.public_ip[0])
for client in clients:
    shell('rsync -qazr test_client root@%s:/root' % client.public_ip[0])

print "Done."
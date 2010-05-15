import os, paramiko, eventlet
from settings import SSH_PUB

key = paramiko.RSAKey.from_private_key_file( os.path.expanduser(SSH_PUB) )

def run_client(client):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(client.public_ip[0], username='root', pkey = mykey)
    print "Executing client profiler..."
    stdin, stdout = ssh.exec_command(" ; ".join([
        "cd test_client",
        "python profile.py"
    ]))
    print stdout.readlines()
    print "Client done."
    ssh.close()

pool = eventlet.GreenPool(200)
pool.imap(run_client, clients)
pool.waitall()

print "Done."
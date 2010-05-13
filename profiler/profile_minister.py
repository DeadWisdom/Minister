import os, eventlet, shlex, paramiko
from eventlet.green import subprocess

from libcloud.types import Provider 
from libcloud.providers import get_driver
from libcloud.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment 
from settings import USER, KEY, DRIVER, IMAGE, SIZE, SSH_PUB

### Setup LibCloud ###
Driver = get_driver(getattr(Provider, DRIVER))
conn = Driver(USER, KEY)
 
image = conn.list_images()[IMAGE]
size = conn.list_sizes()[SIZE]

### Setup Tsung ###
NUM_CLIENTS = 2
TSUNG_TEMPLATE = open('tsung_template.xml').read()

### Ready Deployment Scripts ###
ssh_pub = open( os.path.expanduser(SSH_PUB) ).read()
sd = SSHKeyDeployment( ssh_pub )
server_script = ScriptDeployment( " ; ".join([
    "apt-get update",
    "apt-get install git-core python-setuptools build-essential gcc erlang python-dev -y",
    "easy_install pip virtualenv",
    "groupadd minister 2>null",
    "useradd -g minister minister 2>null",
    "mkdir /www 2>null",
    "cd /www",
    "pip install -E env -e git+git://github.com/DeadWisdom/Minister.git#egg=minister",
    "chown -R minister:minister /www",
    "env/bin/minister . --start"
]) )

### Support Functions ###
def shell(cmd):
    args = shlex.split(str(cmd))
    print "-", args
    try:
        popen = subprocess.Popen(list(args), cwd=os.curdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = popen.communicate()
    except OSError, e:
        err = str(e)
        out = None
    
    return out, err

def start_server():
    print "Staring server..."
    msd = MultiStepDeployment([sd, server_script]) 
    node = conn.deploy_node(name='Server', image=image, size=size, deploy=msd)
    try:
        shell('rsync -qazr test_service root@%s:/www/services' % node.public_ip[0])
    except Exception, e:
        print "Rsync failure, destroying node..."
        node.destroy()
        raise e
    print "Server started at", node.public_ip[0]
    return node

def start_client(index):
    print "Staring client..."
    node = conn.deploy_node(name='Client %d' % index, image=image, size=size, deploy=sd)
    print "Client started at", node.public_ip[0]
    return node

def start_tsung(server, clients):
    context = {
        'server': '<server host="%s" port="8000" type="tcp"/>' % server.public_ip[0],
        'clients': "\n".join(['<client host="%s" use_controller_vm="false" maxusers="800"/>' % c.public_ip[0] for c in clients]),
        'monitor': '<monitor host="%s" type="erlang"/>' % server.public_ip[0],
        'get': '<http url="http://%s/" version="1.1" method="GET"/>' % server.public_ip[0]
    }
    src = TSUNG_TEMPLATE % context
    open("tsung.xml", "w").write(src)
    try:
        shell('tsung -f tsung.xml start')
    finally:
        shell('tsung -f tsung.xml stop')

if __name__ == '__main__':
    server = start_server()
    clients = []
    pool = eventlet.GreenPool(200)
    
    try:
        clients = [node for node in pool.imap(start_client, range(1, NUM_CLIENTS + 1))]
        
        start_tsung(server, clients)
        
        print "Finished."
    except Exception, e:
        print "Exception raised:", e
    
    "Destroying server..."
    server.destroy()
    print "Server dead."
    print "Destroying clients..."
    for c in clients:
        c.destroy()
    print "Clients dead."
    print "Goodbye."
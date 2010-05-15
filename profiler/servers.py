import sys, os, subprocess, shlex, eventlet

from eventlet.green import socket

from libcloud.types import Provider 
from libcloud.providers import get_driver
from libcloud.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment 
from settings import USER, KEY, DRIVER, IMAGE, SIZE, SSH_PUB


### Setup LibCloud ###
Driver = get_driver(getattr(Provider, DRIVER))
conn = Driver(USER, KEY)
 
image = conn.list_images()[IMAGE]
size = conn.list_sizes()[SIZE]


### Ready Deployment Scripts ###
ssh_pub = open( os.path.expanduser(SSH_PUB) ).read()
sd = SSHKeyDeployment( ssh_pub )
server_script = [
    "groupadd minister 2>null",
    "useradd -g minister minister 2>null",
    "mkdir /www 2>null",
    "cd /www",
    "pip install -E env -e git+git://github.com/DeadWisdom/Minister.git#egg=minister",
    "chown -R minister:minister /www",
    "env/bin/minister . --start"
]

setup_script = [
    "apt-get update",
    "apt-get install git-core python-setuptools build-essential gcc python-dev -y",
    "easy_install pip virtualenv eventlet",
]


### Support Functions ###
def confirm(prompt, default=False):
    while True:
        ans = raw_input(prompt)
        if not ans:
            return default
        if ans not in ['y', 'Y', 'n', 'N']:
            print 'please enter y or n.'
            continue
        if ans == 'y' or ans == 'Y':
            return True
        if ans == 'n' or ans == 'N':
            return False

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
    print "Starting server..."
    commands = ScriptDeployment( " ; ".join(setup_script + server_script) )
    msd = MultiStepDeployment([sd, commands]) 
    node = conn.deploy_node(name='Server', image=image, size=size, deploy=msd)
    print "Server started at", node.public_ip[0]
    return node

def start_client(index):
    print "Starting client..."
    commands = ScriptDeployment( " ; ".join(setup_script) )
    msd = MultiStepDeployment([sd, commands])
    node = conn.deploy_node(name='Client %d' % index, image=image, size=size, deploy=msd)
    print "Client started at", node.public_ip[0]
    return node

def start_clients(number):
    pool = eventlet.GreenPool()
    return list( pool.imap(start_client, range(1, number + 1)) )

def stop_servers(ips):
    for node in reversed( conn.list_nodes() ):
        if node.public_ip[0] in ips:
            print "Stopping", node.public_ip[0]
            node.destroy()
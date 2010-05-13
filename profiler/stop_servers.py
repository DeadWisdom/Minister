from libcloud.types import Provider 
from libcloud.providers import get_driver
from settings import DRIVER, USER, KEY

Driver = get_driver(getattr(Provider, DRIVER))
conn = Driver(USER, KEY)

for node in reversed( conn.list_nodes() ):
    print "Stopping", node.public_ip[0]
    node.destroy()
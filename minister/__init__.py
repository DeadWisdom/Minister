# TODO:
#   php         -  rewrite whphp, adjust fastcgi_app
#   logging     -  create logging facility
#   layout      -  destroy tokens.json, make layout.json
#   admin       -  fix the admin to work with the new layout

from manager import Manager

def serve(address=('', 8000), path=None, layout=None, debug=False):
    manager = Manager(path, layout)
    manager.serve(address, debug)
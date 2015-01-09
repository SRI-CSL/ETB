Prerequisites: those of the etb3 and 

sudo apt-get install python-twisted
sudo apt-get install sqlite

mail?

STEP 0: setup the servers.db  ( ./sqlite.py will do this)

STEP 1: check the preferences ( etb_metaserver.ini )  the defaults
in the repo aren't usually good (~ port etc). Make sure
the server_farm_path exists




================================================================

This is an attempt at a "hello world" for an ETB proxy gateway.

STEP 1: start two etbs running on localhost at  8085 and 8086 
respectively:

etb1: 8085

etb2: 8086 

STEP 2: start the middleman:
     
./proxy.py


STEP 3:


either 

connect etb1 to etb2 via 

/  >proxylink(localhost, 8000, etb1, etb2)


or connect etb2 to etb1 via


/  >proxylink(localhost, 8000, etb2, etb1)


STEP 4: You can also talk to either etb indirectly if you want:

For example:

etb_clients/etb-shell/etb-shell -p 8000 -n etb1

Note the new command line option: -n for name 

(p for path was already taken by p for port).

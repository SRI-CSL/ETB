
all: kill clean setup start connect

start:
	(cd net1-1; ../../../src/etbd.py --conf etb_conf.ini --log ../log1-1 &)
	(cd net1-2; ../../../src/etbd.py --conf etb_conf.ini --log ../log1-2 &)
	(cd net1-3; ../../../src/etbd.py --conf etb_conf.ini --log ../log1-3 &)
	(cd net2-1; ../../../src/etbd.py --conf etb_conf.ini --log ../log2-1 &)
	(cd net2-2; ../../../src/etbd.py --conf etb_conf.ini --log ../log2-2 &)
	sleep 5

connect: connect1 connect2 link

connect1:
	../../etb_clients/etb-shell/etb-shell --port 43765 --batch "connect(localhost, 43766)"
	../../etb_clients/etb-shell/etb-shell --port 43765 --batch "connect(localhost, 43767)"

connect2:
	../../etb_clients/etb-shell/etb-shell --port 43768 --batch "connect(localhost, 43769)"

link:
	../../etb_clients/etb-shell/etb-shell --port 43765 --batch "link(localhost, 43768, 43765)"

setup:
	(cd ../; python ./setup_test_area.py)

tail:
	tail -f log1-1 log1-2 log1-3 log2-1 log2-2

kill:
	killall -9 Python || true

clean:
	rm -rf net?-? log?-?

.PHONY: connect connect1 connect2 link setup start clean kill

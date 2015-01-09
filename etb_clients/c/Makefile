
test: etb_core.o test.c
	gcc `xmlrpc-c-config client --libs` -ljson -L libb64-1.2/src -lb64 -o test etb_core.o test.c

etb.o: etb.c etb.h
	gcc `xmlrpc-c-config client --cflags` -I libb64-1.2/include -c etb.c 

etb_core.o: etb_core.c etb_core.h
	gcc `xmlrpc-c-config client --cflags` -I libb64-1.2/include -c etb_core.c 
clean:
	rm -f *.o test

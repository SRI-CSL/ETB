

test: test.cmo etb.cmo etb_stubs.o ../c/etb_core.o
	ocamlc.opt -o test -custom etb.cmo test.cmo etb_stubs.o ../c/etb_core.o -cclib "`xmlrpc-c-config client --libs`" -cclib -ljson -cclib "-L ../c/libb64-1.2/src -lb64"

test.ml: etb.cmi

top: etb.cmo etb_stubs.o ../c/etb_core.o
	ocamlmktop -o etbtop -custom etb.cmo etb_stubs.o ../c/etb_core.o -cclib "`xmlrpc-c-config client --libs`" -cclib -ljson -cclib "-L ../c/libb64-1.2/src -lb64"

etb_stubs.o: etb_stubs.c ../c/etb_core.h
	ocamlc.opt -c -I ../c etb_stubs.c

clean:
	rm -f *.cm[iox] *.o

%.cmo: %.ml
	ocamlc.opt -c $<
%.cmi: %.mli
	ocamlc.opt -c $<

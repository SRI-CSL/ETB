TGZFLE=etb.tar.gz

dist:
	rm -rf dist ${TGZFLE} && mkdir dist && cd dist && \
	git clone dragon@dragon.csl.sri.com:etb.git etb && \
	../add_license.py etb/src/*.py etb/src/etb/*.py etb/src/wrappers_available/*.py  etb/tests/*.py etb/demos/*/*/*.py etb/etb_clients/etb-shell/etb-shell  && \
	rm -rf etb/src/datalogv2 && \
	tar zcf ${TGZFLE} \
		etb/README \
	 	etb/INSTALL \
	 	etb/LICENSE \
		etb/src/ \
		etb/tests/ \
		etb/etb_clients/etb-shell/ \
		etb/demos/make/ \
		etb/demos/meta/ \
		etb/demos/allsat/ \
		etb/demos/allsat2/ \
		etb/demos/k-induction/ \
		etb/doc/images \
		etb/doc/Makefile \
		etb/doc/etb_clients.tex \
		etb/doc/etb_setup.tex \
		etb/doc/etb_apis.tex \
		etb/doc/etb_wrappers.tex && \
	mv ${TGZFLE} ../ && cd ../ && rm -rf dist && \
	echo "ETB distribution created in ${TGZFLE}"



clean:
	find . -name "*.pyc" | xargs -n 1 rm -f
	find . -name "*~" | xargs -n 1 rm -f
	cd doc; make clean
	cd tests; make clean

.PHONY: dist

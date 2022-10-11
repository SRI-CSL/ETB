export PYTHONPATH = ..

all: unittests
	@PYTHONPATH=$$PYTHONPATH \
	 python ./utils_test.py && \
	 python ./in_range.py && \
	 python ./files.py && \
	 python ./remote_queries.py && \
	 python ./pingpong_test.py && \
	 python ./claims.py && \
	 python ./handles.py && \
	 python ./demos.py

path:
	@PYTHONPATH=$$PYTHONPATH \
	python -c "import sys; print(sys.path)"

unittests:
	@echo "\n...\n...\n...\nRunning unit tests...\n"
	@cd .. && \
	python -m unittest discover -p "*_test*" -v && \
	cd tests

test.html: test.txt
	../etb_clients/etb-asciidoc/etb-asciidoc test.txt

clean:
	rm -f test.html *.log main_* *.pyc *~



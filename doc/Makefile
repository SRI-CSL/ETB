# make documentation

LATEXMK = latexmk
LATEXMKFLAGS = -pdf -pdflatex='pdflatex -shell-escape -file-line-error -synctex=1'

all: tex 

tex: etb_guide.pdf # etb_wrappers.pdf etb_clients.pdf etb_apis.pdf etb_setup.pdf

etb_guide.pdf : etb_guide.tex etb_tutorial.tex etb_setup.tex \
                etb_wrappers.tex etb_clients.tex etb_config.tex
	$(LATEXMK) $(LATEXMKFLAGS) etb_guide.tex

# This needs pigments and minted to compile
#   minted comes with recent LaTeX
#   pigments can be installed with: sudo easy_install Pygments

%.tex: %.org
	emacs --batch $< -f org-export-as-latex --kill

etb_wrappers.pdf: etb_wrappers.tex
	@$(LATEXMK) $(LATEXMKFLAGS) etb_wrappers.tex

etb_clients.pdf: etb_clients.tex
	@$(run-latex)

#added this target after gh left
etb_apis.pdf: etb_apis.tex
	@$(run-latex)

#added this target after gh left
etb_setup.pdf: etb_setup.tex images/sshTunnel.png images/2waytunnel.png
	@$(run-latex)

clean:
	rm -f *.aux *.log *.pdf *~

.PHONY:  tex


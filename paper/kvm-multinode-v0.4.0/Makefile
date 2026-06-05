PDF=main.pdf
TEX=main.tex

all:
	pdflatex -interaction=nonstopmode $(TEX)
	bibtex main || true
	pdflatex -interaction=nonstopmode $(TEX)
	pdflatex -interaction=nonstopmode $(TEX)

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc *.lof *.lot *.fls *.fdb_latexmk

distclean: clean
	rm -f $(PDF)

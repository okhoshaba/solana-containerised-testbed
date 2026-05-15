# Build instructions

This is article draft v1.1: `From Synthetic Benchmarks to Controlled Solana Testbeds`.

Recommended build sequence when BibTeX is available:

```bash
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

A generated `main.bbl` file is included so the PDF can also be rebuilt with `pdflatex` only if BibTeX is unavailable:

```bash
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

Version v1.1 adds the practical GitHub integration workflow:

- local pre-flight checks;
- copy workflow for article, docs, prompts, and scripts;
- local PDF rebuild command;
- explicit git staging plan;
- recommended commit message and commit body;
- rollback and safety checks;
- helper integration and validation scripts.

Empirical datasets are still not required for this methodological version.


## Empirical pilot derived files

Derived summaries are stored in `empirical-pilot/`. The raw uploaded archives are not redistributed in this package.

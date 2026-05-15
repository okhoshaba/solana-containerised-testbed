# Synthetic benchmarking Solana article

Current integrated draft: **v1.1 empirical pilot**.

This directory contains the LaTeX source and generated PDF for the article:

**From Synthetic Benchmarks to Controlled Solana Testbeds**

The v1.1 draft includes a preliminary single-host empirical pilot based on baseline, low transaction-load, and medium transaction-load runs. The pilot validates the measurement pipeline; it does not claim general Solana performance limits.

## Build

```bash
bash ../../scripts/build_synthetic_benchmarks_article.sh paper/synthetic-benchmarks-solana
```

or from this directory:

```bash
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

`main.bbl` is committed so the article can be rebuilt without running BibTeX.

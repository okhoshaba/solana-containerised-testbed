# Zenodo metadata for article package

## Recommended Zenodo record type

- Upload type: Publication
- Publication type: Preprint
- Version: v0.4-article-txload-described
- Language: English
- Access right: Open access
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0)

## Title

From Synthetic Benchmarks to Feedback-Controlled Testbeds: Observability and Workload Management in a Containerised Solana Localnet

## Creator

- Oleksandr Khoshaba
  - Affiliation: Vinnytsia National Technical University
  - ORCID: 0000-0001-5375-6280
  - Email: Oleksandr.Khoshaba@gmail.com

## Publication date

2026-05-17

## Description / Abstract

This archive contains the LaTeX source, generated PDF, bibliography, and workload-generation script for the article "From Synthetic Benchmarks to Feedback-Controlled Testbeds: Observability and Workload Management in a Containerised Solana Localnet".

The article argues that synthetic benchmarking in distributed systems is evolving from open-loop performance measurement towards reproducible experimental testbeds that combine workload generation, observability, dataset production, and future feedback-control interfaces. The case study is a containerised private Solana localnet with validator, wallet/workload components, Yellowstone/Geyser-based observability, monitoring services, and Prometheus-compatible metrics.

This version explicitly documents the transaction-load mechanism used in the empirical pilot. The controlled workload profiles `txload-low` and `txload-medium` were implemented using `scripts/run_article_txload_container_v0_4.sh`. The script creates temporary payer and recipient keypairs inside the validator container, funds the payer account through a local airdrop, and then sequentially submits native SOL transfer transactions through the local RPC endpoint. Each transfer sends 0.000001 SOL from the payer to the recipient and records workload-side evidence including timestamps, sequence numbers, exit codes, durations, signatures, per-transfer logs, and a summary JSON.

The empirical pilot is intentionally limited. It validates the measurement pipeline and the distinguishability of controlled transaction-load profiles. It should not be interpreted as a general Solana mainnet performance benchmark, a multi-validator scalability study, or a production-like application-level workload evaluation.

## Keywords

synthetic benchmark; distributed systems; Solana; localnet; containerised testbed; Yellowstone; Geyser; Prometheus; observability; workload generation; feedback control; multi-agent reinforcement learning; reproducible research

## Related identifiers

- GitHub repository: https://github.com/okhoshaba/solana-containerised-testbed
- Related Zenodo software record: https://doi.org/10.5281/zenodo.20098291
- Related Zenodo technical note: https://doi.org/10.5281/zenodo.20167936

## Files in this archive

- `main.pdf` — generated PDF of the article.
- `main.tex` — LaTeX source of the article.
- `references.bib` — BibTeX bibliography.
- `scripts/run_article_txload_container_v0_4.sh` — workload script used for sequential native SOL transfer generation.
- `README-for-article.txt` — human-readable archive description and reuse notes.

## Recommended citation format before DOI assignment

Khoshaba, O. (2026). From Synthetic Benchmarks to Feedback-Controlled Testbeds: Observability and Workload Management in a Containerised Solana Localnet (v0.4-article-txload-described) [Preprint]. Zenodo. DOI: 10.5281/zenodo.20254448


From Synthetic Benchmarks to Feedback-Controlled Testbeds:
Observability and Workload Management in a Containerised Solana Localnet

Author:
Oleksandr Khoshaba
Vinnytsia National Technical University
Oleksandr.Khoshaba@gmail.com

Package version:
v0.4-article-txload-described

Package date:
2026-05-17

Purpose of this archive:
This archive preserves the article source, generated PDF, bibliography, and workload-script evidence for a methodological study of synthetic benchmarking, observability, and workload management in a containerised Solana localnet.

Main files:
- main.pdf
  Generated PDF version of the article.

- main.tex
  LaTeX source of the article.

- references.bib
  BibTeX bibliography used by the article.

- scripts/run_article_txload_container_v0_4.sh
  Shell script used to generate the controlled transaction-load profiles in the empirical pilot.

- metadata.md
  Suggested Zenodo metadata fields.

- checksums.sha256
  SHA-256 checksums for the files in this archive.

What the workload script does:
The script runs inside a containerised Solana localnet environment. It creates temporary payer and recipient keypairs inside the validator container, funds the payer through a local airdrop, and then sequentially submits native SOL transfer transactions through the local RPC endpoint. Each transaction transfers 0.000001 SOL from the payer to the recipient. The script records workload-side evidence: timestamp, sequence number, profile, configured rate, command exit code, execution duration, transaction signature, per-transfer log path, and a final summary JSON.

Interpretation boundary:
The txload-low and txload-medium results validate the measurement pipeline and show that controlled transaction-load profiles are distinguishable from baseline operation. They do not represent a full Solana mainnet performance benchmark, a production workload, a multi-validator scalability result, or a complex application-level workload. Future work should add asynchronous or batched workload generation, richer transaction mixes, RPC pressure profiles, Geyser/Yellowstone stream-latency measurements, paired observability overhead runs, cross-host reproducibility tests, Kubernetes-based deployment, and later feedback-control experiments.

Suggested Zenodo settings:
- Upload type: Publication
- Publication type: Preprint
- Access: Open access
- Licence: CC BY 4.0
- Language: English
- Version: v0.4-article-txload-described

Suggested citation before DOI assignment:
Khoshaba, O. (2026). From Synthetic Benchmarks to Feedback-Controlled Testbeds: Observability and Workload Management in a Containerised Solana Localnet (v0.4-article-txload-described) [Preprint]. Zenodo. DOI_TO_BE_ASSIGNED_BY_ZENODO

After Zenodo publication:
1. Copy the final DOI from Zenodo.
2. Update the GitHub repository documentation with the DOI.
3. Add the Zenodo work to ORCID using the DOI.
4. If required, create a short GitHub commit recording the DOI update.

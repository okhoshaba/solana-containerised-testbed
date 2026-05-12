# Agent Notes for the Monitor Component

- Use English for explanations, change summaries, commit messages, pull request comments, and code comments.
- Keep runtime configuration examples reproducible and container-oriented.
- Avoid committing private keys, seed phrases, tokens, `.env` files, generated logs, or runtime output.
- Prefer explicit container image names such as `docker.io/library/...` to avoid Podman short-name resolution issues.
- The monitor connects to the validator through the Compose network using `validator:10000`.
- Prometheus metrics must bind to `0.0.0.0` inside the container so that the host port mapping works.

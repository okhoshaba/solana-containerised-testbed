ARG SOLANA_BASE_IMAGE=docker.io/khoshaba/solana-source-noavx2:v1.18.25-noavx2-ivybridge
FROM ${SOLANA_BASE_IMAGE}

COPY wallet-init.sh /usr/local/bin/wallet-init.sh
RUN chmod +x /usr/local/bin/wallet-init.sh

ENTRYPOINT ["/usr/local/bin/wallet-init.sh"]


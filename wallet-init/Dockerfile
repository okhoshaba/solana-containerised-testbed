FROM localhost/solana-source-noavx2:v1.18.25

COPY wallet-init.sh /usr/local/bin/wallet-init.sh
RUN chmod +x /usr/local/bin/wallet-init.sh

ENTRYPOINT ["/usr/local/bin/wallet-init.sh"]


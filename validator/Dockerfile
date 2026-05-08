FROM localhost/solana-source-noavx2:v1.18.25

COPY entrypoint.sh /usr/local/bin/validator-entrypoint.sh
RUN chmod +x /usr/local/bin/validator-entrypoint.sh

EXPOSE 8899 10000

ENTRYPOINT ["/usr/local/bin/validator-entrypoint.sh"]


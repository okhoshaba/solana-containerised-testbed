#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-solana-observability}"
JOB_NAME="${JOB_NAME:-wallet-transfer-validation-$(date -u +%Y%m%d%H%M%S)}"
IMAGE="${IMAGE:-docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge-yellowstone}"
SOLANA_URL="${SOLANA_URL:-http://solana-rpc:8899}"
RECEIVER_PUB="${RECEIVER_PUB:-6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb}"

echo "[INFO] Namespace: ${NAMESPACE}"
echo "[INFO] Job name:  ${JOB_NAME}"
echo "[INFO] Image:     ${IMAGE}"
echo "[INFO] RPC URL:   ${SOLANA_URL}"
echo "[INFO] Receiver:  ${RECEIVER_PUB}"

kubectl -n "${NAMESPACE}" apply -f - <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  labels:
    app.kubernetes.io/name: solana-containerised-testbed
    app.kubernetes.io/component: wallet-transfer-validation
    app.kubernetes.io/part-of: solana-containerised-testbed
    testbed.solana/stage: observability-core-validation
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 180
  template:
    metadata:
      labels:
        app.kubernetes.io/name: solana-containerised-testbed
        app.kubernetes.io/component: wallet-transfer-validation
        app.kubernetes.io/part-of: solana-containerised-testbed
        testbed.solana/stage: observability-core-validation
    spec:
      restartPolicy: Never
      containers:
        - name: wallet-transfer-validation
          image: ${IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: SOLANA_URL
              value: "${SOLANA_URL}"
            - name: RECEIVER_PUB
              value: "${RECEIVER_PUB}"
          command:
            - sh
            - -lc
            - |
              set -eu

              SOLANA="/opt/solana/bin/solana"
              SOLANA_KEYGEN="/opt/solana/bin/solana-keygen"
              SENDER_KEYPAIR="/tmp/sender-validation.json"

              echo "[INFO] Checking Solana CLI"
              "\${SOLANA}" --version
              "\${SOLANA_KEYGEN}" --version

              echo "[INFO] Checking Solana cluster version"
              "\${SOLANA}" --url "\${SOLANA_URL}" cluster-version

              echo "[INFO] Creating temporary sender keypair"
              "\${SOLANA_KEYGEN}" new --no-bip39-passphrase --silent --force --outfile "\${SENDER_KEYPAIR}"

              SENDER_PUB="\$("\${SOLANA_KEYGEN}" pubkey "\${SENDER_KEYPAIR}")"

              echo "[INFO] Sender:   \${SENDER_PUB}"
              echo "[INFO] Receiver: \${RECEIVER_PUB}"

              echo "[INFO] Airdropping 2 SOL to sender"
              "\${SOLANA}" --url "\${SOLANA_URL}" airdrop 2 "\${SENDER_PUB}"

              echo "[INFO] Sender balance before transfer"
              "\${SOLANA}" --url "\${SOLANA_URL}" balance "\${SENDER_PUB}"

              echo "[INFO] Receiver balance before transfer"
              "\${SOLANA}" --url "\${SOLANA_URL}" balance "\${RECEIVER_PUB}"

              echo "[INFO] Sending 0.5 SOL from sender to receiver"
              TRANSFER_OUTPUT="\$("\${SOLANA}" --url "\${SOLANA_URL}" --keypair "\${SENDER_KEYPAIR}" transfer \
                --allow-unfunded-recipient \
                "\${RECEIVER_PUB}" \
                0.5)"

              printf '%s\n' "\${TRANSFER_OUTPUT}"

              SIG="\$(printf '%s\n' "\${TRANSFER_OUTPUT}" | awk '/Signature:/ {print \$2; exit}')"

              if [ -z "\${SIG}" ]; then
                echo "[ERROR] Transaction signature was not found in transfer output"
                exit 1
              fi

              echo "[INFO] Transaction signature: \${SIG}"

              echo "[INFO] Confirming transaction"
              "\${SOLANA}" --url "\${SOLANA_URL}" confirm "\${SIG}"

              echo "[INFO] Sender balance after transfer"
              "\${SOLANA}" --url "\${SOLANA_URL}" balance "\${SENDER_PUB}"

              echo "[INFO] Receiver balance after transfer"
              "\${SOLANA}" --url "\${SOLANA_URL}" balance "\${RECEIVER_PUB}"

              echo "[INFO] Wallet transfer validation completed successfully"
YAML

echo "[INFO] Waiting for validation Job to complete"
if kubectl -n "${NAMESPACE}" wait --for=condition=complete "job/${JOB_NAME}" --timeout=180s; then
  echo "[INFO] Validation Job completed"
  kubectl -n "${NAMESPACE}" logs "job/${JOB_NAME}"
else
  echo "[ERROR] Validation Job did not complete successfully"
  kubectl -n "${NAMESPACE}" get pods -l job-name="${JOB_NAME}" -o wide
  kubectl -n "${NAMESPACE}" logs "job/${JOB_NAME}" || true
  exit 1
fi

echo "[INFO] Validation Job object was kept for audit:"
echo "       kubectl -n ${NAMESPACE} logs job/${JOB_NAME}"

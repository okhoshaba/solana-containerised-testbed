# Controlled Load Layer 1 Kubernetes Manifests

This directory contains the Kubernetes manifests for Controlled Load Layer 1.

The manifests are designed to run inside the existing `solana-observability` namespace, where the validated Solana observability core already exposes:

- `solana-rpc` on port `8899`;
- `solana-metrics` on port `9464`.

## Components

The controlled-load layer adds:

- `solana-loadgen2` Deployment;
- `solana-loadgen2` Service on port `7070`;
- `controlled-load-results-pvc`;
- `controlled-load-knee-step` Job.

## Runtime secret

The payer keypair is not stored in Git.

Before applying these manifests, create the runtime secret manually:

```bash
kubectl -n solana-observability create secret generic solana-payer-keypair \
  --from-file=payer.json=/home/khoshaba/solana-secrets/payer.json

Do not commit payer.json.

## Container images

The manifests currently reference:

docker.io/khoshaba/solana-loadgen2:layer1
docker.io/khoshaba/solana-controlled-load-tools:layer1

These images must be pushed to Docker Hub, or otherwise made available to the Kubernetes nodes, before applying the manifests.

## Apply

After the secret and images are available:

kubectl apply -k k8s/controlled-load
Validate
kubectl -n solana-observability get deploy,svc,pvc,job | grep -Ei 'loadgen|controlled'
kubectl -n solana-observability logs deploy/solana-loadgen2
kubectl -n solana-observability logs job/controlled-load-knee-step
Security

The following must not be committed:

payer.json;
keypair JSON files;
kubeconfig files;
Kubernetes admin credentials;
generated smoke-test CSV files containing local runtime evidence.


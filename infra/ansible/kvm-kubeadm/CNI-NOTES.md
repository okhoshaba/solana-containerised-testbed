# CNI notes for the KVM kubeadm cluster

This cluster uses Calico as the CNI plugin.

Important rule:

Do not mix Tigera Operator installation and direct Calico manifest installation.

Use one method only.

For the current reproducible baseline, the selected method is:

- direct Calico manifest;
- `50-install-calico-direct.yml`;
- no Tigera Operator;
- no `custom-resources.yaml`.

The earlier mixed approach created temporary webhook/operator leftovers and must not be reused.

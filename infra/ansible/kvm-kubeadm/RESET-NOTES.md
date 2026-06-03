# Reset notes

`reset-kubeadm-cluster.yml` destroys the current Kubernetes cluster state.

It removes:

- kubeadm cluster state;
- kubelet state;
- CNI state;
- Calico state;
- Kubernetes admin kubeconfig;
- local iptables Kubernetes/CNI rules.

Do not run this playbook on a working cluster unless the goal is to rebuild the cluster from scratch.

Expected rebuild sequence after reset:

1. ansible-playbook site-prepare-nodes.yml
2. ansible-playbook site-create-cluster.yml
3. ansible-playbook 90-validate-kubeadm-readiness.yml
4. kubectl get nodes -o wide
5. kubectl get pods -A -o wide

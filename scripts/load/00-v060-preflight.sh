#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

STAGE="v0.6.0"
HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown-branch)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown-sha)"

RUN_ID="${STAGE}_${HOST_SHORT}_${TS_UTC}_preflight_${GIT_SHA}"
OUT_DIR="${ROOT_DIR}/results/${STAGE}/raw/${RUN_ID}"

mkdir -p "$OUT_DIR"
mkdir -p "$OUT_DIR/repo"
mkdir -p "$OUT_DIR/host"
mkdir -p "$OUT_DIR/k8s"
mkdir -p "$OUT_DIR/rpc"
mkdir -p "$OUT_DIR/logs"

exec > >(tee "$OUT_DIR/logs/preflight.stdout.log") 2> >(tee "$OUT_DIR/logs/preflight.stderr.log" >&2)

echo "=== v0.6.0 preflight capture ==="
echo "ROOT_DIR=$ROOT_DIR"
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo

run_cmd() {
  local name="$1"
  shift
  local outfile="$1"
  shift

  echo ">>> $name"
  {
    echo "# command: $*"
    echo "# started_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    "$@"
    local rc=$?
    echo "# finished_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# exit_code: $rc"
    return $rc
  } > "$outfile" 2>&1 || true
}

write_metadata() {
  cat > "$OUT_DIR/metadata.env" <<META
stage=$STAGE
run_id=$RUN_ID
timestamp_utc=$TS_UTC
host_short=$HOST_SHORT
hostname=$(hostname 2>/dev/null || echo unknown)
git_branch=$GIT_BRANCH
git_sha=$GIT_SHA
root_dir=$ROOT_DIR
META
}

write_metadata

run_cmd "git status" "$OUT_DIR/repo/git-status.txt" git status --short
run_cmd "git branch" "$OUT_DIR/repo/git-branch.txt" git branch --show-current
run_cmd "git last commit" "$OUT_DIR/repo/git-last-commit.txt" git log -1 --oneline
run_cmd "git remote" "$OUT_DIR/repo/git-remote.txt" git remote -v
run_cmd "git diff stat" "$OUT_DIR/repo/git-diff-stat.txt" git diff --stat

run_cmd "date utc" "$OUT_DIR/host/date-utc.txt" date -u
run_cmd "hostnamectl" "$OUT_DIR/host/hostnamectl.txt" hostnamectl
run_cmd "uname" "$OUT_DIR/host/uname.txt" uname -a
run_cmd "os release" "$OUT_DIR/host/os-release.txt" cat /etc/os-release
run_cmd "lscpu" "$OUT_DIR/host/lscpu.txt" lscpu
run_cmd "free" "$OUT_DIR/host/free-h.txt" free -h
run_cmd "df" "$OUT_DIR/host/df-hT.txt" df -hT
run_cmd "lsblk" "$OUT_DIR/host/lsblk.txt" lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL
run_cmd "ip addr" "$OUT_DIR/host/ip-addr.txt" ip -br addr
run_cmd "ip link" "$OUT_DIR/host/ip-link.txt" ip -br link
run_cmd "listening tcp udp" "$OUT_DIR/host/ss-listening.txt" ss -lntup

if command -v ethtool >/dev/null 2>&1; then
  for iface in $(ls /sys/class/net | grep -v '^lo$' | sort); do
    run_cmd "ethtool $iface" "$OUT_DIR/host/ethtool-${iface}.txt" ethtool "$iface"
  done
else
  echo "ethtool not found; skipping NIC details"
fi

if command -v kubectl >/dev/null 2>&1; then
  run_cmd "kubectl version" "$OUT_DIR/k8s/kubectl-version.txt" kubectl version -o yaml
  run_cmd "kubectl cluster-info" "$OUT_DIR/k8s/cluster-info.txt" kubectl cluster-info
  run_cmd "kubectl nodes" "$OUT_DIR/k8s/nodes-wide.txt" kubectl get nodes -o wide
  run_cmd "kubectl pods all namespaces" "$OUT_DIR/k8s/pods-all-namespaces-wide.txt" kubectl get pods -A -o wide
  run_cmd "kubectl services all namespaces" "$OUT_DIR/k8s/services-all-namespaces-wide.txt" kubectl get svc -A -o wide
  run_cmd "kubectl deployments all namespaces" "$OUT_DIR/k8s/deployments-all-namespaces.txt" kubectl get deploy -A -o wide
  run_cmd "kubectl daemonsets all namespaces" "$OUT_DIR/k8s/daemonsets-all-namespaces.txt" kubectl get ds -A -o wide
  run_cmd "kubectl pv pvc" "$OUT_DIR/k8s/pv-pvc.txt" kubectl get pv,pvc -A
  run_cmd "kubectl top nodes" "$OUT_DIR/k8s/top-nodes.txt" kubectl top nodes
  run_cmd "kubectl top pods" "$OUT_DIR/k8s/top-pods-all-namespaces.txt" kubectl top pods -A
else
  echo "kubectl not found; skipping Kubernetes capture"
fi

if command -v crictl >/dev/null 2>&1; then
  run_cmd "crictl images" "$OUT_DIR/k8s/crictl-images.txt" crictl images
  run_cmd "crictl ps" "$OUT_DIR/k8s/crictl-ps.txt" crictl ps -a
fi

if command -v docker >/dev/null 2>&1; then
  run_cmd "docker version" "$OUT_DIR/host/docker-version.txt" docker version
  run_cmd "docker images" "$OUT_DIR/host/docker-images.txt" docker images
fi

if command -v podman >/dev/null 2>&1; then
  run_cmd "podman version" "$OUT_DIR/host/podman-version.txt" podman version
  run_cmd "podman images" "$OUT_DIR/host/podman-images.txt" podman images
fi

if command -v containerd >/dev/null 2>&1; then
  run_cmd "containerd version" "$OUT_DIR/host/containerd-version.txt" containerd --version
fi

if command -v curl >/dev/null 2>&1; then
  run_cmd "solana rpc getHealth" "$OUT_DIR/rpc/getHealth.json" \
    curl -sS -m 5 http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

  run_cmd "solana rpc getVersion" "$OUT_DIR/rpc/getVersion.json" \
    curl -sS -m 5 http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getVersion"}'

  run_cmd "solana rpc getEpochInfo" "$OUT_DIR/rpc/getEpochInfo.json" \
    curl -sS -m 5 http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getEpochInfo"}'
else
  echo "curl not found; skipping RPC checks"
fi

echo
echo "=== Preflight capture completed ==="
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"

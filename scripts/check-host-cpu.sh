#!/usr/bin/env bash
set -euo pipefail

echo "Host architecture:"
uname -m
echo

echo "CPU summary:"
lscpu | egrep 'Architecture|Model name|CPU\(s\)|Thread|Core|Socket|Vendor|Virtualization' || true
echo

echo "Selected CPU flags:"
grep -m1 '^flags' /proc/cpuinfo \
  | tr ' ' '\n' \
  | egrep 'avx|avx2|sse4_1|sse4_2|bmi1|bmi2|adx|sha_ni' \
  | sort -u || true

echo

if grep -m1 '^flags' /proc/cpuinfo | grep -qw 'avx2'; then
  echo "OK: AVX2 is present."
else
  echo "WARNING: AVX2 is NOT present."
  echo "Prebuilt Solana validator binaries may fail with 'Illegal instruction' or 'Aborted'."
fi

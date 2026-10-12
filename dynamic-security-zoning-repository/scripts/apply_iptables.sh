#!/usr/bin/env bash
set -euo pipefail

# Uses a dedicated chain and never flushes the host's global FORWARD chain.
SLICE_SUBNET="${1:-}"
POLICY="${2:-}"
CHAIN="DSZ_SLICE"

if [[ -z "$SLICE_SUBNET" || ! "$POLICY" =~ ^(none|medium|strict)$ ]]; then
  echo "Usage: $0 <slice-subnet/CIDR> <none|medium|strict>" >&2
  exit 2
fi

command -v iptables >/dev/null || { echo "iptables not found" >&2; exit 127; }

# Create chain if missing; remove only this project's jump and rules.
iptables -N "$CHAIN" 2>/dev/null || true
while iptables -C FORWARD -s "$SLICE_SUBNET" -j "$CHAIN" 2>/dev/null; do
  iptables -D FORWARD -s "$SLICE_SUBNET" -j "$CHAIN"
done
iptables -F "$CHAIN"

if [[ "$POLICY" == "none" ]]; then
  # Empty chain returns to the caller's FORWARD chain.
  :
elif [[ "$POLICY" == "medium" ]]; then
  iptables -A "$CHAIN" -p udp --dport 53 -j ACCEPT
  iptables -A "$CHAIN" -p tcp --dport 53 -j ACCEPT
  iptables -A "$CHAIN" -j DROP
else
  iptables -A "$CHAIN" -j DROP
fi

iptables -I FORWARD 1 -s "$SLICE_SUBNET" -j "$CHAIN"
echo "Configured $CHAIN for $SLICE_SUBNET with policy=$POLICY"

#!/bin/bash
# block_ip.sh
# Triggered by Splunk alert when DoS/DDoS threshold is exceeded.
# Extracts the attacker IP from Splunk's results CSV and blocks it via iptables.
#
# How it works:
#   Splunk Alert → Run Script → block_ip.sh → iptables DROP rule
#
# Splunk passes the results file path as argument $8 (gzipped CSV).

# ── CONFIG ────────────────────────────────────────────────────────────────────
LOGFILE="/var/log/ddos_block.log"
# ──────────────────────────────────────────────────────────────────────────────

RESULTS_FILE=$8

echo "$(date) - Script triggered. Looking for results in: $RESULTS_FILE" >> $LOGFILE

# ── Step 1: Validate results file ────────────────────────────────────────────
if [ -z "$RESULTS_FILE" ] || [ ! -f "$RESULTS_FILE" ]; then
    echo "$(date) - ERROR: No results file passed in argument 8." >> $LOGFILE
    exit 1
fi

# ── Step 2: Extract IPs from gzipped CSV ─────────────────────────────────────
# Splunk results are CSVs — NR>1 skips header, $1 gets first column (the IP)
IPS=$(zcat "$RESULTS_FILE" | awk -F',' 'NR>1 {print $1}' | tr -d '"')

# ── Step 3: Block each IP ─────────────────────────────────────────────────────
for IP in $IPS; do

    # Validate it looks like an IP address
    if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then

        # Check if already blocked — avoid duplicate rules
        if sudo /sbin/iptables -L INPUT -n | grep -q "$IP"; then
            echo "$(date) - IP $IP is already blocked. Skipping." >> $LOGFILE
            continue
        fi

        # Insert DROP rule at TOP of INPUT chain
        sudo /sbin/iptables -I INPUT -s "$IP" -j DROP

        echo "$(date) - SUCCESS: Blocked $IP due to DoS alert" >> $LOGFILE
    else
        echo "$(date) - WARNING: '$IP' is not a valid IP. Skipping." >> $LOGFILE
    fi

done
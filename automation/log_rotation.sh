#!/bin/bash
# log_rotation.sh
# Rotates nginx access.log on the main server (VM1).
# - Compresses current log with timestamp
# - Keeps only the 3 most recent backups (deletes oldest automatically)
# - Reloads nginx so it starts writing to a fresh log
# - Sends compressed log to backup server via SCP
#
# Recommended: run via cron every 10 minutes
# Cron entry: */10 * * * * /path/to/log_rotation.sh

# ── CONFIG ────────────────────────────────────────────────────────────────────
LOG_DIR="/var/log/nginx"
LOG_FILE="$LOG_DIR/access.log"
MAX_BACKUPS=3                          # keep only 3 compressed logs

BACKUP_SERVER_USER="saad"             # SSH user on backup server
BACKUP_SERVER_IP="YOUR_BACKUP_IP"     # ← replace with your backup server IP
BACKUP_SERVER_DIR="/backup/nginx_logs"

SCRIPT_LOG="/var/log/log_rotation.log"
# ──────────────────────────────────────────────────────────────────────────────

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
ROTATED_FILE="$LOG_DIR/access_${TIMESTAMP}.log.gz"

echo "$(date) - Starting log rotation" >> $SCRIPT_LOG

# ── Step 1: Compress current access.log ──────────────────────────────────────
if [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; then
    echo "$(date) - access.log is empty or missing, skipping" >> $SCRIPT_LOG
    exit 0
fi

gzip -c "$LOG_FILE" > "$ROTATED_FILE"
echo "$(date) - Compressed to $ROTATED_FILE" >> $SCRIPT_LOG

# ── Step 2: Clear the current log and reload nginx ───────────────────────────
> "$LOG_FILE"
sudo systemctl reload nginx
echo "$(date) - Cleared access.log and reloaded nginx" >> $SCRIPT_LOG

# ── Step 3: Keep only MAX_BACKUPS — delete oldest if exceeded ─────────────────
BACKUP_COUNT=$(ls -1 $LOG_DIR/access_*.log.gz 2>/dev/null | wc -l)

if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
    OLDEST=$(ls -1t $LOG_DIR/access_*.log.gz | tail -$DELETE_COUNT)
    for FILE in $OLDEST; do
        rm -f "$FILE"
        echo "$(date) - Deleted old backup: $FILE" >> $SCRIPT_LOG
    done
fi

# ── Step 4: Send compressed log to backup server via SCP ─────────────────────
scp -o StrictHostKeyChecking=no \
    "$ROTATED_FILE" \
    "$BACKUP_SERVER_USER@$BACKUP_SERVER_IP:$BACKUP_SERVER_DIR/"

if [ $? -eq 0 ]; then
    echo "$(date) - Successfully sent $ROTATED_FILE to backup server" >> $SCRIPT_LOG
else
    echo "$(date) - ERROR: Failed to send to backup server" >> $SCRIPT_LOG
fi

echo "$(date) - Log rotation complete" >> $SCRIPT_LOG
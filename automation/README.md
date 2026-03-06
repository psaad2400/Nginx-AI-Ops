# ⚙️ Automation Scripts

> Shell scripts that handle log rotation, backup, and automated IP blocking.

---

## Scripts Overview

| Script | Trigger | Purpose |
|---|---|---|
| `log_rotation.sh` | Cron (every 10 min) | Compress, rotate and backup nginx logs |
| `block_ip.sh` | Splunk Alert | Block attacker IP via iptables |

---

## 📸 Log Rotation — Main Server

> Compressed log files on VM1 after rotation — only 3 kept at a time

![Log Rotation Main Server](../docs/screenshots/main-server-backup-ss.png)

---

## 📸 Log Backup — Backup Server (VM2)

> Same compressed files received on the backup server via SCP

![Log Backup Server](../docs/screenshots/backupserver-log-ss.png)

---

## 📸 IP Blocked by Alert

> Splunk alert fires → block_ip.sh executes → IP dropped in iptables

![IP Blocked](../docs/screenshots/blockedipbyalert.png)

---

## 1. `log_rotation.sh`

Runs every 10 minutes via cron. Does 4 things in order:

```
1. Compress access.log → access_TIMESTAMP.log.gz
2. Clear access.log + reload nginx (starts fresh log)
3. Delete oldest backup if more than 3 exist
4. SCP compressed log to backup server (VM2)
```

### Setup

```bash
# Copy script to server
sudo cp log_rotation.sh /usr/local/bin/log_rotation.sh
sudo chmod +x /usr/local/bin/log_rotation.sh

# Edit backup server IP inside the script
sudo nano /usr/local/bin/log_rotation.sh
# Set BACKUP_SERVER_IP to your VM2 IP

# Set up passwordless SSH to backup server
ssh-keygen -t rsa
ssh-copy-id saad@YOUR_BACKUP_SERVER_IP

# Add to cron — runs every 10 minutes
crontab -e
# Add this line:
*/10 * * * * /usr/local/bin/log_rotation.sh
```

### What it keeps on main server

```
/var/log/nginx/
├── access.log                          ← current live log (always fresh)
├── access_2026-03-03_12-06-49.log.gz   ← newest backup
├── access_2026-03-03_12-15-13.log.gz
└── access_2026-03-03_12-25-28.log.gz   ← oldest (gets deleted on next run)
```

> Once there are more than 3 backups, the oldest is automatically deleted.

### Backup server receives

```
/backup/nginx_logs/
├── access_2026-03-03_12-06-49.log.gz
├── access_2026-03-03_12-15-13.log.gz
└── access_2026-03-03_12-25-28.log.gz
```

### Monitor rotation logs

```bash
tail -f /var/log/log_rotation.log
```

### Cron Setup

```bash
# Open crontab editor
crontab -e

# Add this line at the bottom — runs every 10 minutes
*/10 * * * * /usr/local/bin/log_rotation.sh >> /var/log/log_rotation.log 2>&1
```

**Verify cron job was added:**
```bash
crontab -l
```

You should see:
```
*/10 * * * * /usr/local/bin/log_rotation.sh >> /var/log/log_rotation.log 2>&1
```

**Verify it is actually running** — after 10 minutes:
```bash
cat /var/log/log_rotation.log
```

You should see entries like:
```
Tue Mar  3 12:06:49 IST 2026 - Starting log rotation
Tue Mar  3 12:06:49 IST 2026 - Compressed to /var/log/nginx/access_2026-03-03_12-06-49.log.gz
Tue Mar  3 12:06:49 IST 2026 - Cleared access.log and reloaded nginx
Tue Mar  3 12:06:49 IST 2026 - Successfully sent file to backup server
Tue Mar  3 12:06:49 IST 2026 - Log rotation complete
```

**Check rotated files on main server:**
```bash
ls -ltr /var/log/nginx/
```

**Check backup server received files:**
```bash
ls -ltr /backup/nginx_logs/
```

### 📸 Cron Running — Main Server

![Log Rotation Main Server](../docs/screenshots/main-server-backup-ss.png)

### 📸 Cron Running — Backup Server

![Log Backup Server](../docs/screenshots/backupserver-log-ss.png)

---

## 2. `block_ip.sh`

Triggered automatically by a Splunk alert when an IP exceeds the request threshold. No manual intervention needed.

### How Splunk Triggers It

```
Splunk Search (real-time alert)
    ↓
index=nginx | stats count by remote_addr | where count > 100
    ↓
Alert Action → Run Script → block_ip.sh
    ↓
Splunk passes results as gzipped CSV via argument $8
    ↓
Script extracts IP → validates → blocks via iptables
    ↓
Logs result to /var/log/ddos_block.log
```

### Setup

```bash
# Copy script to Splunk scripts directory
sudo cp block_ip.sh /opt/splunk/bin/scripts/block_ip.sh
sudo chmod +x /opt/splunk/bin/scripts/block_ip.sh

# Allow splunk user to run iptables without password
sudo visudo
# Add this line:
splunk ALL=(ALL) NOPASSWD: /sbin/iptables
```

### Block log output

```
Tue Mar  3 11:19:56 AM IST 2026 - Script triggered. Looking for results in: /opt/splunk/...
Tue Mar  3 11:19:56 AM IST 2026 - SUCCESS: Blocked 192.168.0.105 due to DoS alert
```

### Check blocked IPs

```bash
# View block log
cat /var/log/ddos_block.log

# View iptables rules
sudo iptables -L INPUT -n | grep DROP

# Unblock an IP if needed
sudo iptables -D INPUT -s IP_ADDRESS -j DROP
```

---

## 🔗 How It Connects to the Rest of the Project

```
nginx/nginx.conf       → generates access.log
log_rotation.sh        → compresses + rotates + backs up logs
splunk/forwarder       → ships logs to Splunk before rotation clears them
block_ip.sh            → called by Splunk alert → blocks IP on firewall
```
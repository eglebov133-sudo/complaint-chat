#!/bin/bash
set -e

echo "=== Deploying complaint-chat ==="

# Copy .env
cp /tmp/deploy/.env.server /opt/complaint-chat/.env
echo "[OK] .env configured"

# Create directories
mkdir -p /opt/complaint-chat/flask_session
mkdir -p /opt/complaint-chat/drafts
echo "[OK] Directories created"

# Copy systemd service
cp /tmp/deploy/complaint-chat.service /etc/systemd/system/complaint-chat.service
systemctl daemon-reload
systemctl enable complaint-chat
systemctl restart complaint-chat
echo "[OK] Systemd service configured and started"

# Copy nginx config
cp /tmp/deploy/nginx-complaint-chat.conf /etc/nginx/sites-available/complaint-chat
ln -sf /etc/nginx/sites-available/complaint-chat /etc/nginx/sites-enabled/complaint-chat
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
echo "[OK] Nginx configured and restarted"

# Check status
sleep 2
systemctl status complaint-chat --no-pager -l | head -15
echo ""
echo "=== DEPLOY COMPLETE ==="
echo "App should be available at http://46.173.16.153"

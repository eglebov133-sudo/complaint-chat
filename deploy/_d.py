import paramiko
import os
import socket

socket.setdefaulttimeout(10)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
try:
    ssh.connect('stuchim.ru', username='root', password='O!hLNs8x1AXH', timeout=10, banner_timeout=10, auth_timeout=10)
except Exception as e:
    print(f"SSH connection failed: {e}")
    exit(1)

print("Connected! Uploading files...")
sftp = ssh.open_sftp()
sftp.get_channel().settimeout(10)

base = r'd:\000\complaint-chat'
files = [
    ('app.py', '/opt/complaint-chat/app.py'),
    ('config.py', '/opt/complaint-chat/config.py'),
    ('requirements.txt', '/opt/complaint-chat/requirements.txt'),
    ('data/recipients.py', '/opt/complaint-chat/data/recipients.py'),
    ('services/dialog_service.py', '/opt/complaint-chat/services/dialog_service.py'),
    ('services/llm_service.py', '/opt/complaint-chat/services/llm_service.py'),
    ('services/orchestrator.py', '/opt/complaint-chat/services/orchestrator.py'),
    ('services/payment_service.py', '/opt/complaint-chat/services/payment_service.py'),
    ('services/contact_verification_service.py', '/opt/complaint-chat/services/contact_verification_service.py'),
    ('services/user_service.py', '/opt/complaint-chat/services/user_service.py'),
    ('services/dadata_service.py', '/opt/complaint-chat/services/dadata_service.py'),
    ('services/agents.py', '/opt/complaint-chat/services/agents.py'),
    ('services/beget_service.py', '/opt/complaint-chat/services/beget_service.py'),
    ('services/yandex_direct_service.py', '/opt/complaint-chat/services/yandex_direct_service.py'),
    ('services/analytics_service.py', '/opt/complaint-chat/services/analytics_service.py'),
    ('data/__init__.py', '/opt/complaint-chat/data/__init__.py'),
    ('static/css/style.css', '/opt/complaint-chat/static/css/style.css'),
    ('static/js/chat.js', '/opt/complaint-chat/static/js/chat.js'),
    ('templates/index.html', '/opt/complaint-chat/templates/index.html'),
    ('templates/tariffs.html', '/opt/complaint-chat/templates/tariffs.html'),
    ('templates/privacy.html', '/opt/complaint-chat/templates/privacy.html'),
    ('templates/terms.html', '/opt/complaint-chat/templates/terms.html'),
    ('templates/login.html', '/opt/complaint-chat/templates/login.html'),
    ('templates/register.html', '/opt/complaint-chat/templates/register.html'),
    ('templates/account.html', '/opt/complaint-chat/templates/account.html'),
    ('templates/admin.html', '/opt/complaint-chat/templates/admin.html'),
    ('templates/admin_login.html', '/opt/complaint-chat/templates/admin_login.html'),
    ('deploy/nginx-complaint-chat.conf', '/etc/nginx/sites-available/complaint-chat'),
]

# Ensure remote directories exist
dirs = set()
for _, remote in files:
    d = os.path.dirname(remote)
    if d not in dirs:
        try:
            sftp.stat(d)
        except FileNotFoundError:
            sftp.mkdir(d)
        dirs.add(d)

for i, (local, remote) in enumerate(files, 1):
    local_path = os.path.join(base, local)
    try:
        sftp.put(local_path, remote)
        print(f"[{i}/{len(files)}] {local}")
    except Exception as e:
        print(f"[{i}/{len(files)}] FAIL {local}: {e}")

sftp.close()

print("\nConfiguring Beget API credentials...")
stdin, stdout, stderr = ssh.exec_command(
    "grep -q BEGET_LOGIN /opt/complaint-chat/.env 2>/dev/null "
    "|| (echo '' >> /opt/complaint-chat/.env "
    "&& echo 'BEGET_LOGIN=egleboxr' >> /opt/complaint-chat/.env "
    "&& echo 'BEGET_PASSWORD=waMA9Y3PkBH5' >> /opt/complaint-chat/.env "
    "&& echo 'BEGET_MAIL_DOMAIN=stuchim.ru' >> /opt/complaint-chat/.env "
    "&& echo 'ADDED'); echo EXIT:$?", timeout=10)
print(stdout.read().decode().strip())

print("\nInstalling dependencies...")
stdin, stdout, stderr = ssh.exec_command("cd /opt/complaint-chat && ./venv/bin/pip install -r requirements.txt -q 2>&1; echo EXIT:$?", timeout=120)
out = stdout.read().decode().strip()
print(out)

print("\nRestarting service...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart complaint-chat && sleep 3 && systemctl is-active complaint-chat 2>&1; echo EXIT:$?", timeout=30)
print("Result:", stdout.read().decode().strip())

print("Reloading nginx...")
stdin, stdout, stderr = ssh.exec_command("nginx -t 2>&1 && systemctl reload nginx && echo OK; echo EXIT:$?", timeout=20)
print("nginx:", stdout.read().decode().strip())

ssh.close()
print("DONE!")

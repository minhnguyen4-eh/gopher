#!/bin/sh
# Minimal SSH server for Gopher: key-only login, port forwarding only (no shell).
set -eu

: "${PUBLIC_KEY:?set PUBLIC_KEY to your ssh public key (one line)}"
USER_NAME="${SSH_USER:-gopher}"
KEY_DIR="${HOSTKEY_DIR:-/data/ssh}"   # mount a volume at /data so the host key survives redeploys

adduser -D -s /sbin/nologin "$USER_NAME" 2>/dev/null || true
echo "$USER_NAME:$(head -c 32 /dev/urandom | base64)" | chpasswd   # unlocks the account; password login stays disabled

mkdir -p "/home/$USER_NAME/.ssh" "$KEY_DIR"
printf '%s\n' "$PUBLIC_KEY" > "/home/$USER_NAME/.ssh/authorized_keys"
chown -R "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.ssh"
chmod 700 "/home/$USER_NAME/.ssh"
chmod 600 "/home/$USER_NAME/.ssh/authorized_keys"

[ -f "$KEY_DIR/ssh_host_ed25519_key" ] || ssh-keygen -q -t ed25519 -N "" -f "$KEY_DIR/ssh_host_ed25519_key"

cat > /etc/ssh/sshd_config <<CONF
Port 2222
HostKey $KEY_DIR/ssh_host_ed25519_key
AllowUsers $USER_NAME
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
PermitTTY no
AllowTcpForwarding yes
AllowAgentForwarding no
X11Forwarding no
ClientAliveInterval 30
ClientAliveCountMax 3
CONF

exec /usr/sbin/sshd -D -e

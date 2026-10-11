# Gopher Setup Guide

Gopher sends Discord traffic through an SSH tunnel to your Windows PC. The PC and the Mac talk to each other over Tailscale.

```
Mac (Gopher) --SSH over Tailscale--> Windows PC --> Discord
```

## 1. Install Tailscale on Windows

1. Download the installer from <https://tailscale.com/download/windows> and run it.
2. Open Tailscale from the system tray, click **Log in**, and sign in with a personal account (Google, GitHub or Microsoft).
3. Write down the PC's `100.x.x.x` IP address. In PowerShell, run:

```powershell
tailscale ip -4
```

## 2. Turn on OpenSSH Server on Windows

Open PowerShell **as Administrator** and run:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

If the first command fails, install it by hand: **Settings → System → Optional features → Add a feature → OpenSSH Server**.

Port 22 should only be open to the Tailscale network. Limit the firewall rule to the Tailscale address range:

```powershell
Get-NetFirewallRule -Name *OpenSSH-Server* | Set-NetFirewallRule -RemoteAddress 100.64.0.0/10
```

## 3. Install Tailscale on the Mac

Run this once:

```bash
brew install tailscale
```

Do **not** install the Tailscale app. The app needs a network extension, and a managed Mac can block it (for example, Cloudflare WARP can make the Sign in button do nothing). Gopher uses the command-line version in "userspace" mode instead. It runs as a normal process and needs no root access and no IT approval.

When the SSH host is a `100.x.x.x` IP or a `*.ts.net` name, clicking **Connect** in Gopher will:

- start the `tailscaled` daemon (its data is in `~/.tailscale`, and its SOCKS5 port is `localhost:1055`)
- open your browser to log in if you are not logged in yet. Use the same Tailscale account as the Windows PC. You only do this once.
- open the SSH tunnel through a ProxyCommand

Good to know:

- The Mac has no Tailscale network interface, so a plain `ssh` to `100.x.x.x` will not work. To test by hand, see step 5.
- The connection may go through a DERP relay. It is a little slower but still works.
- The daemon log is at `~/.tailscale/tailscaled.out`.

## 4. Set up an SSH key (no password)

On the Mac, create a key if you do not have one, then print the public key so you can copy it:

```bash
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub
```

On the Windows PC, paste that line into the right file for your account type:

- **Normal account:** `C:\Users\<name>\.ssh\authorized_keys`
- **Administrator account:** `C:\ProgramData\ssh\administrators_authorized_keys`

For the Administrator file, you must also fix its permissions. Run this in PowerShell as Administrator:

```powershell
icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
```

## 5. Test from the Mac

Replace `<windows-user>` and `100.x.x.x` with your real values:

```bash
ssh -o ProxyCommand="nc -X 5 -x localhost:1055 %h %p" <windows-user>@100.x.x.x
```

If you get in without a password prompt, it works. If it asks for a password, the key is in the wrong place or the file permissions are wrong.

To type less, add this to `~/.ssh/config`:

```
Host win
    HostName 100.x.x.x
    User <windows-user>
    ProxyCommand nc -X 5 -x localhost:1055 %h %p
```

Then connect with:

```bash
ssh win
```

## 6. Fill in Gopher

Open the Gopher dashboard and set:

- **SSH host:** the `100.x.x.x` IP
- **User:** your Windows username
- **Port** and **local port:** keep the defaults

For an SSH SOCKS tunnel, the Windows PC only needs `sshd` running. You do not need to install anything else on it.

If you prefer a name instead of an IP, turn on MagicDNS in the Tailscale admin console and use `<machine-name>.<tailnet>.ts.net`.

## 7. Use Discord

Click **Connect** in Gopher, then open Discord as usual.

Voice and video (UDP) do not go through the SSH tunnel.

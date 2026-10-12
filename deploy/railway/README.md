# Run the SSH server on Railway (Free plan, $0)

This guide takes you from nothing to a working Gopher connection, using only Railway's Free plan. No credit card is needed.

```
Mac (Gopher) --SSH--> Railway (TCP Proxy) --> small SSH container --> Discord / Netlify / Vercel ...
```

The container only runs `sshd`. It allows key login and port forwarding, and nothing else (no shell, no password).

## Know the limits first

These come from Railway's own docs and pricing page, so check them again if Railway changes its plans.

- The Free plan gives **$1 of usage credit per month**. If you use it all, Railway stops your service until the next cycle. You are never billed, because no card is on file.
- On the Free plan you **cannot choose the region** (the pricing page says global regions are trial-only). Expect a US server, so the ping from Vietnam will be high. Chat and web pages work fine. Voice and video do not go through the tunnel anyway.
- An `sshd` container uses very little memory and CPU. Most of the $1 will go to **outbound data ($0.05 per GB)**. As a rough guide, one month of light use fits. Heavy downloads do not.
- Railway says accounts it cannot verify get a **limited network** (restricted outbound access and few ports). If that happens to you, this plan will not work and you need the paid Hobby plan ($5 per month).
- Not confirmed in the docs: whether TCP Proxy works on the Free plan after the 30-day trial. Try it in step 6 before relying on it.
- Read Railway's Terms of Service about running proxies before you use this.

## Step 1: Make an SSH key (skip if you already have one)

On your Mac:

```bash
ssh-keygen -t ed25519
```

Print the public key and copy the whole line:

```bash
cat ~/.ssh/id_ed25519.pub
```

## Step 2: Sign up for Railway

1. Go to <https://railway.com> and click **Login**.
2. Sign in with **GitHub**. This also starts account verification, which gives you full network access.
3. Do not add a payment method. You stay on the Free plan.

## Step 3: Put the files on GitHub

The files in this folder (`Dockerfile`, `entrypoint.sh`) must be in a GitHub repository. If you pushed the Gopher repo, they are already there under `deploy/railway`.

## Step 4: Create the service

1. In Railway, click **New Project → Deploy from GitHub repo** and pick the repo.
2. Open the new service's **Settings** and set **Root Directory** to:

```
deploy/railway
```

Railway will build the `Dockerfile` in that folder.

## Step 5: Add the settings

In the service's **Variables** tab, add:

| Name | Value |
|------|-------|
| `PUBLIC_KEY` | the whole line you copied in step 1 |

Then add a **Volume** to the service and mount it at:

```
/data
```

The volume keeps the server's identity (its host key). Without it, the key changes on every deploy.

## Step 6: Open the port

1. In the service's **Settings → Networking**, click **TCP Proxy**.
2. Enter the port the container listens on:

```
2222
```

3. Railway shows an address like `something.proxy.rlwy.net:15140`. Write down the host and the port. They are different from 22 and 2222.

If you do not see **TCP Proxy**, or it is greyed out, your account does not have it on the Free plan. Stop here and read "Limits" above.

## Step 7: Test from your Mac

Replace `HOST` and `PORT` with the values from step 6:

```bash
ssh -N -D 1081 -p PORT gopher@HOST
```

If it starts and just waits (no output), it works. Keep it running, then open a second terminal:

```bash
curl --socks5-hostname 127.0.0.1:1081 https://vercel.com -I
```

You should see an `HTTP/2 200` or a redirect. Stop the test with `Ctrl+C` in the first terminal.

## Step 8: Use it in Gopher

Open the Gopher dashboard and set:

- **SSH host:** `HOST` (from step 6)
- **SSH port:** `PORT` (from step 6)
- **User:** `gopher`
- **Local port:** keep the default

Click **Connect**. Because this is not a Tailscale address, Gopher does not start Tailscale.

## Step 9: Watch your usage

In Railway, open your project's **Usage** page every few days for the first month.

- Under about $0.50 for the month: you are fine.
- Close to $1: reduce what goes through the tunnel (remove big sites from Gopher's domain list), or upgrade to Hobby ($5 per month).

You can also set a **usage limit** in the account settings, so Railway stops the service before it goes over.

## Fixing problems

| What you see | Likely cause |
|--------------|--------------|
| `Permission denied (publickey)` | `PUBLIC_KEY` is missing, has a line break, or is not the key your Mac uses. Fix it and redeploy. |
| `Connection refused` or timeout | The service is stopped (credit used up) or the TCP Proxy port is wrong. Check the deploy logs. |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | The volume at `/data` is missing, so the host key changed. Add the volume. |
| Connects, but pages do not load | The domain is not in Gopher's list. Add it in the dashboard. |
| Very slow | The Free plan runs in a far-away region. The paid plan lets you pick Singapore. |

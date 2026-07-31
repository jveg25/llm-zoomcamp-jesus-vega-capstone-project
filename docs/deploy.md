# Deploying to a Hetzner Cloud server

Runbook for putting the whole stack on a single virtual server behind Caddy with
automatic HTTPS. The application code is identical to local — the only
differences are the `docker-compose.prod.yaml` overlay and two extra `.env`
values.

Nothing here is Hetzner-specific beyond §1. It is Docker on Ubuntu, so the same
steps work on any provider (AWS EC2, Google Cloud, DigitalOcean) once you have a
server with a public IP.

## What the deployment looks like

One server runs every container. Caddy is the only one that publishes host
ports; everything else is reachable solely over Docker's internal network.

```
                  Public IPv4
                      │
        ┌─────────────┴─────────────┐   firewall: 22, 80, 443 only
        │      Hetzner server       │
        │                           │
        │   Caddy  :80 :443 ────────┼──> ui:8501        personalinstructor.…
        │     │  (Let's Encrypt)    │    api:8000       api.…
        │     ├─────────────────────┼──> auth:9999      auth.…
        │     ├─────────────────────┼──> airflow:8080   airflow.…
        │     └─────────────────────┼──> grafana:3000   grafana.…
        │                           │
        │   db (pgvector)  ← no published port, internal only
        └───────────────────────────┘
```

Postgres is deliberately unreachable from outside. The base compose file
publishes `5432` for local convenience; the prod overlay removes that, and the
firewall must not open it either.

## Prerequisites

- A Hetzner Cloud account (<https://console.hetzner.cloud>).
- DNS for `jesusvega.dev` managed in Cloudflare.
- An OpenAI API key.

---

## 1. Create the server

**New project** → **Add Server**:

| Setting | Value |
|---|---|
| Location | **Ashburn, VA** — closest to Lima (~100 ms). Germany is ~200 ms. |
| Image | **Ubuntu 24.04** |
| Type | **Shared vCPU → CPX21** (3 vCPU / 4 GB / 80 GB) |
| Networking | IPv4 **and** IPv6 |
| SSH key | Add your public key — see below |
| Firewall | Create one now, rules in §2 |

Roughly €7–8/month; confirm on Hetzner's pricing page, since figures change.

**4 GB is the point.** The whole stack — Postgres, API, UI, GoTrue, Grafana,
Caddy *and* Airflow — fits. Airflow's `standalone` mode alone wants 1–2 GB, so on
a 2 GB server it would have to be switched off, and being able to show the DAG
running is half the reason it's in the project.

If you have no SSH key yet:

```bash
ssh-keygen -t ed25519 -C "hetzner"      # press Enter at every prompt
cat ~/.ssh/id_ed25519.pub               # paste this into Hetzner
```

Hetzner IPs are static — there is no Elastic IP equivalent to configure.

## 2. Firewall

In the Hetzner Cloud firewall, inbound — nothing else:

| Port | Source | Why |
|---|---|---|
| 22 | your IP (or `0.0.0.0/0` if your IP moves) | SSH |
| 80 | `0.0.0.0/0` | Let's Encrypt validation + redirect to HTTPS |
| 443 | `0.0.0.0/0` | all application traffic |

Port 80 cannot be closed: Caddy proves domain control over it before a
certificate can be issued. Do **not** open 5432, 8000, 8501, 8080 or 3000 —
those services are reached through Caddy.

## 3. DNS in Cloudflare

Five A records, all pointing at the server's IPv4, and **all of them DNS only
(grey cloud)**:

| Name | Type | Content | Proxy |
|---|---|---|---|
| `personalinstructor` | A | `<server-ip>` | **DNS only** |
| `api.personalinstructor` | A | `<server-ip>` | **DNS only** |
| `auth.personalinstructor` | A | `<server-ip>` | **DNS only** |
| `airflow.personalinstructor` | A | `<server-ip>` | **DNS only** |
| `grafana.personalinstructor` | A | `<server-ip>` | **DNS only** |

> **The grey cloud matters.** This is the opposite of `jesusvega.dev`, which is
> proxied (orange) because Cloudflare serves it. Here, Caddy obtains its own
> Let's Encrypt certificate, and it can only do that if Let's Encrypt reaches
> *your server* on port 80. With the orange cloud on, Cloudflare intercepts the
> request and validation fails.

Confirm the records resolve to your server before starting the stack —
Caddy requests certificates on boot, and failed attempts count against Let's
Encrypt rate limits:

```bash
dig +short personalinstructor.jesusvega.dev    # must be the server IP, not a Cloudflare IP
```

## 4. Install Docker

```bash
ssh root@<server-ip>

apt-get update && apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io \
                   docker-buildx-plugin docker-compose-plugin

docker compose version    # must be >= 2.24 for the `!override` tag
```

Add swap — cheap insurance against a build spike killing a container:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 5. Clone and configure

```bash
git clone https://github.com/jveg25/llm-zoomcamp-jesus-vega-capstone-project.git app
cd app
cp .env.example .env
nano .env
```

Set these — the last two are what the overlay adds:

```bash
OPENAI_API_KEY=sk-...
POSTGRES_PASSWORD=<openssl rand -base64 24>
SUPABASE_JWT_SECRET=<openssl rand -base64 48>
GRAFANA_PASSWORD=<something strong>
DOMAIN=personalinstructor.jesusvega.dev     # no scheme, no trailing slash
ACME_EMAIL=jesus.vega.ingenieria@outlook.com
```

`DOMAIN` is the base name. The Caddyfile derives `api.`, `auth.`, `airflow.` and
`grafana.` from it, so don't include a scheme or a sub-subdomain.

Use real passwords. The local defaults (`postgres` / `admin`) are fine on a
laptop and unacceptable here — Grafana and Airflow are internet-facing behind
nothing but their own logins.

## 6. Start the stack

Every command from here needs **both** compose files. Define an alias so you
can't forget one:

```bash
alias dc='docker compose -f docker-compose.yaml -f docker-compose.prod.yaml'
dc up -d --build            # first build takes a few minutes
dc logs -f caddy            # look for "certificate obtained successfully"
```

## 7. Bootstrap the database

Idempotent, and works over `docker exec`, so it needs no published Postgres port:

```bash
POSTGRES_PASSWORD='<the one from .env>' ./scripts/bootstrap_db.sh
```

If step 3 reports `auth.users missing`, GoTrue hadn't finished its first boot.
Wait a few seconds and re-run — the script is safe to repeat.

## 8. Create your admin account

1. Open `https://personalinstructor.jesusvega.dev` and **sign up**. New users
   land in the `pending` role and cannot ask anything yet.
2. Promote yourself:

```bash
docker exec pi-db psql -U postgres -c \
  "UPDATE profiles SET role='admin' WHERE email='you@example.com';"
```

Log out and back in — the role comes from a fresh JWT.

## 9. Ingest the corpus

```bash
dc exec api python -m ingestion.run
```

Or trigger the `ingest_papers` DAG from `https://airflow.personalinstructor.jesusvega.dev`.

## 10. Verify

```bash
curl -sI https://personalinstructor.jesusvega.dev | head -1          # 200
curl -s -o /dev/null -w '%{http_code}\n' https://api.personalinstructor.jesusvega.dev/docs
curl -sI http://personalinstructor.jesusvega.dev | head -1           # 308 -> https
```

Then confirm the database is *not* reachable — this should time out, not
connect:

```bash
nc -vz -w 5 <server-ip> 5432
```

Finally sign in, ask a question, and check the conversation appears in Grafana.

---

## Operations

**Logs**

```bash
dc logs -f api          # one service
dc logs --tail=100      # everything
```

**Deploy a change**

```bash
git pull && dc up -d --build
```

Only rebuilt services restart; `db` and its volume are untouched.

**Back up the database**

```bash
docker exec pi-db pg_dump -U postgres postgres | gzip > backup-$(date +%F).sql.gz
```

Worth a cron job. The `db_data` volume survives `dc down`, but not `dc down -v`
— which also destroys `caddy_data`, forcing fresh certificate issuance.

**After a reboot** — nothing to do: every service carries
`restart: unless-stopped`.

---

## Troubleshooting

**Caddy can't get a certificate.** Almost always DNS or port 80. Check that the
record resolves to *your server's* IP and not a Cloudflare one — if you see
`104.21.x.x` or `172.67.x.x`, the orange cloud is still on for that subdomain
(§3). Let's Encrypt rate-limits repeated failures, so fix the cause before
retrying rather than restarting Caddy in a loop.

**The UI loads but chat never responds.** Streamlit runs over a WebSocket, which
Caddy upgrades automatically, so suspect the API: `dc logs api`.

**"Bad Gateway".** The upstream is down or still starting — `dc ps`, then read
that service's logs.

**Airflow links point at `localhost:8080`.** `AIRFLOW__WEBSERVER__BASE_URL`
didn't apply; confirm both compose files were passed (`dc config | grep BASE_URL`).

**Out of memory.** Check `free -h` and `docker stats`. Confirm the swap file from
§4 is active (`swapon --show`).

## Cost

Server roughly €7–8/month. OpenAI usage is on top: about $0.0007 per question on
`gpt-5.4-mini`, so a few thousand questions a month is a couple of dollars. The
Grafana dashboard tracks spend per conversation, so the real figure is
measurable rather than estimated.

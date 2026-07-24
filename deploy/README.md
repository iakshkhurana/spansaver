# Deploy — full public stack on one VM

Puts the **whole** SpanSaver stack on the public internet behind TLS: Mission Control, the auditor
API, the victim stack + collector, and a self-hosted SigNoz — with Caddy as the only public door.

```
Internet ──443──> Caddy ──> app.<domain>     → Mission Control UI  (+ /api → auditor)
                        └──> signoz.<domain>  → SigNoz UI (own login)
   (everything else — ClickHouse, OTLP, raw auditor/UI ports — stays INTERNAL)
```

> ⚠️ **Read the Security section before exposing anything.** The auditor mounts the Docker socket
> to restart the collector on apply; its mutating endpoints are gated by Basic Auth and the raw
> ports are never published — but this is a demo stack, not hardened production. Tear it down after
> judging.

---

## 0. What you need
- A **VM**: Ubuntu 22.04/24.04, **≥ 4 vCPU / 16 GB RAM / 40 GB disk** (SigNoz + ClickHouse are heavy).
- A **domain** with two DNS **A records** → the VM's public IP:
  - `app.<domain>`  (Mission Control)
  - `signoz.<domain>` (SigNoz)
- The VM's **cloud firewall / security group** set to **inbound 22, 80, 443 only** (see §1 — this is
  what actually protects ClickHouse/OTLP, because Docker bypasses `ufw`).
- An **LLM key** (OpenAI or Anthropic) for `/explain` + askdocs.

## 1. Firewall FIRST (provider security group)
In your cloud console, restrict the VM's inbound rules to:
| Port | Source | Why |
|------|--------|-----|
| 22   | your IP (ideally) | SSH |
| 80   | 0.0.0.0/0 | HTTP → Caddy (redirects to 443 + ACME) |
| 443  | 0.0.0.0/0 | HTTPS → Caddy |

Do **not** open 8080 / 4317 / 4318 / 8100 / 3000 / 9000. Caddy reaches SigNoz internally; nothing
else should be public. (A host `ufw` rule is not enough — Docker publishes ports past it, so the
provider security group is the real boundary.)

## 2. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
docker version && docker compose version
```

## 3. Get the code
```bash
git clone <your-repo-url> spansaver && cd spansaver
# (deploy from the branch you want, e.g. the v2 UI branch: git checkout v2)
```

## 4. Install SigNoz (Foundry / casting.yml)
```bash
curl -fsSL https://signoz.io/foundry.sh | bash
foundryctl cast -f casting.yml            # brings SigNoz up (ClickHouse, query, UI on :8080)
docker compose ps -a | grep -i clickhouse # note the ClickHouse container name
docker network ls | grep -i signoz        # note the network name (→ SIGNOZ_DOCKER_NETWORK)
```
Open `http://<vm-ip>:8080` **once from an SSH tunnel** (`ssh -L 8080:localhost:8080 vm`) — not
publicly — to create the admin user + an **API key** (Settings → API keys).

## 5. App config — `.env` (repo root)
```bash
cp .env.example .env && nano .env
```
Set at least:
- `SIGNOZ_API_KEY=` the key from step 4
- `CLICKHOUSE_DSN=clickhouse://default:@clickhouse:9000/default` and
  `CLICKHOUSE_HOST=<clickhouse-container-name from step 4>` (e.g. `signoz-telemetrystore-clickhouse-0-0`)
- `SIGNOZ_COLLECTOR_OTLP_ENDPOINT=host.docker.internal:4317` (our collector → SigNoz ingest)
- `LLM_PROVIDER=openai|anthropic` + the matching key
- prices (`PRICE_*`) — leave defaults, they're the "assumed rate"
- `WASTE_*=1` to seed the demo leaks

`SIGNOZ_UI_URL` / `UI_ORIGINS` are set for you by the prod compose (to the public URLs) — no need to
touch them here.

## 6. Deploy config — `deploy/`
```bash
cd deploy
cp .env.deploy.example .env          # domains → URLs + SIGNOZ_DOCKER_NETWORK
cp caddy.env.example  caddy.env      # domains + basic-auth for the guarded endpoints
# generate the auth hash (copy the $-string verbatim into caddy.env BASIC_AUTH_HASH):
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'a-strong-password'
nano .env caddy.env
```

## 7. Bring the stack up
```bash
# from deploy/
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
docker compose --env-file .env -f docker-compose.prod.yml ps
```
Caddy fetches TLS certs automatically (needs 80/443 open + DNS resolving). Then:
- **https://app.\<domain\>** — Mission Control
- **https://signoz.\<domain\>** — SigNoz

## 8. Seed data + audit
```bash
# generate traffic so there's something to find (leave running)
python3 scripts/traffic.py    # or: nohup python3 scripts/traffic.py &
```
Import `dashboards/*.json` + create the alerts (`alerts/README.md`) in SigNoz, wait ~10 min for
volume, then click **Run Audit** in the UI (or `curl -s -X POST https://app.<domain>/api/audit`).

---

## Security (read this)
- **Cloud security group = the boundary.** Inbound 22/80/443 only. Everything else internal.
- **Auditor mutations gated.** `apply` / `unapply` / `verify` / `explain` require Basic Auth (Caddy).
  Read paths (`audit`, `findings`, `health`) are open for the live demo. To demo an apply, you'll be
  prompted for the `caddy.env` credentials.
- **Docker socket.** The auditor can restart the collector via `/var/run/docker.sock`. That's why the
  mutating endpoints are behind auth. If you don't need live apply on the public box, comment out the
  `docker.sock` volume in `docker-compose.prod.yml` and demo apply locally instead — safest.
- **ClickHouse is never published.** It's reachable only inside the SigNoz docker network.
- **Secrets.** `.env`, `deploy/.env`, `deploy/caddy.env` hold keys — they're gitignored patterns
  (`.env`); never commit the real ones. Rotate the SigNoz API key + LLM key after the event.
- **Tear it down when done** (§ below). A public LLM-calling endpoint left running can cost money.

## Update / redeploy
```bash
cd deploy && git pull
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
```

## Teardown
```bash
cd deploy && docker compose --env-file .env -f docker-compose.prod.yml down
# SigNoz (separate project):
foundryctl down 2>/dev/null || (cd pours/deployment && docker compose down)
# then delete the VM so nothing lingers / bills.
```

## Cost / reality check
A 16 GB VM runs ~$40–80/mo pro-rated; for a hackathon, spin it up for judging and destroy it after.
If all you need is a shareable link, a mock-mode UI on a static host is far cheaper — but you chose
the full stack, so this is the secure way to do it.

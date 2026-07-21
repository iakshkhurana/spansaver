# Setup

## Prerequisites
- Docker + Docker Compose, ≥8 GB free RAM (SigNoz + our stack), git, Node 20+/pnpm,
  Python 3.12, an LLM API key (Anthropic or OpenAI).

## 1. SigNoz (self-host)
Install via the **official SigNoz self-host Docker guide** (signoz.io → Docs → Install).
Don't pin ports/paths from memory — after install, note what your version actually exposes:
- `SIGNOZ_UI_URL` — the URL you open in the browser.
- `SIGNOZ_API_URL` — same host; confirm the API base by watching a request in browser
  devtools while clicking around the SigNoz UI.
- Create an API key in SigNoz settings (admin) → `SIGNOZ_API_KEY`.
- ClickHouse runs inside SigNoz's compose. Confirm the container name
  (`docker ps | grep clickhouse`) and set `CLICKHOUSE_DSN`. Our compose joins SigNoz's docker
  network so the auditor can reach it by service name.

Sanity check before building anything:
```
docker exec -it <clickhouse-container> clickhouse-client -q "SHOW DATABASES"
# expect signoz_logs / signoz_traces / signoz_metrics among them
```

## 2. Our stack
```
cp .env.example .env        # fill SigNoz values, LLM key, leave prices at defaults
make up                     # collector + victim services + auditor + ui
make waste-on               # arm all WASTE_* toggles
make traffic                # start load (leave running)
```
Wait ~10 minutes so volumes are meaningful, then open Mission Control and run `make audit`.

## 3. Checklist before Day-2 coding starts
- [ ] orders / payments / askdocs visible as services in SigNoz
- [ ] askdocs spans carry token-usage attributes (dump one span, record the exact keys in
      `auditor/llm_auditor/attrs.py`)
- [ ] ClickHouse volume query returns per-service log bytes
- [ ] SigNoz API returns the dashboards list with your API key (record the route in
      `auditor/telemetry_auditor/signoz_api.py`)
- [ ] Import `dashboards/*.json` stubs so deep links have somewhere to land

## 4. Dev accelerator: SigNoz MCP in your editor
Connect the SigNoz MCP server to Cursor / Claude Code (SigNoz docs → AI → MCP server; for
self-host, run the MCP server locally against your instance). Then your coding agent can
check "what attributes exist on askdocs spans?" against live data instead of guessing —
which is also a line we use in the demo.

## Troubleshooting quick hits
- No data in SigNoz → check collector logs first (`make logs`); 90% of the time it's the
  OTLP endpoint env var in a victim service.
- Auditor can't reach ClickHouse → confirm both stacks share the docker network
  (`docker network inspect`).
- API 401 → key created under a non-admin user, or wrong header casing; verify via curl.

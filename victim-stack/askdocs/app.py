"""askdocs — a tiny RAG-style FAQ service, and the LLM-waste victim.

Waste modes (LEAK-CATALOG L1/L2):
  WASTE_LLM_NOCACHE=1  answer every prompt fresh, even exact repeats   (leak L1)
  WASTE_LLM_BLOAT=1    glue the ENTIRE doc set into every system prompt (leak L2)

The L1 fix is a config flip, not code: ASKDOCS_CACHE=1 turns on an exact-match, TTL-bounded
response cache (safe: no semantic guessing). WASTE_LLM_NOCACHE forces a bypass so the
"before" state is genuinely uncached.

Instrumentation is Traceloop (OpenLLMetry): initialised at startup below. It auto-wraps the
OpenAI / Anthropic client and emits gen_ai.* spans carrying model + token-usage attributes —
the raw material for every LLM detector. FastAPI spans are added on top.
"""
import hashlib
import logging
import os
import time

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from traceloop.sdk import Traceloop

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
_DEFAULT_MODEL = {"anthropic": "claude-haiku-4-5-20251001", "openai": "gpt-4o-mini"}
ASKDOCS_MODEL = os.getenv("ASKDOCS_MODEL") or _DEFAULT_MODEL.get(LLM_PROVIDER, "gpt-4o-mini")

WASTE_LLM_NOCACHE = os.getenv("WASTE_LLM_NOCACHE", "0") == "1"
WASTE_LLM_BLOAT = os.getenv("WASTE_LLM_BLOAT", "0") == "1"
ASKDOCS_CACHE = os.getenv("ASKDOCS_CACHE", "0") == "1"
CACHE_TTL = int(os.getenv("ASKDOCS_CACHE_TTL", "3600"))
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("askdocs")

# Traceloop → OUR collector via OTLP. disable_batch=True flushes each span immediately, which
# also makes "dump one real span to pin its attribute keys" (D1 DoD) painless.
Traceloop.init(
    app_name="askdocs",
    exporter=OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True),
    disable_batch=True,
)

app = FastAPI(title="askdocs")
FastAPIInstrumentor.instrument_app(app)

# Minimal "knowledge base". Real retrieval picks the one relevant doc; bloat mode dumps them
# all into every prompt regardless of the question.
DOCS = {
    "shipping": "Orders ship in 1-2 business days. Standard delivery is 3-5 days; express is next-day.",
    "returns": "Returns are accepted within 30 days of delivery for a full refund, tags attached.",
    "payments": "We accept Visa, Mastercard, Amex, and PayPal. Charges appear as 'ACME STORE'.",
    "warranty": "All products carry a 1-year limited warranty covering manufacturing defects.",
    "accounts": "Reset your password from the login page; account data is exportable on request.",
    "hours": "Support is available 9am-6pm ET, Monday through Friday, excluding US holidays.",
}
FULL_DOCS = "\n\n".join(f"[{k}] {v}" for k, v in DOCS.items())

_cache: dict[str, tuple[str, float]] = {}

# Runtime waste state. Both start from env (the wasteful "before"); the L1/L2 fixes flip them
# live via POST /admin/* so applying a fix is an instant, reversible config change on the running
# service — no container rebuild, and the token graph steps down on camera.
_cache_enabled = ASKDOCS_CACHE and not WASTE_LLM_NOCACHE   # L1: exact-match response cache
_bloat_enabled = WASTE_LLM_BLOAT                           # L2: full-docs preamble on every prompt


class AskRequest(BaseModel):
    question: str


class CacheToggle(BaseModel):
    enabled: bool
    clear: bool = False    # drop cached entries when disabling, so "before" is genuinely cold


class BloatToggle(BaseModel):
    enabled: bool          # L2 fix applies with enabled=false (context moves behind retrieval)


def _retrieve(question: str) -> str:
    """Naive keyword retrieval: return the single most relevant doc (the non-wasteful path)."""
    q = question.lower()
    best = max(DOCS.items(), key=lambda kv: sum(w in q for w in kv[1].lower().split()))
    return f"[{best[0]}] {best[1]}"


def _system_prompt(question: str) -> str:
    context = FULL_DOCS if _bloat_enabled else _retrieve(question)
    return (
        "You are a concise customer-support assistant. Answer only from the context.\n\n"
        f"Context:\n{context}"
    )


def _call_llm(system: str, question: str) -> str:
    if LLM_PROVIDER == "openai":
        from openai import OpenAI

        resp = OpenAI().chat.completions.create(
            model=ASKDOCS_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": question}],
        )
        return resp.choices[0].message.content or ""

    from anthropic import Anthropic

    resp = Anthropic().messages.create(
        model=ASKDOCS_MODEL,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


@app.get("/")
def root():
    return {
        "service": "askdocs",
        "provider": LLM_PROVIDER,
        "model": ASKDOCS_MODEL,
        "waste": {"nocache": WASTE_LLM_NOCACHE, "bloat": _bloat_enabled},
        "cache_enabled": _cache_enabled,
    }


@app.post("/admin/cache")
def admin_cache(toggle: CacheToggle):
    """Flip the exact-match cache at runtime — this IS applying/unapplying the L1 fix. The
    auditor calls this on /apply/L1 (enabled=true) and /unapply/L1 (enabled=false, clear=true)."""
    global _cache_enabled
    _cache_enabled = toggle.enabled
    if toggle.clear or not toggle.enabled:
        _cache.clear()
    log.info("admin: cache_enabled=%s (cleared=%s)", _cache_enabled, toggle.clear or not toggle.enabled)
    return {"cache_enabled": _cache_enabled, "entries": len(_cache)}


@app.post("/admin/bloat")
def admin_bloat(toggle: BloatToggle):
    """Flip the full-docs preamble at runtime — this IS applying/unapplying the L2 fix. The
    auditor calls this on /apply/L2 (enabled=false → context behind retrieval) and /unapply/L2."""
    global _bloat_enabled
    _bloat_enabled = toggle.enabled
    log.info("admin: bloat_enabled=%s", _bloat_enabled)
    return {"bloat_enabled": _bloat_enabled}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    # Exact-match cache is the L1 fix; runtime flag (seeded from env) lets /apply flip it live.
    cache_on = _cache_enabled
    key = hashlib.sha256(req.question.strip().lower().encode()).hexdigest()

    if cache_on and key in _cache:
        answer, expires = _cache[key]
        if expires > time.time():
            log.info("cache hit key=%s", key[:12])
            return {"answer": answer, "cached": True, "model": ASKDOCS_MODEL}

    answer = _call_llm(_system_prompt(req.question), req.question)
    if cache_on:
        _cache[key] = (answer, time.time() + CACHE_TTL)
    log.info("answered q=%r cached=%s", req.question[:60], False)
    return {"answer": answer, "cached": False, "model": ASKDOCS_MODEL}

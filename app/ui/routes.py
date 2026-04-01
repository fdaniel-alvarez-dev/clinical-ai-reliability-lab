from __future__ import annotations

import html
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _json_pretty(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


@router.get("/ui/reports/{report_id}", response_class=HTMLResponse)
async def report_ui(report_id: str, request: Request) -> HTMLResponse:
    repo = request.app.state.repo  # type: ignore[attr-defined]
    stored = repo.get_report(report_id=report_id)
    if stored is None or stored.final_json is None:
        raise HTTPException(status_code=404, detail="report not found")

    final_json = stored.final_json
    accepted = bool(final_json.get("accepted"))
    status_text = "ACCEPTED" if accepted else "REJECTED"

    artifacts = stored.artifacts_json or {}
    artifacts_pre = html.escape(_json_pretty(artifacts))
    final_pre = html.escape(_json_pretty(final_json))

    header = f"CHR Report Viewer — {html.escape(report_id)}"
    body = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{header}</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111a2e;
        --text: #e7eefc;
        --muted: #a9b7d0;
        --accent: #7aa2ff;
        --ok: #24d18f;
        --bad: #ff5b6e;
        --border: rgba(255,255,255,0.08);
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      }}
      body {{ margin: 0; background: var(--bg); color: var(--text); }}
      .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
      .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 16px; }}
      .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
      .kv {{ display: grid; grid-template-columns: 160px 1fr; gap: 8px 12px; }}
      .k {{ color: var(--muted); }}
      .badge {{ display: inline-block; padding: 6px 10px; border-radius: 999px; font-weight: 600; }}
      .ok {{ background: rgba(36,209,143,0.15); color: var(--ok); border: 1px solid rgba(36,209,143,0.35); }}
      .bad {{ background: rgba(255,91,110,0.12); color: var(--bad); border: 1px solid rgba(255,91,110,0.35); }}
      h1 {{ margin: 0 0 12px 0; font-size: 20px; }}
      h2 {{ margin: 20px 0 8px 0; font-size: 16px; color: var(--muted); }}
      pre {{ background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 12px; padding: 12px; overflow: auto; }}
      a {{ color: var(--accent); text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .hint {{ color: var(--muted); font-size: 13px; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h1 data-testid="title">{header}</h1>
        <div class="row">
          <div class="kv" style="flex: 1" data-testid="summary">
            <div class="k">Decision</div>
            <div>
              <span class="badge {"ok" if accepted else "bad"}" data-testid="decision">{status_text}</span>
            </div>
            <div class="k">Workflow ID</div>
            <div><code data-testid="workflow_id">{html.escape(str(final_json.get("workflow_id","")))}</code></div>
            <div class="k">Correlation ID</div>
            <div><code data-testid="correlation_id">{html.escape(str(final_json.get("correlation_id","")))}</code></div>
          </div>
          <div class="kv" style="flex: 1">
            <div class="k">API</div>
            <div class="hint">
              <a href="/v1/reports/{html.escape(report_id)}">report JSON</a> ·
              <a href="/v1/reports/{html.escape(report_id)}/evaluation">evaluation</a> ·
              <a href="/v1/reports/{html.escape(report_id)}/artifacts">artifacts index</a>
            </div>
            <div class="k">Synthetic</div>
            <div class="hint">This is an educational demo. Not medical advice.</div>
          </div>
        </div>

        <h2>Artifacts (refs)</h2>
        <div class="hint">For non-local stores these are URIs (e.g. s3:// or gs://).</div>
        <pre data-testid="artifacts_json">{artifacts_pre}</pre>

        <h2>Final JSON</h2>
        <pre data-testid="final_json">{final_pre}</pre>
      </div>
    </div>
  </body>
</html>
""".strip()

    return HTMLResponse(content=body)


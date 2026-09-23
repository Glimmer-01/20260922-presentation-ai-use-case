#!/usr/bin/env python3
"""Build a self-contained, offline demonstration of the review interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WEB = ROOT / "clinical-protocol-diff" / "assets" / "web"
SESSION = ROOT / "development" / "ui-preview-stage6-acceptance"
OUTPUT = HERE / "临床方案修订审阅-静态演示.html"

sys.path.insert(0, str(ROOT / "clinical-protocol-diff" / "scripts"))
from session_store import SessionStore  # noqa: E402


def script_safe_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


session_json = script_safe_json(SessionStore(SESSION).public())
style = (WEB / "style.css").read_text(encoding="utf-8")
layout = (WEB / "layout.css").read_text(encoding="utf-8")
app = (WEB / "app.js").read_text(encoding="utf-8")
index = (WEB / "index.html").read_text(encoding="utf-8")

# The real application receives its token through the local service URL. The
# static demo has no service, so a fixed non-secret marker only unlocks startup.
app = app.replace('let token = "";', 'let token = "static-demo";', 1)
app = app.replace('sessionStorage.getItem("clinical-review-token") || "";', 'sessionStorage.getItem("clinical-review-token") || token;', 1)
app = app.replace("已自动保存", "演示内容已保存在本浏览器")
app = app.replace("已读取保存的审阅", "已载入静态演示")
app = app.replace("}修订审阅`;", "}修订审阅 · 静态演示`;", 1)

mock = r'''(() => {
  "use strict";
  const BASE = __SESSION_JSON__;
  const STORAGE_KEY = "clinical-protocol-diff-static-demo-v1";
  const EDITABLE = ["id", "kind", "section", "old_ids", "new_ids", "old_text", "new_text", "include", "reviewed", "flagged", "tags", "note", "reason", "substantive", "risk"];
  const clone = (value) => JSON.parse(JSON.stringify(value));
  let demoSession = clone(BASE);
  let demoJob = null;

  function payloadOf(value) {
    return {
      revision: value.revision,
      metadata: clone(value.metadata || {}),
      changes: (value.changes || []).map((change) => Object.fromEntries(
        EDITABLE.filter((key) => key in change).map((key) => [key, clone(change[key])])
      ))
    };
  }

  function mergePayload(payload, bumpRevision) {
    const byID = new Map((demoSession.changes || []).map((change) => [change.id, change]));
    demoSession.metadata = { ...(demoSession.metadata || {}), ...(payload.metadata || {}) };
    demoSession.changes = (payload.changes || []).map((raw) => ({ ...(byID.get(raw.id) || {}), ...clone(raw) }));
    if (bumpRevision) demoSession.revision = Number(demoSession.revision || 0) + 1;
    else if (Number.isInteger(payload.revision)) demoSession.revision = Math.max(Number(BASE.revision || 0), payload.revision);
    demoSession.updated_at = new Date().toISOString();
  }

  function saveLocal() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(payloadOf(demoSession))); }
    catch (_) { /* Private browsing may disable file-page storage. */ }
  }

  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved && Array.isArray(saved.changes)) mergePayload(saved, false);
  } catch (_) { /* Fall back to the embedded acceptance snapshot. */ }

  function jsonResponse(value, status = 200) {
    return new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json; charset=utf-8" }
    });
  }

  function requestPath(input) {
    try { return new URL(input instanceof Request ? input.url : String(input), location.href).pathname; }
    catch (_) { return String(input); }
  }

  window.fetch = async (input, options = {}) => {
    const path = requestPath(input);
    const method = String(options.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
    let body = null;
    if (options.body) {
      try { body = JSON.parse(options.body); }
      catch (_) { return jsonResponse({ error: "演示请求数据无效。" }, 400); }
    }

    if (method === "GET" && path === "/api/health") return jsonResponse({ ok: true, mode: "static-demo" });
    if (method === "GET" && path === "/api/session") return jsonResponse(clone(demoSession));

    if (method === "PUT" && path === "/api/review") {
      if (!body || body.revision !== demoSession.revision) {
        return jsonResponse({ error: "演示页面版本已变化，请刷新后重试。" }, 409);
      }
      mergePayload(body, true);
      saveLocal();
      return jsonResponse(clone(demoSession));
    }

    if (method === "POST" && path === "/api/submit") {
      if (!body || body.revision !== demoSession.revision) {
        return jsonResponse({ error: "演示页面版本已变化，请刷新后重试。" }, 409);
      }
      mergePayload(body, true);
      saveLocal();
      demoJob = {
        id: "static-demo-job",
        status: "complete",
        filename: "静态演示 · Word 生成流程",
        preview_status: "unavailable",
        warnings: [{ message: "当前为离线静态演示：已模拟固定提交快照，但不会创建或下载正式 Word 文件。" }],
        created_at: new Date().toISOString()
      };
      return jsonResponse({
        job_id: demoJob.id,
        session: clone(demoSession),
        warnings: clone(demoJob.warnings)
      }, 202);
    }

    if (method === "GET" && path === "/api/jobs/static-demo-job" && demoJob) {
      return jsonResponse(clone(demoJob));
    }
    return jsonResponse({ error: "该功能在静态演示模式中不可用。" }, 404);
  };

  window.resetClinicalStaticDemo = () => {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) { /* Ignore. */ }
    location.reload();
  };

  document.getElementById("reset-static-demo")?.addEventListener("click", () => {
    if (window.confirm("恢复内置演示数据？本浏览器中对该演示页的修改会被清除。")) window.resetClinicalStaticDemo();
  });
})();'''.replace("__SESSION_JSON__", session_json)

demo_css = r'''
.static-demo-notice {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
  padding: 9px 24px;
  border-bottom: 1px solid #d7e5e3;
  background: #edf7f5;
  color: #235e5a;
  font-size: 11px;
  line-height: 1.5;
}
.static-demo-notice strong { white-space: nowrap; }
.static-demo-notice span { flex: 1; }
.static-demo-notice button {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--teal);
  font-size: 11px;
  text-decoration: underline;
}
@media (max-width: 800px) {
  .static-demo-notice { align-items: flex-start; padding: 9px 16px; flex-wrap: wrap; }
  .static-demo-notice span { flex-basis: calc(100% - 100px); }
  .static-demo-notice button { margin-left: auto; }
}
'''

index = index.replace("<title>临床方案 · 修订审阅</title>", "<title>临床方案 · 修订审阅 · 静态演示</title>")
index = index.replace('    <link rel="stylesheet" href="/style.css">\n', "")
index = index.replace('    <link rel="stylesheet" href="/layout.css">\n', "")
index = index.replace('    <script src="/app.js" defer></script>\n', "")
index = index.replace("  </head>", f"    <style>\n{style}\n{layout}\n{demo_css}\n    </style>\n  </head>")
notice = '''
    <section class="static-demo-notice" aria-label="静态演示说明">
      <strong>静态演示模式</strong>
      <span>无需本地服务；编辑仅保存在当前浏览器。提交会模拟流程，但不会生成正式 Word。</span>
      <button id="reset-static-demo" type="button">恢复演示数据</button>
    </section>'''
index = index.replace("    </header>", "    </header>" + notice, 1)
index = index.replace("本机审阅 · 自动保存", "静态演示 · 浏览器内保存")
index = index.replace("  </body>", f"    <script>\n{mock}\n    </script>\n    <script>\n{app}\n    </script>\n  </body>")

OUTPUT.write_text(index, encoding="utf-8")
print(OUTPUT)
print(f"bytes={OUTPUT.stat().st_size}")

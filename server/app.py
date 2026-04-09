"""
Code Review Environment – FastAPI Server App
Exposes the OpenEnv interface over HTTP/WebSocket.
"""
from __future__ import annotations
import sys
import os

# Ensure parent dir is on path so models/tasks/grader are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json

from models import CodeReviewAction, CodeReviewObservation, EpisodeState
from server.environment import CodeReviewEnvironment

app = FastAPI(
    title="Code Review OpenEnv",
    description="An RL environment for learning to review code — bugs, security, style, and performance.",
    version="1.0.0",
)

# ── Environment registry ──────────────────────────────────────────────────────
# One env instance per task; in production you'd have session management.
_envs: dict[str, CodeReviewEnvironment] = {}

VALID_TASKS = ["find_bug", "security_audit", "full_review"]


def _get_or_create(task_name: str) -> CodeReviewEnvironment:
    if task_name not in _envs:
        _envs[task_name] = CodeReviewEnvironment(task_name=task_name)
    return _envs[task_name]


# ── REST Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html><body style='font-family:monospace;padding:2rem;'>
    <h2>🔍 Code Review OpenEnv</h2>
    <p>An RL environment for AI-powered code review.</p>
    <ul>
      <li><a href='/docs'>📖 Interactive API Docs (Swagger)</a></li>
      <li><a href='/web'>🖥️  Web Interface</a></li>
      <li><b>Tasks:</b> find_bug (easy) | security_audit (medium) | full_review (hard)</li>
    </ul>
    </body></html>
    """


@app.get("/health")
def health():
    return {"status": "ok", "environment": "code_review_env", "version": "1.0.0"}


@app.post("/reset", response_model=CodeReviewObservation)
def reset(task_name: str = "find_bug"):
    if task_name not in VALID_TASKS:
        raise HTTPException(400, f"Unknown task '{task_name}'. Valid: {VALID_TASKS}")
    env = _get_or_create(task_name)
    return env.reset()


@app.post("/step")
def step(action: CodeReviewAction, task_name: str = "find_bug"):
    if task_name not in VALID_TASKS:
        raise HTTPException(400, f"Unknown task '{task_name}'. Valid: {VALID_TASKS}")
    if task_name not in _envs:
        raise HTTPException(400, "Call /reset first.")
    env = _envs[task_name]
    obs, reward, done, info = env.step(action)
    return {
        "observation": obs.model_dump(),
        "reward": round(reward, 4),
        "done": done,
        "info": info,
    }


@app.get("/state", response_model=EpisodeState)
def state(task_name: str = "find_bug"):
    if task_name not in _envs:
        raise HTTPException(400, "No active episode. Call /reset first.")
    return _envs[task_name].state()


@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {"name": "find_bug", "difficulty": "easy",
             "description": "Identify logical/runtime bugs in a Python module."},
            {"name": "security_audit", "difficulty": "medium",
             "description": "Detect security vulnerabilities in a Flask login endpoint."},
            {"name": "full_review", "difficulty": "hard",
             "description": "Comprehensive review: bugs + security + style + performance."},
        ]
    }


# ── WebSocket Endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{task_name}")
async def websocket_endpoint(websocket: WebSocket, task_name: str):
    """
    WebSocket interface for the OpenEnv client.
    Messages (JSON):
      { "type": "reset" }
      { "type": "step", "action": { ... } }
      { "type": "state" }
    """
    if task_name not in VALID_TASKS:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    env = _get_or_create(task_name)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "reset":
                obs = env.reset()
                await websocket.send_text(json.dumps({
                    "type": "observation",
                    "observation": obs.model_dump(),
                    "reward": 0.0,
                    "done": False,
                    "info": {},
                }))

            elif msg_type == "step":
                action = CodeReviewAction(**msg["action"])
                obs, reward, done, info = env.step(action)
                await websocket.send_text(json.dumps({
                    "type": "step_result",
                    "observation": obs.model_dump(),
                    "reward": round(reward, 4),
                    "done": done,
                    "info": info,
                }))

            elif msg_type == "state":
                s = env.state()
                await websocket.send_text(json.dumps({
                    "type": "state",
                    "state": s.model_dump(),
                }))

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        pass


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    """Start the Code Review OpenEnv server using uvicorn."""
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )


if __name__ == "__main__":
    main()


# ── Optional Web Interface ─────────────────────────────────────────────────────

@app.get("/web", response_class=HTMLResponse)
def web_interface():
    """Simple interactive web UI for testing the environment manually."""
    return """<!DOCTYPE html>
<html>
<head>
  <title>Code Review OpenEnv – Web Interface</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', monospace; background: #0d1117; color: #c9d1d9; margin: 0; }
    .header { background: linear-gradient(135deg, #1f6feb, #388bfd); padding: 1.5rem 2rem; }
    .header h1 { margin: 0; font-size: 1.5rem; color: white; }
    .header p { margin: 0.3rem 0 0; color: rgba(255,255,255,0.8); font-size: 0.9rem; }
    .container { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding: 1.5rem; }
    .panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.2rem; }
    .panel h3 { margin-top: 0; color: #58a6ff; font-size: 1rem; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }
    select, textarea, button { width: 100%; padding: 0.5rem; border-radius: 6px; font-size: 0.85rem; margin-bottom: 0.7rem; }
    select, textarea { background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; }
    button { background: #238636; color: white; border: none; cursor: pointer; font-weight: 600; }
    button:hover { background: #2ea043; }
    button.secondary { background: #1f6feb; }
    button.secondary:hover { background: #388bfd; }
    pre { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; overflow-x: auto; font-size: 0.78rem; white-space: pre-wrap; }
    .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .easy { background: #1a7f37; color: white; }
    .medium { background: #9a6700; color: white; }
    .hard { background: #b62324; color: white; }
    .reward-bar { height: 8px; background: #30363d; border-radius: 4px; margin: 0.5rem 0; }
    .reward-fill { height: 100%; background: linear-gradient(90deg, #238636, #2ea043); border-radius: 4px; transition: width 0.5s; }
    #log { max-height: 350px; overflow-y: auto; }
    .log-entry { border-left: 3px solid #30363d; padding: 0.4rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.8rem; }
    .log-entry.success { border-color: #238636; }
    .log-entry.error { border-color: #b62324; }
    .log-entry.info { border-color: #1f6feb; }
  </style>
</head>
<body>
  <div class="header">
    <h1>🔍 Code Review OpenEnv</h1>
    <p>Interactive interface for testing the RL environment</p>
  </div>
  <div class="container">
    <div class="panel">
      <h3>⚙️ Control Panel</h3>
      <label>Task:</label>
      <select id="task">
        <option value="find_bug">find_bug <span class="badge easy">easy</span></option>
        <option value="security_audit">security_audit (medium)</option>
        <option value="full_review">full_review (hard)</option>
      </select>
      <button class="secondary" onclick="doReset()">🔄 Reset Episode</button>
      <hr style="border-color:#30363d">
      <label>Issues JSON (array):</label>
      <textarea id="issues" rows="8" placeholder='[{"category":"bug","severity":"medium","description":"...","suggestion":"..."}]'></textarea>
      <label>Summary:</label>
      <textarea id="summary" rows="2" placeholder="Overall review summary..."></textarea>
      <label><input type="checkbox" id="approved"> Approve code</label><br><br>
      <button onclick="doStep()">▶️ Submit Review</button>
    </div>
    <div class="panel">
      <h3>📊 Episode State</h3>
      <div id="score-display" style="margin-bottom:1rem">
        <span>Cumulative Score: <b id="score-val">0.00</b></span>
        <div class="reward-bar"><div class="reward-fill" id="score-bar" style="width:0%"></div></div>
      </div>
      <div id="state-display"></div>
      <h3>📋 Code Snippet</h3>
      <pre id="code-display">Click "Reset Episode" to load code.</pre>
    </div>
  </div>
  <div style="padding: 0 1.5rem 1.5rem">
    <div class="panel">
      <h3>📝 Event Log</h3>
      <div id="log"></div>
    </div>
  </div>
<script>
const BASE = window.location.origin;
let currentScore = 0;

function log(msg, type='info') {
  const el = document.getElementById('log');
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.prepend(entry);
}

async function doReset() {
  const task = document.getElementById('task').value;
  try {
    const r = await fetch(`${BASE}/reset?task_name=${task}`, {method:'POST'});
    const data = await r.json();
    document.getElementById('code-display').textContent =
      `// ${data.snippet.filename}\\n\\n${data.snippet.code}`;
    document.getElementById('state-display').innerHTML =
      `<b>Task:</b> ${data.task_name}<br><b>Desc:</b> ${data.task_description}<br><b>Steps:</b> ${data.step_count}`;
    currentScore = 0;
    updateScore(0);
    log(`Episode reset for task: ${task}`, 'info');
  } catch(e) { log('Reset failed: '+e, 'error'); }
}

async function doStep() {
  const task = document.getElementById('task').value;
  const issuesTxt = document.getElementById('issues').value.trim();
  const summary = document.getElementById('summary').value.trim();
  const approved = document.getElementById('approved').checked;
  let issues = [];
  if (issuesTxt) {
    try { issues = JSON.parse(issuesTxt); } catch(e) { log('Invalid issues JSON: '+e, 'error'); return; }
  }
  if (!summary) { log('Please provide a summary.', 'error'); return; }
  const action = { issues, summary, approved };
  try {
    const r = await fetch(`${BASE}/step?task_name=${task}`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(action)
    });
    const data = await r.json();
    const obs = data.observation;
    updateScore(obs.score_so_far);
    document.getElementById('state-display').innerHTML =
      `<b>Step:</b> ${obs.step_count} | <b>Reward:</b> ${data.reward} | <b>Done:</b> ${data.done}<br><b>Feedback:</b> ${obs.last_feedback}`;
    const type = data.reward > 0.5 ? 'success' : data.reward > 0 ? 'info' : 'error';
    log(`Step ${obs.step_count} → reward=${data.reward} | ${obs.last_feedback}`, type);
  } catch(e) { log('Step failed: '+e, 'error'); }
}

function updateScore(val) {
  document.getElementById('score-val').textContent = val.toFixed(2);
  document.getElementById('score-bar').style.width = (val*100)+'%';
}

// Auto-load first task on page open
doReset();
</script>
</body>
</html>"""

import asyncio
import uuid
from flask import Flask, request, jsonify, render_template_string
from temporalio.client import Client
from workflow import SplunkAgentWorkflow

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Splunk AI Agent</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #0a0e17;
    --surface: #0f1623;
    --border: #1e2d45;
    --accent: #00d4ff;
    --accent2: #7c3aed;
    --green: #00ff9d;
    --orange: #ff6b35;
    --text: #e2e8f0;
    --muted: #4a5568;
    --glow: 0 0 20px rgba(0,212,255,0.15);
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }
  /* Grid background */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; position: relative; z-index: 1; }

  /* Header */
  header { text-align: center; margin-bottom: 50px; }
  .logo {
    display: inline-flex; align-items: center; gap: 12px;
    background: linear-gradient(135deg, var(--surface), #131d2e);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 24px;
    margin-bottom: 24px;
  }
  .logo-dot { width:10px; height:10px; border-radius:50%; background: var(--accent); box-shadow: 0 0 10px var(--accent); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  .logo-text { font-family:'Syne',sans-serif; font-weight:800; font-size:1rem; letter-spacing:3px; color:var(--accent); }

  h1 { font-family:'Syne',sans-serif; font-size:2.8rem; font-weight:800; line-height:1.1; margin-bottom:12px; }
  h1 span { color: var(--accent); }
  .subtitle { color: var(--muted); font-size:0.85rem; letter-spacing:1px; }

  /* Input area */
  .query-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .query-box:focus-within {
    border-color: var(--accent);
    box-shadow: var(--glow);
  }
  .query-label {
    font-size:0.7rem; letter-spacing:2px; color:var(--accent); margin-bottom:12px;
    display:flex; align-items:center; gap:8px;
  }
  .query-label::before { content:'//'; color:var(--muted); }
  textarea {
    width:100%; background:transparent; border:none; outline:none;
    color:var(--text); font-family:'JetBrains Mono',monospace; font-size:1rem;
    resize:none; line-height:1.6;
  }
  textarea::placeholder { color:var(--muted); }

  /* Examples */
  .examples { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; }
  .example-chip {
    background: rgba(0,212,255,0.05);
    border: 1px solid rgba(0,212,255,0.2);
    border-radius:20px;
    padding: 6px 14px;
    font-size:0.75rem;
    color: var(--accent);
    cursor:pointer;
    transition: all 0.2s;
  }
  .example-chip:hover { background:rgba(0,212,255,0.12); border-color:var(--accent); }

  /* Run button */
  .run-btn {
    width:100%;
    background: linear-gradient(135deg, var(--accent2), #5b21b6);
    border: none; border-radius: 12px;
    padding: 16px;
    font-family:'Syne',sans-serif; font-size:1rem; font-weight:700;
    color:#fff; cursor:pointer; letter-spacing:2px;
    transition: all 0.2s;
    position:relative; overflow:hidden;
  }
  .run-btn:hover:not(:disabled) { transform:translateY(-2px); box-shadow:0 8px 25px rgba(124,58,237,0.4); }
  .run-btn:disabled { opacity:0.6; cursor:not-allowed; transform:none; }
  .run-btn .spinner { display:none; }
  .run-btn.loading .btn-text { display:none; }
  .run-btn.loading .spinner { display:inline-block; }

  /* Pipeline steps */
  .pipeline {
    display:grid; grid-template-columns:1fr 1fr 1fr;
    gap:12px; margin-bottom:24px;
  }
  .step {
    background:var(--surface); border:1px solid var(--border);
    border-radius:12px; padding:16px; text-align:center;
    transition: all 0.4s;
  }
  .step.active { border-color:var(--accent); box-shadow:var(--glow); }
  .step.done { border-color:var(--green); }
  .step-icon { font-size:1.5rem; margin-bottom:8px; }
  .step-name { font-size:0.65rem; letter-spacing:2px; color:var(--muted); }
  .step.active .step-name { color:var(--accent); }
  .step.done .step-name { color:var(--green); }

  /* Results */
  #results { display:none; }

  .result-card {
    background:var(--surface); border:1px solid var(--border);
    border-radius:16px; padding:24px; margin-bottom:16px;
    animation: slideUp 0.4s ease;
  }
  @keyframes slideUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:none} }

  .card-label {
    font-size:0.65rem; letter-spacing:2px; margin-bottom:12px;
    display:flex; align-items:center; gap:8px;
  }
  .card-label .dot { width:6px; height:6px; border-radius:50%; }
  .dot-blue { background:var(--accent); }
  .dot-green { background:var(--green); }
  .dot-orange { background:var(--orange); }

  /* Query display */
  .spl-query {
    background:#060d16; border:1px solid var(--border);
    border-radius:8px; padding:16px;
    font-size:0.9rem; color:var(--accent);
    word-break:break-all; line-height:1.6;
    position:relative;
  }
  .copy-btn {
    position:absolute; top:10px; right:10px;
    background:rgba(0,212,255,0.1); border:1px solid rgba(0,212,255,0.2);
    border-radius:6px; padding:4px 10px;
    color:var(--accent); font-size:0.7rem; cursor:pointer;
    font-family:'JetBrains Mono',monospace;
  }
  .copy-btn:hover { background:rgba(0,212,255,0.2); }

  .explanation { color:var(--muted); font-size:0.82rem; margin-top:10px; line-height:1.6; }

  /* Answer */
  .answer-text {
    font-size:1.1rem; line-height:1.7; color:var(--text);
    font-family:'Syne',sans-serif;
  }
  .stat-badge {
    display:inline-flex; align-items:center; gap:8px;
    background:rgba(0,255,157,0.08); border:1px solid rgba(0,255,157,0.2);
    border-radius:8px; padding:8px 16px; margin-top:12px;
    font-size:0.85rem; color:var(--green);
  }

  /* Data table */
  .table-wrap { overflow-x:auto; border-radius:8px; border:1px solid var(--border); }
  table { width:100%; border-collapse:collapse; font-size:0.78rem; }
  th {
    background:#060d16; padding:10px 14px;
    text-align:left; color:var(--accent);
    font-size:0.65rem; letter-spacing:1px;
    border-bottom:1px solid var(--border);
  }
  td { padding:10px 14px; border-bottom:1px solid rgba(30,45,69,0.5); color:var(--muted); }
  tr:last-child td { border-bottom:none; }
  tr:hover td { background:rgba(0,212,255,0.03); color:var(--text); }

  /* Error */
  .error-card {
    background:rgba(255,107,53,0.05); border:1px solid rgba(255,107,53,0.3);
    border-radius:12px; padding:20px;
    color:var(--orange); font-size:0.85rem;
  }

  @media(max-width:600px) {
    h1 { font-size:1.8rem; }
    .pipeline { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">
      <div class="logo-dot"></div>
      <div class="logo-text">SPLUNK AI AGENT</div>
    </div>
    <h1>Ask Your <span>Logs</span><br/>Anything.</h1>
    <p class="subtitle">// POWERED BY OLLAMA + TEMPORAL + SPLUNK //</p>
  </header>

  <!-- Pipeline -->
  <div class="pipeline">
    <div class="step" id="step1">
      <div class="step-icon">🧠</div>
      <div class="step-name">OLLAMA → SPL</div>
    </div>
    <div class="step" id="step2">
      <div class="step-icon">🔍</div>
      <div class="step-name">SPLUNK QUERY</div>
    </div>
    <div class="step" id="step3">
      <div class="step-icon">💬</div>
      <div class="step-name">FORMAT ANSWER</div>
    </div>
  </div>

  <!-- Input -->
  <div class="query-box">
    <div class="query-label">NATURAL LANGUAGE QUERY</div>
    <textarea id="prompt" rows="3" placeholder="e.g. Give me total number of requests that have 200 response code"></textarea>
  </div>

  <!-- Example chips -->
  <div class="examples">
    <div class="example-chip" onclick="setPrompt(this)">Total 200 status requests</div>
    <div class="example-chip" onclick="setPrompt(this)">Top 10 error 500 sources</div>
    <div class="example-chip" onclick="setPrompt(this)">Requests per hour today</div>
    <div class="example-chip" onclick="setPrompt(this)">Most active IP addresses</div>
    <div class="example-chip" onclick="setPrompt(this)">All 404 errors last 7 days</div>
  </div>

  <button class="run-btn" id="runBtn" onclick="runQuery()">
    <span class="btn-text">⚡ RUN AGENT</span>
    <span class="spinner">⟳ AGENT RUNNING...</span>
  </button>

  <!-- Results -->
  <div id="results">
    <!-- Query card -->
    <div class="result-card" id="queryCard">
      <div class="card-label"><div class="dot dot-blue"></div> GENERATED SPL QUERY</div>
      <div class="spl-query" id="splQuery">
        <button class="copy-btn" onclick="copyQuery()">COPY</button>
        <span id="queryText"></span>
      </div>
      <div class="explanation" id="explanation"></div>
    </div>

    <!-- Answer card -->
    <div class="result-card" id="answerCard">
      <div class="card-label"><div class="dot dot-green"></div> AGENT ANSWER</div>
      <div class="answer-text" id="answerText"></div>
      <div class="stat-badge" id="statBadge"></div>
    </div>

    <!-- Data table -->
    <div class="result-card" id="tableCard">
      <div class="card-label"><div class="dot dot-orange"></div> RAW DATA SAMPLE</div>
      <div class="table-wrap" id="tableWrap"></div>
    </div>

    <!-- Error -->
    <div class="error-card" id="errorCard" style="display:none"></div>
  </div>
</div>

<script>
function setPrompt(el) {
  document.getElementById('prompt').value = el.textContent;
}

function setStep(n) {
  ['step1','step2','step3'].forEach((id,i) => {
    const el = document.getElementById(id);
    el.className = 'step' + (i < n ? ' done' : i === n-1 ? ' active' : '');
  });
}

function copyQuery() {
  navigator.clipboard.writeText(document.getElementById('queryText').textContent);
  document.querySelector('.copy-btn').textContent = 'COPIED!';
  setTimeout(() => document.querySelector('.copy-btn').textContent = 'COPY', 1500);
}

async function runQuery() {
  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) return;

  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  btn.classList.add('loading');
  document.getElementById('results').style.display = 'none';
  document.getElementById('errorCard').style.display = 'none';

  setStep(1);

  try {
    const resp = await fetch('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });

    setStep(2);
    await new Promise(r => setTimeout(r, 400));
    setStep(3);

    const data = await resp.json();

    if (!resp.ok || data.error) {
      throw new Error(data.error || 'Agent failed');
    }

    // Populate query card
    document.getElementById('queryText').textContent = data.query;
    document.getElementById('explanation').textContent = data.explanation;

    // Populate answer
    document.getElementById('answerText').textContent = data.answer;
    document.getElementById('statBadge').textContent = `📊 ${data.total_results} result(s) returned from Splunk`;

    // Build table
    const rows = data.sample_data || [];
    if (rows.length > 0) {
      const cols = Object.keys(rows[0]).filter(k => !k.startsWith('_'));
      let html = '<table><thead><tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';
      rows.forEach(r => {
        html += '<tr>' + cols.map(c => `<td>${r[c] ?? ''}</td>`).join('') + '</tr>';
      });
      html += '</tbody></table>';
      document.getElementById('tableWrap').innerHTML = html;
      document.getElementById('tableCard').style.display = 'block';
    } else {
      document.getElementById('tableCard').style.display = 'none';
    }

    document.getElementById('results').style.display = 'block';
    ['step1','step2','step3'].forEach(id => document.getElementById(id).className = 'step done');

  } catch (err) {
    document.getElementById('errorCard').textContent = '⚠ ' + err.message;
    document.getElementById('errorCard').style.display = 'block';
    document.getElementById('results').style.display = 'block';
    ['step1','step2','step3'].forEach(id => document.getElementById(id).className = 'step');
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
}

// Enter to submit
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('prompt').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runQuery(); }
  });
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    user_prompt = data.get("prompt", "").strip()
    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Run Temporal workflow synchronously from Flask
    result = asyncio.run(_run_workflow(user_prompt))
    return jsonify(result)


async def _run_workflow(prompt: str) -> dict:
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        SplunkAgentWorkflow.run,
        prompt,
        id=f"splunk-agent-{uuid.uuid4()}",
        task_queue="splunk-agent-queue",
    )
    return result


if __name__ == "__main__":
    print("🌐 Starting Splunk Agent UI at http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
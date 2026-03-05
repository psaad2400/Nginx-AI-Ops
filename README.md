## 📦 Part of nginx-ai-ops
This agents folder is one part of the larger nginx-ai-ops platform which also includes Splunk setup, Prometheus + Grafana monitoring, and log automation scripts. See the [main README](../README.md) for the full picture.

# 🤖 Agents

> The AI brain of nginx-ai-ops — each agent is a Temporal workflow powered by a local LLM (Ollama).

---

## Available Agents

| Agent | Status | Port | Description |
|---|---|---|---|
| [`query_agent`](./query_agent) | ✅ Active | 5001 | Ask nginx logs anything in plain English |

---

## How Agents Work
```
User Prompt
     ↓
Temporal Workflow (durable, crash-safe)
     ↓
Ollama (local LLM — no internet needed)
     ↓
Splunk REST API
     ↓
Answer + Raw Data
```

---

## Quick Start
```bash
# Install dependencies
pip install -r ../requirements.txt

# Pull the LLM
ollama pull llama3

# Start Temporal
temporal server start-dev

# Run the query agent
cd query_agent
python worker.py    # Terminal 1
python app.py       # Terminal 2
```

→ Open **http://localhost:5001**

---

> Each agent has its own README with full setup instructions.
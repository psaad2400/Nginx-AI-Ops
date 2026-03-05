import json
import time
import requests
import urllib3
from temporalio import activity

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ─── CONFIG ────────────────────────────────────────────────────────────────────
OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "llama3"         

SPLUNK_HOST    = "<YOUR VM IP>"
SPLUNK_PORT    = 8089
SPLUNK_USER    = "<YOUR SPLUNK USERNAME>"
SPLUNK_PASS    = "<YOUR SPLUNK PASSWORD>"
SPLUNK_INDEX   = "<SPLUNK INDEX NAME>"

SPLUNK_BASE    = f"https://{SPLUNK_HOST}:{SPLUNK_PORT}"


# ─── Activity 1: Convert natural language → Splunk SPL query ──────────────────
@activity.defn
async def generate_splunk_query(user_prompt: str) -> dict:
    """
    Sends the user's natural language prompt to Ollama (local LLM).
    Returns the generated Splunk SPL query + explanation.
    """
    system_context = """You are an expert Splunk SPL (Search Processing Language) query generator.

Your job: Convert natural language questions into valid Splunk SPL queries for nginx access logs.

Rules:
1. Always output ONLY a JSON object, nothing else.
2. JSON format must be exactly:
   {
     "query": "<the SPL query>",
     "explanation": "<brief explanation of what the query does>",
     "time_range": "<earliest time range e.g. -24h, -7d, -1h>"
   }
3. ALWAYS use index=nginx unless the user specifies a different index.
4. ALWAYS use these exact field names — do not guess or invent field names:
   - remote_addr      : client IP address making the request
   - status           : HTTP response status code (200, 404, 500, etc.)
   - request_method   : HTTP method (GET, POST, PUT, DELETE)
   - uri              : the request path/endpoint (e.g. /api/login)
   - bytes_sent       : response size in bytes
   - request_time     : time in seconds to process the request (float)
   - http_user_agent  : browser or client making the request
   - http_referer     : referring URL
   - upstream_addr    : backend server that handled the request
   - upstream_time    : time in seconds taken by the backend
   - server_name      : nginx virtual host / domain name
   - protocol         : HTTP protocol version (HTTP/1.1, HTTP/2.0)
5. Common query patterns using the above fields:
   - Total 200 requests:     index=nginx status=200 | stats count
   - Count by status code:   index=nginx | stats count by status
   - Top client IPs:         index=nginx | top limit=10 remote_addr
   - Slowest endpoints:      index=nginx | stats avg(request_time) by uri | sort -avg(request_time) | head 10
   - All 4xx/5xx errors:     index=nginx status>=400 | stats count by status uri
   - Top requested URIs:     index=nginx | top limit=10 uri
   - Bandwidth per endpoint: index=nginx | stats sum(bytes_sent) as total_bytes by uri | sort -total_bytes
   - Requests over time:     index=nginx | timechart span=1h count by status
   - Requests by method:     index=nginx | stats count by request_method
   - Slow upstream calls:    index=nginx | stats avg(upstream_time) by upstream_addr | sort -avg(upstream_time)
6. Always add | head 1000 for safety on large result sets unless aggregating (stats/timechart/top).
7. Return ONLY the JSON. No markdown, no explanation outside JSON."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{system_context}\n\nUser question: {user_prompt}\n\nRespond with JSON only:",
        "stream": False,
        "options": {"temperature": 0.1}
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()

    raw = response.json().get("response", "").strip()

    # Strip markdown fences if Ollama wraps response
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    return {
        "query": parsed.get("query", ""),
        "explanation": parsed.get("explanation", ""),
        "time_range": parsed.get("time_range", "-24h")
    }


# ─── Activity 2: Execute query on Splunk and get results ─────────────────────
@activity.defn
async def execute_splunk_query(query_info: dict) -> dict:
    """
    Submits the SPL query to Splunk's REST API and returns results.
    Uses basic auth. Polls until the job is done.
    """
    spl_query = query_info["query"]
    time_range = query_info.get("time_range", "-24h")

    auth = (SPLUNK_USER, SPLUNK_PASS)
    verify_ssl = False

    # Step 1: Create search job
    job_resp = requests.post(
        f"{SPLUNK_BASE}/services/search/jobs",
        auth=auth,
        verify=verify_ssl,
        data={
            "search": f"search {spl_query}",
            "earliest_time": time_range,
            "latest_time": "now",
            "output_mode": "json"
        },
        timeout=30
    )
    job_resp.raise_for_status()
    job_sid = job_resp.json()["sid"]

    # Step 2: Poll until complete
    for _ in range(30):  # max 30 * 2s = 60s wait
        status_resp = requests.get(
            f"{SPLUNK_BASE}/services/search/jobs/{job_sid}",
            auth=auth,
            verify=verify_ssl,
            params={"output_mode": "json"},
            timeout=15
        )
        status = status_resp.json()["entry"][0]["content"]
        if status["isDone"]:
            break
        time.sleep(2)

    # Step 3: Fetch results
    results_resp = requests.get(
        f"{SPLUNK_BASE}/services/search/jobs/{job_sid}/results",
        auth=auth,
        verify=verify_ssl,
        params={"output_mode": "json", "count": 100},
        timeout=30
    )
    results_resp.raise_for_status()
    results_data = results_resp.json()

    results = results_data.get("results", [])
    total   = len(results)

    return {
        "total_results": total,
        "results": results[:50],
        "job_sid": job_sid,
        "status": "success"
    }


# ─── Activity 3: Format results into a human-readable answer ─────────────────
@activity.defn
async def format_answer(user_prompt: str, query_info: dict, splunk_results: dict) -> dict:
    """
    Uses Ollama to turn raw Splunk results into a clear English answer.
    """
    results_preview = json.dumps(splunk_results["results"][:10], indent=2)

    prompt = f"""You are a data analyst. The user asked: "{user_prompt}"

We ran this Splunk query: {query_info['query']}
Total results returned: {splunk_results['total_results']}
Sample data (first 10 rows):
{results_preview}

Write a clear, concise answer to the user's question based on this data.
Be specific with numbers. Keep it under 5 sentences.
Do NOT mention Splunk or SPL — just answer the question naturally."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    answer = response.json().get("response", "").strip()

    return {
        "answer": answer,
        "query": query_info["query"],
        "explanation": query_info["explanation"],
        "total_results": splunk_results["total_results"],
        "sample_data": splunk_results["results"][:10]
    }
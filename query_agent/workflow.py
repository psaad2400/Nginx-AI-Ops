# workflow.py
# Temporal Workflow — orchestrates the 3-step agent pipeline:
#   1. Generate Splunk query from natural language (Ollama)
#   2. Execute query on Splunk server
#   3. Format results into a human-readable answer (Ollama)

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


with workflow.unsafe.imports_passed_through():
    from activities import generate_splunk_query, execute_splunk_query, format_answer


@workflow.defn
class SplunkAgentWorkflow:
    """
    Durable agentic workflow. Even if the process crashes mid-query,
    Temporal replays from the last checkpoint automatically.
    """

    @workflow.run
    async def run(self, user_prompt: str) -> dict:
        workflow.logger.info(f"🚀 SplunkAgent started | Prompt: {user_prompt}")

        # ── Step 1: Natural Language → SPL Query (Ollama) ─────────────────────
        workflow.logger.info("🧠 Generating Splunk query via Ollama...")
        query_info = await workflow.execute_activity(
            generate_splunk_query,
            args=[user_prompt],
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        workflow.logger.info(f"✅ Query generated: {query_info['query']}")

        # ── Step 2: Execute Query on Splunk ────────────────────────────────────
        workflow.logger.info("🔍 Executing query on Splunk server...")
        splunk_results = await workflow.execute_activity(
            execute_splunk_query,
            args=[query_info],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        workflow.logger.info(f"📊 Got {splunk_results['total_results']} results from Splunk")

        # ── Step 3: Format into Human-Readable Answer (Ollama) ────────────────
        workflow.logger.info("💬 Formatting answer via Ollama...")
        final = await workflow.execute_activity(
            format_answer,
            args=[user_prompt, query_info, splunk_results],
            start_to_close_timeout=timedelta(seconds=90),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        workflow.logger.info("🏁 Workflow complete!")
        return final
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from workflow import SplunkAgentWorkflow
from activities import generate_splunk_query, execute_splunk_query, format_answer


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="splunk-agent-queue",
        workflows=[SplunkAgentWorkflow],
        activities=[generate_splunk_query, execute_splunk_query, format_answer],
    )

    print("✅ Splunk Agent Worker is running!")
    print("   Listening on task queue: splunk-agent-queue")
    print("   Now run: python app.py\n")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
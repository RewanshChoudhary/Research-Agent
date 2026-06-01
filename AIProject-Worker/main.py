import asyncio
import os

from worker.core.consumer import consume


def main():
    consumer_name = os.getenv("REDIS_CONSUMER_NAME", "worker-1")
    asyncio.run(consume(consumer_name))


if __name__ == "__main__":
    main()

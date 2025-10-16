import asyncio
from typing import Dict
from loguru import logger

from worker.tasks import cerbo_collection_task_worker, energetic_schedule_task_worker

class WorkerManager:
    def __init__(self):
        # словарь: object_id -> {"collection_task": Task, "schedule_task": Task}
        self.tasks: Dict[str, Dict[str, asyncio.Task]] = {}

    async def start_worker(self, object_id: str, object_name: str ):
        if object_id in self.tasks:
            logger.warning(f"Worker for object {object_id} is already running.")
            return

        # создаём асинхронные задачи
        collection_task = asyncio.create_task(cerbo_collection_task_worker(object_id=object_id, object_name=object_name))
        schedule_task = asyncio.create_task(energetic_schedule_task_worker(object_id))

        self.tasks[object_id] = {
            "collection_task": collection_task,
            "schedule_task": schedule_task,
        }
        logger.info(f"Worker tasks started for object {object_id}")

    async def stop_worker(self, object_id: str):
        if object_id not in self.tasks:
            logger.warning(f"No worker running for object {object_id}")
            return

        for task in self.tasks[object_id].values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        del self.tasks[object_id]
        logger.info(f"Worker tasks stopped for object {object_id}")
"""
Device Polling Tasks API
Управление задачами фонового опроса энергетических устройств
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from loguru import logger
import aiohttp

from cor_pass.database.db import get_db
from cor_pass.database.models import DevicePollingTask, EnergeticObject, User
from cor_pass.schemas import (
    DevicePollingTaskCreate,
    DevicePollingTaskUpdate,
    DevicePollingTaskResponse,
    DevicePollingTaskListResponse,
)
from cor_pass.services.shared.access import admin_access

router = APIRouter(prefix="/polling-tasks", tags=["Device Polling Tasks"])


@router.post(
    "/",
    response_model=DevicePollingTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу фонового опроса",
    description="""
    Создаёт новую задачу фонового опроса для энергетического объекта.
    
    **Типы задач:**
    - `cerbo_collection` - Сбор данных с Cerbo GX через API
    - `schedule_check` - Проверка и применение расписания
    - `modbus_registers` - Чтение Modbus регистров по конфигу
    - `custom_command` - Пользовательская команда
    
    **Пример command_config для modbus_registers:**
    ```json
    {
        "register_groups": ["battery", "solar", "grid"]
    }
    ```
    """
)
async def create_polling_task(
    task: DevicePollingTaskCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Создание новой задачи опроса"""
    try:
        # Проверяем существование объекта
        result = await db.execute(
            select(EnergeticObject).where(EnergeticObject.id == task.energetic_object_id)
        )
        energetic_object = result.scalar_one_or_none()
        
        if not energetic_object:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Energetic object {task.energetic_object_id} not found"
            )
        
        # Создаём задачу
        new_task = DevicePollingTask(
            energetic_object_id=task.energetic_object_id,
            task_type=task.task_type.value,
            command_config=task.command_config,
            interval_seconds=task.interval_seconds,
            is_active=task.is_active
        )
        
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        
        logger.info(f"Created polling task {new_task.id} for object {task.energetic_object_id}")
        
        return DevicePollingTaskResponse.model_validate(new_task)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating polling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create polling task: {str(e)}"
        )


@router.get(
    "/object/{object_id}",
    response_model=DevicePollingTaskListResponse,
    summary="Получить все задачи объекта",
    description="Возвращает список всех задач опроса для указанного энергетического объекта"
)
async def get_object_polling_tasks(
    object_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Получение всех задач опроса для объекта"""
    try:
        # Получаем объект
        result = await db.execute(
            select(EnergeticObject).where(EnergeticObject.id == object_id)
        )
        energetic_object = result.scalar_one_or_none()
        
        if not energetic_object:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Energetic object {object_id} not found"
            )
        
        # Получаем все задачи
        result = await db.execute(
            select(DevicePollingTask).where(
                DevicePollingTask.energetic_object_id == object_id
            ).order_by(DevicePollingTask.created_at.desc())
        )
        tasks = result.scalars().all()
        
        active_count = sum(1 for task in tasks if task.is_active)
        
        return DevicePollingTaskListResponse(
            energetic_object_id=object_id,
            energetic_object_name=energetic_object.name,
            tasks=[DevicePollingTaskResponse.model_validate(task) for task in tasks],
            total_tasks=len(tasks),
            active_tasks=active_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting polling tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get polling tasks: {str(e)}"
        )


@router.get(
    "/{task_id}",
    response_model=DevicePollingTaskResponse,
    summary="Получить задачу по ID",
    description="Возвращает детали конкретной задачи опроса"
)
async def get_polling_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Получение задачи по ID"""
    try:
        result = await db.execute(
            select(DevicePollingTask).where(DevicePollingTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Polling task {task_id} not found"
            )
        
        return DevicePollingTaskResponse.model_validate(task)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting polling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get polling task: {str(e)}"
        )


@router.patch(
    "/{task_id}",
    response_model=DevicePollingTaskResponse,
    summary="Обновить задачу опроса",
    description="Обновляет параметры задачи опроса (интервал, конфигурацию, статус активности)"
)
async def update_polling_task(
    task_id: str,
    task_update: DevicePollingTaskUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Обновление задачи опроса"""
    try:
        result = await db.execute(
            select(DevicePollingTask).where(DevicePollingTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Polling task {task_id} not found"
            )
        
        # Обновляем поля
        update_data = task_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "task_type" and value is not None:
                setattr(task, field, value.value)
            else:
                setattr(task, field, value)
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Updated polling task {task_id}")
        
        return DevicePollingTaskResponse.model_validate(task)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating polling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update polling task: {str(e)}"
        )


@router.patch(
    "/{task_id}/toggle",
    response_model=DevicePollingTaskResponse,
    summary="Включить/выключить задачу",
    description="Переключает статус активности задачи (вкл/выкл фоновый опрос)"
)
async def toggle_polling_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Переключение активности задачи"""
    try:
        result = await db.execute(
            select(DevicePollingTask).where(DevicePollingTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Polling task {task_id} not found"
            )
        
        task.is_active = not task.is_active
        
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Toggled polling task {task_id} to {'active' if task.is_active else 'inactive'}")
        
        return DevicePollingTaskResponse.model_validate(task)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error toggling polling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle polling task: {str(e)}"
        )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу опроса",
    description="Удаляет задачу фонового опроса (фоновая задача также будет остановлена)"
)
async def delete_polling_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Удаление задачи опроса"""
    try:
        result = await db.execute(
            select(DevicePollingTask).where(DevicePollingTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Polling task {task_id} not found"
            )
        
        await db.delete(task)
        await db.commit()
        
        logger.info(f"Deleted polling task {task_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting polling task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete polling task: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[DevicePollingTaskResponse],
    summary="Получить все задачи опроса",
    description="Возвращает список всех задач опроса во всей системе"
)
async def get_all_polling_tasks(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(admin_access)
):
    """Получение всех задач опроса"""
    try:
        query = select(DevicePollingTask)
        
        if active_only:
            query = query.where(DevicePollingTask.is_active == True)
        
        query = query.order_by(DevicePollingTask.created_at.desc())
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return [DevicePollingTaskResponse.model_validate(task) for task in tasks]
        
    except Exception as e:
        logger.error(f"Error getting all polling tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get polling tasks: {str(e)}"
        )


@router.post(
    "/reload",
    status_code=status.HTTP_200_OK,
    summary="Перезагрузить задачи воркера",
    description="""
    Отправляет сигнал воркеру для немедленной перезагрузки задач из БД.
    Полезно после создания/обновления/удаления задач для применения изменений без ожидания.
    
    **Примечание:** Воркер также автоматически перезагружает задачи каждые 5 секунд.
    """
)
async def trigger_worker_reload(
    admin: User = Depends(admin_access)
):
    """
    Триггер немедленной перезагрузки задач воркера
    
    Отправляет внутренний HTTP запрос к воркеру (если доступен webhook endpoint)
    или просто возвращает success, полагаясь на автоматическую синхронизацию
    """
    try:
        # TODO: Можно добавить webhook endpoint на воркере для немедленного обновления
        # Пока просто возвращаем успех, т.к. воркер сам синхронизируется каждые 5 сек
        
        logger.info("Worker reload triggered via API")
        
        return {
            "status": "success",
            "message": "Worker will reload tasks within 5 seconds (automatic sync interval)"
        }
        
    except Exception as e:
        logger.error(f"Error triggering worker reload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger worker reload: {str(e)}"
        )

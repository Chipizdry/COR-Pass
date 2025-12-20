"""
Dynamic Polling Manager
Управляет фоновыми задачами опроса устройств на основе конфигурации в БД
"""
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from loguru import logger
from sqlalchemy import select

from cor_pass.database.db import async_session_maker
from cor_pass.database.models import DevicePollingTask, EnergeticObject
from cor_pass.database.models.enums import PollingTaskType
from worker.modbus_client import decode_signed_16, decode_signed_32, register_modbus_error, register_modbus_success


class PollingManager:
    """
    Динамический менеджер фоновых задач опроса устройств
    
    Особенности:
    - Загружает активные задачи из БД при старте
    - Создаёт asyncio.Task для каждой активной задачи
    - Поддерживает динамическое добавление/удаление задач
    - Читает конфигурации Modbus из JSON файлов
    """
    
    def __init__(self):
        # Словарь: task_id -> {"task": asyncio.Task, "config": dict}
        self.tasks: Dict[str, Dict[str, Any]] = {}
        
        # Путь к конфигам Modbus
        self.modbus_configs_dir = Path(__file__).parent / "modbus_configs"
        
        # Кэш загруженных конфигов: filename -> config dict
        self.modbus_configs_cache: Dict[str, dict] = {}
        
        # Регистрация обработчиков типов задач
        self.task_handlers: Dict[str, Callable] = {
            PollingTaskType.CERBO_COLLECTION.value: self._run_cerbo_collection_task,
            PollingTaskType.SCHEDULE_CHECK.value: self._run_schedule_check_task,
            PollingTaskType.MODBUS_REGISTERS.value: self._run_modbus_registers_task,
            PollingTaskType.CUSTOM_COMMAND.value: self._run_custom_command_task,
        }
    
    def load_modbus_config(self, config_filename: str) -> Optional[dict]:
        """Загрузка Modbus конфигурации из JSON файла"""
        if config_filename in self.modbus_configs_cache:
            return self.modbus_configs_cache[config_filename]
        
        config_path = self.modbus_configs_dir / config_filename
        
        if not config_path.exists():
            logger.error(f"Modbus config file not found: {config_path}")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.modbus_configs_cache[config_filename] = config
                logger.info(f"Loaded Modbus config: {config_filename}")
                return config
        except Exception as e:
            logger.error(f"Error loading Modbus config {config_filename}: {e}", exc_info=True)
            return None
    
    async def start_polling_task(self, polling_task: DevicePollingTask, energetic_object: EnergeticObject):
        """Запуск задачи опроса"""
        task_id = polling_task.id
        
        if task_id in self.tasks:
            logger.warning(f"Polling task {task_id} is already running")
            return
        
        # Выбираем обработчик по типу задачи
        handler = self.task_handlers.get(polling_task.task_type)
        
        if not handler:
            logger.error(f"Unknown task type: {polling_task.task_type}")
            return
        
        # Создаём asyncio.Task
        async_task = asyncio.create_task(
            handler(
                task_id=task_id,
                object_id=energetic_object.id,
                object_name=energetic_object.name,
                interval=polling_task.interval_seconds,
                command_config=polling_task.command_config,
                modbus_config_file=energetic_object.modbus_config_file
            )
        )
        
        self.tasks[task_id] = {
            "task": async_task,
            "config": {
                "task_type": polling_task.task_type,
                "object_id": energetic_object.id,
                "object_name": energetic_object.name,
                "interval": polling_task.interval_seconds,
                "command_config": polling_task.command_config,
            }
        }
        
        logger.info(
            f"Started polling task {task_id} ({polling_task.task_type}) "
            f"for object {energetic_object.name} with interval {polling_task.interval_seconds}s"
        )
    
    async def stop_polling_task(self, task_id: str):
        """Остановка задачи опроса"""
        if task_id not in self.tasks:
            logger.warning(f"Polling task {task_id} is not running")
            return
        
        task_info = self.tasks[task_id]
        async_task = task_info["task"]
        
        # Отменяем задачу
        async_task.cancel()
        
        try:
            await async_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error stopping task {task_id}: {e}", exc_info=True)
        
        del self.tasks[task_id]
        logger.info(f"Stopped polling task {task_id}")
    
    async def reload_tasks_from_db(self):
        """Загрузка/обновление задач из БД"""
        try:
            async with async_session_maker() as db:
                # Получаем все активные задачи
                result = await db.execute(
                    select(DevicePollingTask, EnergeticObject)
                    .join(EnergeticObject, DevicePollingTask.energetic_object_id == EnergeticObject.id)
                    .where(
                        DevicePollingTask.is_active == True,
                        EnergeticObject.is_active == True
                    )
                )
                rows = result.all()
                
                # SQLAlchemy возвращает список Row(tuple), распаковываем явно
                active_tasks = [(row[0], row[1]) for row in rows]
                
                logger.info(f"Found {len(active_tasks)} active polling tasks in DB")
                
                active_task_ids = {polling_task.id for (polling_task, _) in active_tasks}
                
                # Запускаем новые задачи
                for polling_task, energetic_object in active_tasks:
                    
                    if polling_task.id not in self.tasks:
                        logger.info(
                            f"Starting new task {polling_task.id}: {polling_task.task_type} "
                            f"for object {energetic_object.name} ({energetic_object.protocol})"
                        )
                        await self.start_polling_task(polling_task, energetic_object)
                    else:
                        logger.debug(f"Task {polling_task.id} already running")
                
                # Останавливаем удалённые/неактивные задачи
                for task_id in list(self.tasks.keys()):
                    if task_id not in active_task_ids:
                        logger.info(f"Stopping inactive task {task_id}")
                        await self.stop_polling_task(task_id)
                
                logger.info(f"Polling manager status: {len(self.tasks)} tasks running")
                
        except Exception as e:
            logger.error(f"Error reloading tasks from DB: {e}", exc_info=True)
    
    # ==================== Task Handlers ====================
    
    async def _run_cerbo_collection_task(
        self,
        task_id: str,
        object_id: str,
        object_name: str,
        interval: int,
        command_config: dict,
        modbus_config_file: Optional[str]
    ):
        """Задача сбора данных с Cerbo GX (совместимость с существующим кодом)"""
        from worker.tasks import cerbo_collection_task_worker
        
        logger.debug(f"[{task_id}] Starting CERBO_COLLECTION task for {object_name}")
        
        try:
            # Используем существующую функцию
            await cerbo_collection_task_worker(object_id=object_id, object_name=object_name)
        except asyncio.CancelledError:
            logger.debug(f"[{task_id}] CERBO_COLLECTION task cancelled")
            raise
        except Exception as e:
            logger.error(f"[{task_id}] Error in CERBO_COLLECTION task: {e}", exc_info=True)
    
    async def _run_schedule_check_task(
        self,
        task_id: str,
        object_id: str,
        object_name: str,
        interval: int,
        command_config: dict,
        modbus_config_file: Optional[str]
    ):
        """Задача проверки расписания (совместимость с существующим кодом)"""
        from worker.tasks import energetic_schedule_task_worker
        
        logger.debug(f"[{task_id}] Starting SCHEDULE_CHECK task for {object_name}")
        
        try:
            # Используем существующую функцию
            await energetic_schedule_task_worker(object_id=object_id, object_name=object_name)
        except asyncio.CancelledError:
            logger.debug(f"[{task_id}] SCHEDULE_CHECK task cancelled")
            raise
        except Exception as e:
            logger.error(f"[{task_id}] Error in SCHEDULE_CHECK task: {e}", exc_info=True)
    
    async def _run_modbus_registers_task(
        self,
        task_id: str,
        object_id: str,
        object_name: str,
        interval: int,
        command_config: dict,
        modbus_config_file: Optional[str]
    ):
        """
        Универсальная задача чтения Modbus регистров на основе JSON конфига
        
        command_config format:
        {
            "register_groups": ["battery", "solar"],  # какие группы читать
            "preset": "battery_only"  # или использовать пресет из конфига
        }
        """
        if not modbus_config_file:
            logger.error(f"[{task_id}] No modbus_config_file specified for object {object_name}")
            return
        
        # Загружаем конфиг
        modbus_config = self.load_modbus_config(modbus_config_file)
        if not modbus_config:
            logger.error(f"[{task_id}] Failed to load Modbus config: {modbus_config_file}")
            return
        
        logger.debug(
            f"[{task_id}] Starting MODBUS_REGISTERS task for {object_name} "
            f"with config {modbus_config_file}"
        )
        
        # Определяем какие группы регистров читать
        register_groups = []
        
        if "preset" in command_config:
            preset_name = command_config["preset"]
            preset = modbus_config.get("polling_presets", {}).get(preset_name)
            
            if preset:
                register_groups = preset.get("groups", [])
                # Можно переопределить интервал из пресета
                if "interval_seconds" in preset and interval == 5:  # если дефолтный
                    interval = preset["interval_seconds"]
                logger.debug(f"[{task_id}] Using preset '{preset_name}': {register_groups}")
            else:
                logger.warning(f"[{task_id}] Preset '{preset_name}' not found in config")
        
        if "register_groups" in command_config:
            # Переопределяем/дополняем группы из command_config
            register_groups = command_config["register_groups"]
            logger.debug(f"[{task_id}] Using register_groups from config: {register_groups}")
        
        if modbus_config_file == "deye_inverter.json" and "gen_relay_status" not in register_groups:
            register_groups.append("gen_relay_status")
            logger.debug(f"[{task_id}] Added gen_relay_status to register_groups for generator monitoring")
        
        if not register_groups:
            logger.error(f"[{task_id}] No register groups specified")
            return
        
        # Основной цикл опроса
        from worker.modbus_client import get_or_create_modbus_client, ModbusTCP, DEFAULT_MODBUS_PORT
        from worker.modbus_broker import get_broker, RequestPriority
        
        # Получаем IP-адрес объекта из БД
        async with async_session_maker() as db:
            obj_data = await db.execute(
                select(EnergeticObject).where(EnergeticObject.id == object_id)
            )
            obj = obj_data.scalar_one_or_none()
            if not obj or not obj.ip_address:
                logger.error(f"[{task_id}] IP-адрес объекта {object_id} не найден")
                return
            
            ip_address = obj.ip_address
            port = obj.port
            protocol = obj.protocol or modbus_config.get("protocol", "modbus_tcp")
            slave_id = obj.slave_id if hasattr(obj, 'slave_id') and obj.slave_id else modbus_config.get("slave_id", 1)
        logger.debug(f"[{task_id}] Protocol: {protocol}, IP: {ip_address}, Port: {port}, Slave: {slave_id}")
        
        # Используем брокер
        broker = get_broker()
        
        while True:
            try:
                collected_data = {}
                
                # Читаем каждую группу регистров
                for group_name in register_groups:
                    group = modbus_config["register_groups"].get(group_name)
                    
                    if not group:
                        logger.warning(f"[{task_id}] Register group '{group_name}' not found")
                        continue
                    
                    # logger.debug(f"[{task_id}] Reading group '{group_name}'")
                    
                    # Для modbus_over_tcp (Deye) читаем всю группу за раз
                    if protocol == "modbus_over_tcp":
                        try:
                            start_address = group.get("start_address")
                            count = group.get("count")
                            func_code = group.get("func_code", 3)
                            
                            if start_address is None or count is None:
                                logger.error(f"[{task_id}] Group '{group_name}' missing start_address or count")
                                continue
                            
                            # logger.debug(
                            #     f"[{task_id}] Reading {count} registers from address {start_address} "
                            #     f"(func={func_code})"
                            # )
                            
                            # Используем брокер с приоритетом POLLING
                            result = await broker.submit_request(
                                protocol=protocol,
                                host=ip_address,
                                port=port,
                                operation="read",
                                params={"start": start_address, "count": count, "func_code": func_code},
                                slave_id=slave_id,
                                object_id=object_id,
                                priority=RequestPriority.POLLING,
                                timeout=8.0,
                                request_id=f"polling_{task_id}_{group_name}",
                            )
                            
                            raw_registers = result.get("data", [])
                            # logger.debug(f"[{task_id}] Got {len(raw_registers)} registers: {raw_registers[:5]}...")
                            
                            register_modbus_success(object_id)
                            
                            # Обрабатываем каждый регистр в группе
                            for register in group.get("registers", []):
                                try:
                                    offset = register.get("offset", 0)
                                    reg_type = register.get("type", "uint16")
                                    scale = register.get("scale", 1.0)
                                    name = register["name"]
                                    bit_index = register.get("bit", None)  # Индекс бита для извлечения
                                    
                                    if offset >= len(raw_registers):
                                        logger.warning(f"[{task_id}] Offset {offset} out of range for {name}")
                                        continue
                                    
                                    raw_value = raw_registers[offset]
                                    
                                    # Декодируем значение
                                    if reg_type == "int16":
                                        value = decode_signed_16(raw_value)
                                    elif reg_type == "uint16":
                                        value = raw_value
                                    elif reg_type == "int32" and offset + 1 < len(raw_registers):
                                        value = decode_signed_32(raw_registers[offset], raw_registers[offset + 1])
                                    elif reg_type == "uint32" and offset + 1 < len(raw_registers):
                                        value = (raw_registers[offset] << 16) | raw_registers[offset + 1]
                                    else:
                                        value = raw_value
                                    
                                    # Если нужно извлечь конкретный бит
                                    if bit_index is not None:
                                        logger.debug(f"[{task_id}] Bit extraction for {name}: raw={value}, bit_index={bit_index}, extracted={(int(value) >> bit_index) & 1}")
                                        value = (int(value) >> bit_index) & 1
                                    
                                    # Применяем масштабирование
                                    scaled_value = value * scale
                                    collected_data[name] = scaled_value
                                    
                                    # logger.debug(
                                    #     f"[{task_id}] {name}={scaled_value} (raw={raw_value}, scale={scale}, bit={bit_index})"
                                    # )
                                    
                                except Exception as e:
                                    logger.error(
                                        f"[{task_id}] Error processing register {register.get('name')}: {e}"
                                    )
                            
                        except TimeoutError:
                            logger.warning(f"[{task_id}] Timeout reading group '{group_name}'")
                            register_modbus_error(object_id)
                        except Exception as e:
                            logger.error(
                                f"[{task_id}] Error reading group '{group_name}': {e}"
                            )
                            register_modbus_error(object_id)
                    
                    # Для modbus_tcp (Victron) читаем регистры по отдельности
                    else:
                        for register in group.get("registers", []):
                            try:
                                # Чтение регистра
                                address = register["address"]
                                count = register.get("count", 1)
                                reg_type = register.get("type", "uint16")
                                scale = register.get("scale", 1.0)
                                name = register["name"]
                                bit_index = register.get("bit", None)  # Индекс бита для извлечения
                                
                                # Определяем func_code из типа функции
                                func_code = 4  # input registers по умолчанию
                                if "function" in register:
                                    if register["function"] == "holding":
                                        func_code = 3
                                
                                # Используем брокер с приоритетом POLLING
                                result = await broker.submit_request(
                                    protocol=protocol,
                                    host=ip_address,
                                    port=port,
                                    operation="read",
                                    params={"start": address, "count": count, "func_code": func_code},
                                    slave_id=slave_id,
                                    object_id=object_id,
                                    priority=RequestPriority.POLLING,
                                    timeout=8.0,
                                    request_id=f"polling_{task_id}_{name}",
                                )
                                
                                registers_data = result.get("data", [])
                                
                                register_modbus_success(object_id)
                                
                                # Декодируем значение в зависимости от типа
                                raw_value = registers_data[0] if len(registers_data) > 0 else 0
                                
                                if reg_type == "int16":
                                    value = decode_signed_16(raw_value)
                                elif reg_type == "uint16":
                                    value = raw_value
                                elif reg_type == "int32" and len(registers_data) >= 2:
                                    value = decode_signed_32(registers_data[0], registers_data[1])
                                elif reg_type == "uint32" and len(registers_data) >= 2:
                                    value = (registers_data[0] << 16) | registers_data[1]
                                else:
                                    value = raw_value
                                
                                # Если нужно извлечь конкретный бит
                                if bit_index is not None:
                                    logger.debug(f"[{task_id}] Bit extraction for {name}: raw={value}, bit_index={bit_index}, extracted={(int(value) >> bit_index) & 1}")
                                    value = (int(value) >> bit_index) & 1
                                
                                # Применяем масштабирование
                                scaled_value = value * scale
                                
                                collected_data[name] = scaled_value
                                
                                # logger.debug(
                                #     f"[{task_id}] Read {name}={scaled_value} "
                                #     f"(raw={raw_value}, scale={scale}, bit={bit_index})"
                                # )
                                
                            except TimeoutError:
                                logger.warning(f"[{task_id}] Timeout reading register {register.get('name')}")
                                register_modbus_error(object_id)
                            except Exception as e:
                                logger.error(
                                    f"[{task_id}] Error reading register {register.get('name')}: {e}"
                                )
                                register_modbus_error(object_id)
                
                if collected_data:
                    # Регистрируем успешное чтение
                    register_modbus_success(object_id)
                    
                    # Добавляем метаданные
                    collected_data["measured_at"] = datetime.now()
                    collected_data["object_name"] = object_name
                    collected_data["energetic_object_id"] = object_id
                    
                    # logger.info(
                    #     f"[{task_id}] Collected {len(collected_data)} values from {object_name}"
                    # )
                
                    # Пока просто логируем
                    logger.debug(f"[{task_id}] Data: {collected_data}")
                    
                    # Проверяем gen_relay для уведомлений в Telegram
                    if "gen_relay" in collected_data:
                        try:
                            from worker.telegram_bot import get_telegram_monitor
                            
                            telegram_monitor = get_telegram_monitor()
                            if telegram_monitor:
                                # Получаем telegram_chat_ids из БД
                                async with async_session_maker() as db:
                                    obj_data = await db.execute(
                                        select(EnergeticObject).where(EnergeticObject.id == object_id)
                                    )
                                    obj = obj_data.scalar_one_or_none()
                                    # telegram_chat_ids это строка через запятую - парсим в список
                                    if obj and hasattr(obj, 'telegram_chat_ids') and obj.telegram_chat_ids:
                                        chat_ids = [cid.strip() for cid in str(obj.telegram_chat_ids).split(',') if cid.strip()]
                                    else:
                                        chat_ids = []
                                
                                gen_relay_value = int(collected_data["gen_relay"])
                                await telegram_monitor.check_generator_status(
                                    object_id=object_id,
                                    object_name=object_name,
                                    gen_relay=gen_relay_value,
                                    chat_ids=chat_ids
                                )
                            else:
                                logger.debug(f"[{task_id}] Telegram monitor not available for gen_relay check")
                        except Exception as e:
                            logger.error(f"[{task_id}] Error checking gen_relay for Telegram: {e}")
                else:
                    logger.warning(f"[{task_id}] No data collected from {object_name}")
                
            except asyncio.CancelledError:
                logger.info(f"[{task_id}] MODBUS_REGISTERS task cancelled")
                raise
            except Exception as e:
                logger.error(f"[{task_id}] Error in MODBUS_REGISTERS task: {e}", exc_info=True)
            
            await asyncio.sleep(interval)
    
    async def _run_custom_command_task(
        self,
        task_id: str,
        object_id: str,
        object_name: str,
        interval: int,
        command_config: dict,
        modbus_config_file: Optional[str]
    ):
        """Пользовательская задача (для будущего расширения)"""
        logger.warning(f"[{task_id}] CUSTOM_COMMAND task type not yet implemented")
        
        # Заглушка для будущей реализации
        while True:
            try:
                logger.debug(f"[{task_id}] CUSTOM_COMMAND task tick for {object_name}")
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"[{task_id}] CUSTOM_COMMAND task cancelled")
                raise
    
    async def get_running_tasks_info(self) -> list:
        """Получение информации о запущенных задачах"""
        tasks_info = []
        
        for task_id, task_data in self.tasks.items():
            config = task_data["config"]
            async_task = task_data["task"]
            
            tasks_info.append({
                "task_id": task_id,
                "task_type": config["task_type"],
                "object_id": config["object_id"],
                "object_name": config["object_name"],
                "interval": config["interval"],
                "is_running": not async_task.done(),
                "is_cancelled": async_task.cancelled(),
            })
        
        return tasks_info

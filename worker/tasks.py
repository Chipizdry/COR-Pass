import asyncio
from datetime import datetime, time as dt_time
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from loguru import logger
from cor_pass.database.db import async_session_maker
from cor_pass.schemas import FullDeviceMeasurementCreate
from worker.modbus_client import (
    get_modbus_client_singleton,
    register_modbus_success,
    get_modbus_error_stats
)
from worker.data_collector import (
    collect_battery_data,
    collect_inverter_power_data,
    collect_ess_ac_data,
    get_solarchargers_current_sum,
    get_battery_status,
    send_grid_feed_w_command,
)
from worker.db_operations import create_full_device_measurement, get_all_schedules, update_schedule_is_active_status
from worker.schedule_task import send_dvcc_max_charge_current_command, send_vebus_soc_command
from cor_pass.config.config import settings
from worker.telegram_bot import (
    get_telegram_monitor, 
    send_schedule_change_notification, 
    send_power_loss_notification,
    send_connection_loss_notification,
    update_object_data  
)
from cor_pass.repository.cerbo_service import get_energetic_object



DEFAULT_grid_feed_kw = 70000
DEFAULT_battery_level_percent = 30
DEFAULT_charge_battery_value = 300

COLLECTION_INTERVAL_SECONDS = 2
SCHEDULE_CHECK_INTERVAL_SECONDS = 3

current_active_schedule_id: Optional[str] = None

async def set_inverter_parameters(
    object_id: str,
    grid_feed_w: int,
    battery_level_percent: int,
    charge_battery_value: int
):
    modbus_client_instance = await get_modbus_client_singleton()
    if not modbus_client_instance:
        logger.error(f"[{object_id}] Не удалось получить Modbus клиент для установки параметров инвертора.")
        return

    if settings.app_env == "development":
        logger.info(f"[{object_id}] (DEV) Установка параметров инвертора: grid_feed_w={grid_feed_w}, battery_level_percent={battery_level_percent}, charge_battery_value={charge_battery_value}")
        
        await send_grid_feed_w_command(modbus_client=modbus_client_instance, grid_feed_w=grid_feed_w)
        await send_vebus_soc_command(modbus_client=modbus_client_instance, battery_level_percent=battery_level_percent)
        await send_dvcc_max_charge_current_command(modbus_client=modbus_client_instance, charge_battery_value=charge_battery_value)


async def cerbo_collection_task_worker(object_id: str, object_name: str):

    CONSECUTIVE_ERROR_THRESHOLD = 10  # После 10 последовательных ошибок - уведомление
    
    while True:
        transaction_id = uuid4()
        modbus_client_instance = await get_modbus_client_singleton()

        try:
            if not modbus_client_instance or not modbus_client_instance.connected:
                logger.critical(f"[{object_id}] [{transaction_id}] Modbus client not connected. Skipping cycle.")
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            collected_data = {}

            try:
                collected_data.update(await collect_battery_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await collect_inverter_power_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await collect_ess_ac_data(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await get_solarchargers_current_sum(modbus_client_instance, transaction_id))
            except Exception:
                pass
            try:
                collected_data.update(await get_battery_status(modbus_client_instance, transaction_id))
            except Exception:
                pass

            if not collected_data:
                logger.warning(f"[{object_id}] [{transaction_id}] No data collected. Skipping save.")
                
                # Получаем статистику ошибок из modbus_client
                error_stats = get_modbus_error_stats(object_id)
                consecutive_errors = error_stats['consecutive_errors']
                
                # Проверяем порог последовательных ошибок
                if consecutive_errors == CONSECUTIVE_ERROR_THRESHOLD:
                    if settings.app_env == "development":
                        await send_connection_loss_notification(
                            object_id=object_id,
                            object_name=object_name,
                            is_connection_lost=True,
                            consecutive_errors=consecutive_errors,
                            error_rate_percent=0.0
                        )
                
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            collected_data["measured_at"] = datetime.now()
            collected_data["object_name"] = object_name  # связываем с объектом
            collected_data["energetic_object_id"] = object_id

            required_fields = ["general_battery_power", "inverter_total_ac_output", "ess_total_input_power", "solar_total_pv_power", "measured_at", "object_name", "soc"]
            missing_fields = [f for f in required_fields if f not in collected_data or collected_data[f] is None]
            if missing_fields:
                logger.error(f"[{object_id}] Missing fields: {missing_fields}. Skipping save.", extra={"collected_data": collected_data})
                
                error_stats = get_modbus_error_stats(object_id)
                consecutive_errors = error_stats['consecutive_errors']
                
                if consecutive_errors == CONSECUTIVE_ERROR_THRESHOLD:
                    if settings.app_env == "development":
                        await send_connection_loss_notification(
                            object_id=object_id,
                            object_name=object_name,
                            is_connection_lost=True,
                            consecutive_errors=consecutive_errors,
                            error_rate_percent=0.0
                        )
                
                await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                continue

            register_modbus_success(object_id)
            
            error_stats = get_modbus_error_stats(object_id)
            
            if error_stats['last_error_time'] is not None:
                time_since_error = (datetime.now() - error_stats['last_error_time']).total_seconds()
                if time_since_error < 60: 
                    if settings.app_env == "development":
                        await send_connection_loss_notification(
                            object_id=object_id,
                            object_name=object_name,
                            is_connection_lost=False,
                            consecutive_errors=0,
                            error_rate_percent=0.0
                        )
            
            full_measurement = FullDeviceMeasurementCreate(**collected_data)
            async with async_session_maker() as db:
                await create_full_device_measurement(db=db, data=full_measurement)
            
            # Обновляем данные для команд Telegram бота (только в development)
            if settings.app_env == "development":
                try:
                    update_object_data(object_id, {
                        'object_name': object_name,
                        'soc': collected_data.get("soc", 0),
                        'general_battery_power': collected_data.get("general_battery_power", 0),
                        'battery_voltage': collected_data.get("battery_voltage"),
                        'solar_total_pv_power': collected_data.get("solar_total_pv_power", 0),
                        'inverter_total_ac_output': collected_data.get("inverter_total_ac_output", 0),
                        'ess_total_input_power': collected_data.get("ess_total_input_power", 0),
                    })
                except Exception as e:
                    logger.error(f"[{object_id}] Error updating object data for commands: {e}", exc_info=True)
            
            # Проверяем уровень заряда батареи и отправляем уведомление в Telegram (только в development)
            if settings.app_env == "development":
                try:
                    telegram_monitor = get_telegram_monitor()
                    await telegram_monitor.check_battery_level(
                        object_id=object_id,
                        object_name=object_name,
                        battery_soc=collected_data.get("battery_soc", 0),
                        battery_voltage=collected_data.get("battery_voltage"),
                        battery_power=collected_data.get("general_battery_power")
                    )
                except Exception as e:
                    logger.error(f"[{object_id}] Error checking battery level for Telegram: {e}", exc_info=True)
                
                # Проверяем потерю электроэнергии на входе (только если есть данные ESS)
                if "ess_total_input_power" in collected_data:
                    try:
                        voltage_l1 = collected_data.get("input_voltage_l1", 0)
                        voltage_l2 = collected_data.get("input_voltage_l2", 0)
                        voltage_l3 = collected_data.get("input_voltage_l3", 0)
                        
                        # Пороги для определения потери электроэнергии
                        # Для трехфазной сети нормальное напряжение ~220-240V на фазу
                        VOLTAGE_THRESHOLD = 100.0  # Напряжение меньше 100V считается потерей фазы
                        
                        # Проверяем потерю энергии (хотя бы одна фаза пропала)
                        is_power_lost = (
                            voltage_l1 < VOLTAGE_THRESHOLD or
                            voltage_l2 < VOLTAGE_THRESHOLD or
                            voltage_l3 < VOLTAGE_THRESHOLD
                        )
                        
                        # Логирование для отладки
                        if is_power_lost:
                            logger.warning(
                                f"[{object_id}] Power loss detected: "
                                f"L1={voltage_l1:.1f}V, L2={voltage_l2:.1f}V, L3={voltage_l3:.1f}V"
                            )
                        
                        await send_power_loss_notification(
                            object_id=object_id,
                            object_name=object_name,
                            is_power_lost=is_power_lost,
                            voltage_l1=voltage_l1,
                            voltage_l2=voltage_l2,
                            voltage_l3=voltage_l3,
                        )
                    except Exception as e:
                        logger.error(f"[{object_id}] Error checking power loss for Telegram: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"[{object_id}] Error in collection task: {e}", exc_info=True)
            
            # Получаем статистику ошибок из modbus_client
            error_stats = get_modbus_error_stats(object_id)
            consecutive_errors = error_stats['consecutive_errors']
            
            # Проверяем порог последовательных ошибок
            if consecutive_errors == CONSECUTIVE_ERROR_THRESHOLD:
                if settings.app_env == "development":
                    try:
                        await send_connection_loss_notification(
                            object_id=object_id,
                            object_name=object_name,
                            is_connection_lost=True,
                            consecutive_errors=consecutive_errors,
                            error_rate_percent=0.0
                        )
                    except Exception as notification_error:
                        logger.error(
                            f"[{object_id}] Failed to send connection loss notification: {notification_error}",
                            exc_info=True
                        )

        await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)


async def energetic_schedule_task_worker(object_id: str, object_name: str):
    current_active_schedule_id: str | None = None
    logger.debug(f"[{object_id}] Starting energetic schedule task worker.")
    logger.debug(f"current_active_schedule_id initialized to: {current_active_schedule_id}")

    while True:
        try:
            async with async_session_maker() as db:
                # Получаем объект для доступа к его timezone
                energetic_object = await get_energetic_object(db, object_id)
                if not energetic_object:
                    logger.error(f"[{object_id}] Energetic object not found!")
                    break
                
                # Получаем текущее время в timezone объекта
                object_timezone = ZoneInfo(energetic_object.timezone)
                now_time = datetime.now(object_timezone).time()
                
                all_schedules = await get_all_schedules(db)
                # фильтруем только для этого объекта
                object_schedules = [s for s in all_schedules if s.energetic_object_id == object_id]

                operational_schedules = [s for s in object_schedules if not s.is_manual_mode]
                
                logger.debug(f"[{object_id}] 🔍 Проверка расписаний: найдено {len(object_schedules)} расписаний для объекта, {len(operational_schedules)} операционных, текущее время {now_time} ({energetic_object.timezone}), активное расписание ID: {current_active_schedule_id}")

                active_schedule = None
                for schedule in operational_schedules:
                    if schedule.start_time <= schedule.end_time:
                        if schedule.start_time <= now_time < schedule.end_time:
                            active_schedule = schedule
                            break
                    else:
                        if now_time >= schedule.start_time or now_time < schedule.end_time:
                            active_schedule = schedule
                            break

                if active_schedule:
                    logger.debug(f"[{object_id}] ✅ Найдено активное расписание ID={active_schedule.id}, период {active_schedule.start_time}-{active_schedule.end_time}")
                    
                    if active_schedule.id != current_active_schedule_id:
                        logger.info(f"[{object_id}] 🔄 Переключение расписания: {current_active_schedule_id} → {active_schedule.id}")
                        
                        # Получаем параметры предыдущего расписания для уведомления
                        old_grid_feed_kw = None
                        old_battery_level_percent = None
                        old_charge_battery_value = None
                        
                        if current_active_schedule_id:
                            old_schedule = next((s for s in all_schedules if s.id == current_active_schedule_id), None)
                            if old_schedule:
                                old_grid_feed_kw = old_schedule.grid_feed_w / 1000  # W -> kW
                                old_battery_level_percent = old_schedule.battery_level_percent
                                old_charge_battery_value = old_schedule.charge_battery_value
                        
                        # деактивация предыдущей
                        if current_active_schedule_id:
                            await update_schedule_is_active_status(db, current_active_schedule_id, False)
                        
                        current_active_schedule_id = active_schedule.id
                        
                        # установка параметров инвертора для объекта
                        await set_inverter_parameters(
                            object_id,
                            active_schedule.grid_feed_w,
                            active_schedule.battery_level_percent,
                            active_schedule.charge_battery_value,
                        )
                        await update_schedule_is_active_status(db, active_schedule.id, True)
                        
                        # Отправляем уведомление в Telegram (только в development)
                        if settings.app_env == "development":
                            try:
                                await send_schedule_change_notification(
                                    object_id=object_id,
                                    object_name=object_name,
                                    object_timezone=energetic_object.timezone,
                                    old_grid_feed_kw=old_grid_feed_kw,
                                    old_battery_level_percent=old_battery_level_percent,
                                    old_charge_battery_value=old_charge_battery_value,
                                    new_grid_feed_kw=active_schedule.grid_feed_w / 1000,  # W -> kW
                                    new_battery_level_percent=active_schedule.battery_level_percent,
                                    new_charge_battery_value=active_schedule.charge_battery_value,
                                    is_manual_mode=False,
                                    active_schedule_start_time=active_schedule.start_time,
                                    active_schedule_end_time=active_schedule.end_time
                                )
                            except Exception as e:
                                logger.error(f"[{object_id}] Error sending schedule change notification: {e}", exc_info=True)
                    else:
                        logger.debug(f"[{object_id}] ⏸️ Расписание ID={active_schedule.id} уже активно, параметры не меняем")
                else:
                    logger.debug(f"[{object_id}] ⚠️ Активное расписание не найдено, сбрасываем на дефолт")
                    # сброс к дефолтным параметрам
                    if current_active_schedule_id:
                        logger.info(f"[{object_id}] 🔄 Сброс расписания {current_active_schedule_id} на дефолтные параметры")
                        await update_schedule_is_active_status(db, current_active_schedule_id, False)
                        current_active_schedule_id = None
                        await set_inverter_parameters(object_id, DEFAULT_grid_feed_kw, DEFAULT_battery_level_percent, DEFAULT_charge_battery_value)
                        
                        # Отправляем уведомление о сбросе на дефолт (только в development)
                        if settings.app_env == "development":
                            try:
                                await send_schedule_change_notification(
                                    object_id=object_id,
                                    object_name=object_name,
                                    object_timezone=energetic_object.timezone,
                                    old_grid_feed_kw=None,
                                    old_battery_level_percent=None,
                                    old_charge_battery_value=None,
                                    new_grid_feed_kw=DEFAULT_grid_feed_kw / 1000,  # W -> kW
                                    new_battery_level_percent=DEFAULT_battery_level_percent,
                                    new_charge_battery_value=DEFAULT_charge_battery_value,
                                    is_manual_mode=False
                                )
                            except Exception as e:
                                logger.error(f"[{object_id}] Error sending schedule reset notification: {e}", exc_info=True)
                    # Если current_active_schedule_id уже None, не вызываем set_inverter_parameters повторно

        except Exception as e:
            logger.error(f"[{object_id}] Error in schedule task: {e}", exc_info=True)

        await asyncio.sleep(SCHEDULE_CHECK_INTERVAL_SECONDS)
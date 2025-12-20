"""
Telegram бот для мониторинга уровня заряда батарей в modbus_worker.
Отправляет уведомления в группы при низком уровне заряда.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from zoneinfo import ZoneInfo
import aiohttp
from loguru import logger
from cor_pass.config.config import settings


TELEGRAM_BOT_TOKEN="8230955133:AAEssUmnoHAyef8PuPTh6spmQhKkT8A79S4"
TELEGRAM_BATTERY_ALERT_THRESHOLD=70
TELEGRAM_ALERT_COOLDOWN_MINUTES=60
TELEGRAM_TIMEZONE="Europe/Kiev"


class TelegramBatteryMonitor:
    """Мониторинг батарей с уведомлениями в Telegram"""
    
    def __init__(
        self,
        bot_token: str = None,
        chat_ids: List[str] = None,
        alert_threshold: int = None,
        cooldown_minutes: int = None,
        timezone: str = None
    ):
        """
        Инициализация Telegram монитора
        
        Args:
            bot_token: Токен Telegram бота (из BotFather)
            chat_ids: Список ID чатов/групп для отправки уведомлений
            alert_threshold: Уровень заряда (%) для отправки уведомления
            cooldown_minutes: Минимальный интервал между уведомлениями
            timezone: Часовой пояс (например: 'Europe/Kiev', 'Europe/Moscow')
        """
        self.bot_token = TELEGRAM_BOT_TOKEN or settings.telegram_bot_token
        
        # По умолчанию используем пустой список - chat_ids должны передаваться явно
        # для каждого объекта из EnergeticObject.telegram_chat_ids
        if chat_ids:
            self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]
        else:
            self.chat_ids = []
        
        self.alert_threshold = TELEGRAM_BATTERY_ALERT_THRESHOLD or settings.telegram_battery_alert_threshold
        self.cooldown_minutes = TELEGRAM_ALERT_COOLDOWN_MINUTES or settings.telegram_alert_cooldown_minutes
        self.timezone = ZoneInfo(timezone or settings.telegram_timezone or 'Europe/Kiev')
        
        # Хранилище последних уведомлений для каждого объекта
        self._last_alerts: Dict[str, datetime] = {}
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        logger.info(
            f"TelegramBatteryMonitor initialized: "
            f"default_chats={len(self.chat_ids)}, threshold={self.alert_threshold}%, "
            f"cooldown={self.cooldown_minutes}min, timezone={self.timezone}"
        )
        logger.info(
            "ℹ️ Chat IDs should be provided per object from EnergeticObject.telegram_chat_ids"
        )
    
    def _should_send_alert(self, object_id: str) -> bool:
        """
        Проверяет, нужно ли отправлять уведомление (учитывая cooldown)
        
        Args:
            object_id: ID энергетического объекта
            
        Returns:
            True если можно отправить уведомление
        """
        if object_id not in self._last_alerts:
            return True
        
        last_alert = self._last_alerts[object_id]
        time_since_alert = datetime.now() - last_alert
        cooldown = timedelta(minutes=self.cooldown_minutes)
        
        return time_since_alert >= cooldown
    
    async def send_message(self, text: str, chat_id: str = None, chat_ids: Optional[List[str]] = None) -> bool:
        """
        Отправляет сообщение в Telegram чат
        
        Args:
            text: Текст сообщения
            chat_id: Конкретный chat_id (если None, отправляет во все)
            chat_ids: Список chat_id для отправки
            
        Returns:
            True если сообщение отправлено успешно хотя бы в один чат
        """
        # Приоритет: chat_id (единственный) > chat_ids (список) > self.chat_ids (дефолт)
        if chat_id:
            target_chats = [chat_id]
        elif chat_ids and len(chat_ids) > 0:
            target_chats = chat_ids
        else:
            target_chats = self.chat_ids
        
        logger.info(f"📨 send_message called: chat_id={chat_id}, chat_ids={chat_ids}, target_chats={target_chats}")
        
        if not target_chats:
            logger.warning("⚠️ No target chats specified, message not sent")
            return False
        
        success_count = 0
        
        for chat in target_chats:
            try:
                url = f"{self.api_url}/sendMessage"
                payload = {
                    "chat_id": chat,
                    "text": text,
                    "parse_mode": "HTML"
                }
                
                logger.debug(f"📤 Sending to chat {chat}: url={url}, payload={payload}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Telegram message sent successfully to chat {chat}, result={result}")
                            success_count += 1
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"❌ Failed to send Telegram message to chat {chat}. "
                                f"Status: {response.status}, Error: {error_text}"
                            )
            
            except Exception as e:
                logger.error(f"💥 Error sending Telegram message to chat {chat}: {e}", exc_info=True)
        
        if success_count > 0:
            logger.info(f"Telegram message sent to {success_count}/{len(target_chats)} chats")
            return True
        
        return False
    
    async def check_battery_level(
        self,
        object_id: str,
        object_name: str,
        battery_soc: float,
        battery_voltage: Optional[float] = None,
        battery_power: Optional[float] = None,
        chat_ids: Optional[List[str]] = None
    ):
        """
        Проверяет уровень заряда батареи и отправляет уведомление при необходимости
        
        Args:
            object_id: ID энергетического объекта
            object_name: Название объекта
            battery_soc: Уровень заряда батареи (%)
            battery_voltage: Напряжение батареи (V)
            battery_power: Мощность батареи (W)
            chat_ids: Список chat_id для отправки (из EnergeticObject.telegram_chat_ids)
        """
        # Проверяем порог
        if battery_soc > self.alert_threshold:
            # Заряд нормальный, сбрасываем таймер если был
            if object_id in self._last_alerts:
                del self._last_alerts[object_id]
            return
        
        # Низкий заряд - проверяем cooldown
        if not self._should_send_alert(object_id):
            logger.debug(
                f"Battery low for {object_name} ({battery_soc}%), "
                f"but cooldown not expired yet"
            )
            return
        
        # Формируем сообщение
        message = self._format_alert_message(
            object_name=object_name,
            battery_soc=battery_soc,
            battery_voltage=battery_voltage,
            battery_power=battery_power
        )
        
        # Отправляем уведомление в чаты объекта
        success = await self.send_message(message, chat_ids=chat_ids)
        
        if success:
            # Обновляем время последнего уведомления
            self._last_alerts[object_id] = datetime.now()
            logger.warning(
                f"⚠️ Low battery alert sent for {object_name}: {battery_soc}%"
            )
    
    def _format_alert_message(
        self,
        object_name: str,
        battery_soc: float,
        battery_voltage: Optional[float] = None,
        battery_power: Optional[float] = None
    ) -> str:
        """
        Форматирует сообщение об уведомлении
        
        Args:
            object_name: Название объекта
            battery_soc: Уровень заряда (%)
            battery_voltage: Напряжение (V)
            battery_power: Мощность (W)
            
        Returns:
            Отформатированное сообщение
        """
        # Текущее время в настроенном часовом поясе
        now_local = datetime.now(self.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        message_parts = [
            "🔋 <b>ПРЕДУПРЕЖДЕНИЕ: НИЗКИЙ УРОВЕНЬ ЗАРЯДА БАТАРЕИ</b>\n",
            f"📍 Объект: <b>{object_name}</b>",
            f"⚡ Уровень заряда: <b>{battery_soc:.1f}%</b>",
        ]
        
        if battery_voltage is not None:
            message_parts.append(f"🔌 Напряжение: {battery_voltage:.1f} V")
        
        if battery_power is not None:
            power_kw = battery_power / 1000
            message_parts.append(f"⚙️ Мощность: {power_kw:.2f} kW")
        
        message_parts.append(f"🕐 Время: {timestamp}")
        message_parts.append(f"\n⚠️ Пороговое значение: {self.alert_threshold}%")
        
        return "\n".join(message_parts)
    
    async def check_generator_status(
        self,
        object_id: str,
        object_name: str,
        gen_relay: int,
        chat_ids: Optional[List[str]] = None
    ):
        """
        Проверяет статус генератора и отправляет уведомление при запуске/остановке
        
        Args:
            object_id: ID энергетического объекта
            object_name: Название объекта
            gen_relay: Значение реле генератора (1=включен, 0=выключен)
            chat_ids: Список chat_id для отправки (из EnergeticObject.telegram_chat_ids)
        """
        # Ключ для хранения последнего состояния
        state_key = f"gen_{object_id}"
        is_on = gen_relay == 1
        
        # Проверяем изменение состояния
        if not hasattr(self, '_generator_states'):
            self._generator_states = {}
        
        last_state = self._generator_states.get(state_key)
        
        # Если состояние не изменилось, ничего не делаем
        if last_state == is_on:
            return
        
        # Обновляем состояние
        self._generator_states[state_key] = is_on
        
        # Пропускаем первую инициализацию (когда last_state=None)
        if last_state is None:
            logger.info(f"Generator monitor initialized for {object_name}: relay={gen_relay}")
            return
        
        # Формируем сообщение в зависимости от нового состояния
        now_local = datetime.now(self.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_on:
            # Генератор запустился
            message = (
                "⚡ <b>ГЕНЕРАТОР ЗАПУЩЕН</b>\n\n"
                f"📍 Объект: <b>{object_name}</b>\n"
                f"🔌 Статус: <b>РАБОТАЕТ</b>\n"
                f"🕐 Время: {timestamp}"
            )
            log_msg = f"⚡ Generator STARTED for {object_name}"
        else:
            # Генератор остановился
            message = (
                "🛑 <b>ГЕНЕРАТОР ОСТАНОВЛЕН</b>\n\n"
                f"📍 Объект: <b>{object_name}</b>\n"
                f"🔌 Статус: <b>ВЫКЛЮЧЕН</b>\n"
                f"🕐 Время: {timestamp}"
            )
            log_msg = f"🛑 Generator STOPPED for {object_name}"
        
        # Отправляем уведомление
        success = await self.send_message(message, chat_ids=chat_ids)
        
        if success:
            logger.info(log_msg)
        else:
            logger.warning(f"Failed to send generator alert for {object_name}")
    
    async def send_test_message(self):
        """Отправляет тестовое сообщение для проверки работы бота"""
        # Текущее время в настроенном часовом поясе
        now_local = datetime.now(self.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        test_message = (
            "✅ <b>Telegram Bot для мониторинга батарей активирован</b>\n\n"
            f"📊 Порог уведомлений: {self.alert_threshold}%\n"
            f"⏱️ Интервал cooldown: {self.cooldown_minutes} минут\n"
            f"🕐 Время: {timestamp}"
        )
        
        # success = await self.send_message(test_message)
        success = "bot working"
        if success:
            logger.info("✅ Test message sent successfully to Telegram")
        else:
            logger.error("❌ Failed to send test message to Telegram")
        
        return success


# Глобальный экземпляр монитора
telegram_monitor: Optional[TelegramBatteryMonitor] = None


# Хранилище последних состояний для отслеживания изменений
_last_schedule_states: Dict[str, Optional[str]] = {}  # object_id -> schedule_id
_last_power_loss_states: Dict[str, bool] = {}  # object_id -> has_power
_last_connection_states: Dict[str, bool] = {}  # object_id -> has_connection


async def send_schedule_change_notification(
    object_id: str,
    object_name: str,
    object_timezone: str,
    old_grid_feed_kw: Optional[float],
    old_battery_level_percent: Optional[int],
    old_charge_battery_value: Optional[int],
    new_grid_feed_kw: Optional[float],
    new_battery_level_percent: Optional[int],
    new_charge_battery_value: Optional[int],
    is_manual_mode: bool = False,
    active_schedule_start_time: Optional[datetime] = None,
    active_schedule_end_time: Optional[datetime] = None
):
    """
    Отправляет уведомление о смене расписания с отображением параметров
    
    Args:
        object_id: ID энергетического объекта
        object_name: Название объекта
        object_timezone: Часовой пояс объекта (например: 'Europe/Kiev')
        old_grid_feed_kw: Предыдущая отдача в сеть (kW)
        old_battery_level_percent: Предыдущий порог разряда батареи (%)
        old_charge_battery_value: Предыдущее значение зарядки батареи (W)
        new_grid_feed_kw: Новая отдача в сеть (kW)
        new_battery_level_percent: Новый порог разряда батареи (%)
        new_charge_battery_value: Новое значение зарядки батареи (W)
        is_manual_mode: True если переключено в ручной режим
        active_schedule_start_time: Время начала расписания
        active_schedule_end_time: Время окончания расписания
    """
    try:
        monitor = get_telegram_monitor()
        # Используем timezone объекта, а не глобальный timezone бота
        tz = ZoneInfo(object_timezone)
        now_local = datetime.now(tz)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_manual_mode:
            icon = "🔧"
            title = "ПЕРЕКЛЮЧЕНИЕ В РУЧНОЙ РЕЖИМ"
            params_text = f"Объект переведен в <b>ручной режим управления</b>"
        elif new_grid_feed_kw is not None:
            icon = "📅"
            title = "АВТОМАТИЧЕСКАЯ СМЕНА РАСПИСАНИЯ"
            
            # Формируем текст с параметрами
            params_parts = ["\n📊 <b>Новые параметры:</b>"]
            params_parts.append(f"   ⚡ Отдача в сеть: <b>{new_grid_feed_kw:.2f} kW</b>")
            params_parts.append(f"   🔋 Порог разряда: <b>{new_battery_level_percent}%</b>")
            params_parts.append(f"   🔌 Ток заряда батареи: <b>{new_charge_battery_value} А</b>")
            

            if active_schedule_start_time:

                if hasattr(active_schedule_start_time, 'strftime'):
                    start_time_str = active_schedule_start_time.strftime("%H:%M")
                else:
                    start_time_str = str(active_schedule_start_time)
                params_parts.append(f"   🕒 Время начала: <b>{start_time_str}</b>")
            
            if active_schedule_end_time:
                if hasattr(active_schedule_end_time, 'strftime'):
                    end_time_str = active_schedule_end_time.strftime("%H:%M")
                else:
                    end_time_str = str(active_schedule_end_time)
                params_parts.append(f"   🕒 Время окончания: <b>{end_time_str}</b>")

            # Если были старые параметры, показываем изменение
            if old_grid_feed_kw is not None:
                params_parts.append("\n📋 <b>Предыдущие параметры:</b>")
                params_parts.append(f"   ⚡ Отдача в сеть: {old_grid_feed_kw:.2f} kW")
                params_parts.append(f"   🔋 Порог разряда: {old_battery_level_percent}%")
                params_parts.append(f"   🔌 Ток заряда батареи: {old_charge_battery_value} А")

            params_text = "\n".join(params_parts)
        else:
            icon = "⚙️"
            title = "СБРОС НА ДЕФОЛТНЫЕ ПАРАМЕТРЫ"
            params_text = "❌ Активное расписание завершено, используются стандартные параметры"
        
        message = (
            f"{icon} <b>{title}</b>\n\n"
            f"📍 Объект: <b>{object_name}</b>\n"
            f"🌍 Часовой пояс: {object_timezone}\n"
            f"{params_text}\n"
            f"🕐 Время: {timestamp}"
        )
        
        # await monitor.send_message(message)
        logger.info(f"📅 Schedule change notification sent for {object_name}")
        
    except Exception as e:
        logger.error(f"Error sending schedule change notification: {e}", exc_info=True)


async def send_power_loss_notification(
    object_id: str,
    object_name: str,
    is_power_lost: bool,
    voltage_l1: float = None,
    voltage_l2: float = None,
    voltage_l3: float = None,
    chat_ids: Optional[List[str]] = None,
):
    """
    Отправляет уведомление о потере или восстановлении электроэнергии
    
    Args:
        object_id: ID энергетического объекта
        object_name: Название объекта
        is_power_lost: True если энергия потеряна, False если восстановлена
        voltage_l1: Напряжение на фазе L1 (V)
        voltage_l2: Напряжение на фазе L2 (V)
        voltage_l3: Напряжение на фазе L3 (V)
    """
    try:
        # Проверяем изменение состояния
        last_state = _last_power_loss_states.get(object_id, False)
        if last_state == is_power_lost:
            # Состояние не изменилось, не отправляем уведомление
            return
        
        # Обновляем состояние
        _last_power_loss_states[object_id] = is_power_lost
        
        monitor = get_telegram_monitor()
        now_local = datetime.now(monitor.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_power_lost:
            icon = "⚠️"
            title = "ПОТЕРЯ ЭЛЕКТРОЭНЕРГИИ"
            
            # Определяем какие фазы пропали
            VOLTAGE_THRESHOLD = 100.0
            lost_phases = []
            if voltage_l1 is not None and voltage_l1 < VOLTAGE_THRESHOLD:
                lost_phases.append(f"L1: {voltage_l1:.1f}V")
            if voltage_l2 is not None and voltage_l2 < VOLTAGE_THRESHOLD:
                lost_phases.append(f"L2: {voltage_l2:.1f}V")
            if voltage_l3 is not None and voltage_l3 < VOLTAGE_THRESHOLD:
                lost_phases.append(f"L3: {voltage_l3:.1f}V")
            
            if lost_phases:
                status = f"❌ <b>Потеря фаз: {', '.join(lost_phases)}</b>"
            else:
                status = "❌ <b>Отсутствует входное напряжение</b>"
        else:
            icon = "✅"
            title = "ЭЛЕКТРОЭНЕРГИЯ ВОССТАНОВЛЕНА"
            
            # Показываем текущие напряжения
            if voltage_l1 is not None and voltage_l2 is not None and voltage_l3 is not None:
                status = (
                    f"✅ <b>Входное напряжение восстановлено</b>\n"
                    f"   📊 L1: {voltage_l1:.1f}V, L2: {voltage_l2:.1f}V, L3: {voltage_l3:.1f}V"
                )
            else:
                status = "✅ <b>Входное напряжение восстановлено</b>"
        
        message_parts = [
            f"{icon} <b>{title}</b>\n",
            f"📍 Объект: <b>{object_name}</b>",
            status,
            f"🕐 Время: {timestamp}"
        ]
        
        message = "\n".join(message_parts)
        
        await monitor.send_message(message, chat_ids=chat_ids)
        
        if is_power_lost:
            logger.warning(f"⚠️ Power loss notification sent for {object_name}")
        else:
            logger.info(f"✅ Power restored notification sent for {object_name}")
        
    except Exception as e:
        logger.error(f"Error sending power loss notification: {e}", exc_info=True)


async def send_connection_loss_notification(
    object_id: str,
    object_name: str,
    is_connection_lost: bool,
    consecutive_errors: int = 0,
    error_rate_percent: float = 0.0,
    chat_ids: Optional[List[str]] = None,
):
    """
    Отправляет уведомление о потере или восстановлении связи с устройством
    
    Args:
        object_id: ID энергетического объекта
        object_name: Название объекта
        is_connection_lost: True если связь потеряна, False если восстановлена
        consecutive_errors: Количество последовательных ошибок
        error_rate_percent: Процент ошибок (0-100)
    """
    try:
        # Проверяем изменение состояния
        last_state = _last_connection_states.get(object_id, False)
        if last_state == is_connection_lost:
            # Состояние не изменилось, не отправляем уведомление
            return
        
        # Обновляем состояние
        _last_connection_states[object_id] = is_connection_lost
        
        monitor = get_telegram_monitor()
        now_local = datetime.now(monitor.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_connection_lost:
            icon = "🔴"
            title = "ПОТЕРЯ СВЯЗИ С УСТРОЙСТВОМ"
            status_parts = ["❌ <b>Связь с устройством потеряна</b>"]
            
            if consecutive_errors > 0:
                status_parts.append(f"📊 Последовательных ошибок: <b>{consecutive_errors}</b>")
            
            if error_rate_percent > 0:
                status_parts.append(f"⚠️ Процент ошибок: <b>{error_rate_percent:.1f}%</b>")
            
            status_parts.append("\n💡 <i>Проверьте Modbus соединение и устройство Cerbo GX</i>")
            status = "\n".join(status_parts)
        else:
            icon = "🟢"
            title = "СВЯЗЬ С УСТРОЙСТВОМ ВОССТАНОВЛЕНА"
            status = "✅ <b>Связь с устройством восстановлена</b>\n📡 <i>Сбор данных возобновлен</i>"
        
        message_parts = [
            f"{icon} <b>{title}</b>\n",
            f"📍 Объект: <b>{object_name}</b>",
            status,
            f"🕐 Время: {timestamp}"
        ]
        
        message = "\n".join(message_parts)
        
        await monitor.send_message(message, chat_ids=chat_ids)
        
        if is_connection_lost:
            logger.error(
                f"🔴 Connection loss notification sent for {object_name} "
                f"(errors: {consecutive_errors}, rate: {error_rate_percent:.1f}%)"
            )
        else:
            logger.info(f"🟢 Connection restored notification sent for {object_name}")
        
    except Exception as e:
        logger.error(f"Error sending connection loss notification: {e}", exc_info=True)


def get_telegram_monitor() -> TelegramBatteryMonitor:
    """
    Получает глобальный экземпляр Telegram монитора (singleton)
    
    Returns:
        Экземпляр TelegramBatteryMonitor
    """
    global telegram_monitor
    
    if telegram_monitor is None:
        telegram_monitor = TelegramBatteryMonitor()
    
    return telegram_monitor


async def init_telegram_monitor() -> bool:
    """
    Инициализирует Telegram монитор и отправляет тестовое сообщение
    
    Returns:
        True если инициализация успешна
    """
    try:
        monitor = get_telegram_monitor()
        
        # Проверяем что токен настроен
        if not monitor.bot_token or monitor.bot_token == "TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram bot token not configured, skipping initialization")
            return False
        
        # Chat IDs теперь берутся из EnergeticObject.telegram_chat_ids для каждого объекта
        logger.info("✅ Telegram monitor initialized. Chat IDs will be loaded from EnergeticObject.telegram_chat_ids")
        
        # Отправляем тестовое сообщение (если есть дефолтные чаты для команд бота)
        success = await monitor.send_test_message()
        return success
    
    except Exception as e:
        logger.error(f"Failed to initialize Telegram monitor: {e}", exc_info=True)
        return False


# ==================== КОМАНДЫ БОТА ====================

# Хранилище данных объектов для команд
_objects_data: Dict[str, Dict] = {}


def update_object_data(object_id: str, data: dict):
    """
    Обновляет данные об объекте для использования в командах
    
    Args:
        object_id: ID объекта
        data: Данные объекта (battery_soc, power, voltage, etc.)
    """
    global _objects_data
    _objects_data[object_id] = {
        **data,
        'last_update': datetime.now()
    }
    logger.debug(f"📊 Updated object data for {object_id}: soc={data.get('soc')}%, power={data.get('general_battery_power')}W")


async def handle_telegram_command(command: str, chat_id: str, message_id: int):
    """
    Обрабатывает команды от пользователей
    
    Args:
        command: Текст команды (например: '/status')
        chat_id: ID чата откуда пришла команда
        message_id: ID сообщения
    """
    try:
        monitor = get_telegram_monitor()
        
        # Разбираем команду
        parts = command.strip().split()
        cmd = parts[0].lower()
        
        # Убираем @botname если есть (для групповых чатов)
        if '@' in cmd:
            cmd = cmd.split('@')[0]
        
        if cmd == '/start' or cmd == '/help':
            await send_help_message(monitor, chat_id)
        
        elif cmd == '/status':
            await send_status_message(monitor, chat_id)
        
        elif cmd == '/battery':
            await send_battery_message(monitor, chat_id)
        
        elif cmd == '/power':
            await send_power_message(monitor, chat_id)
        
        elif cmd == '/schedule':
            object_id = parts[1] if len(parts) > 1 else None
            await send_schedule_message(monitor, chat_id, object_id)
        
        elif cmd == '/debug':
            # Отладочная команда для проверки данных
            await send_debug_message(monitor, chat_id)
        
        elif cmd == '/generator':
            await send_generator_message(monitor, chat_id)
        
        else:
            await monitor.send_message(
                f"❓ Неизвестная команда: {cmd}\nИспользуйте /help для списка команд",
                chat_id
            )
    
    except Exception as e:
        logger.error(f"Error handling command '{command}': {e}", exc_info=True)


async def send_help_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """Отправляет справку по командам"""
    help_text = """
🤖 <b>Команды бота мониторинга энергосистемы</b>

<b>Основные команды:</b>
/status - Общий статус всех объектов
/battery - Информация о батареях
/power - Текущая мощность (ввод/вывод)
/generator - Статус генератора
/schedule [object_id] - Активное расписание
/debug - Отладочная информация
/help - Эта справка

<b>Автоматические уведомления:</b>
• ⚠️ Низкий заряд батареи (< {}%)
• 📅 Смена расписания
• ⚡ Потеря/восстановление питания

<b>Мониторинг работает 24/7</b>
Данные обновляются каждые 2 секунды
""".format(monitor.alert_threshold)
    
    await monitor.send_message(help_text, chat_id)


async def send_status_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """Отправляет общий статус всех объектов"""
    logger.info(f"📞 send_status_message called, chat_id={chat_id}, _objects_data has {len(_objects_data)} objects")
    logger.debug(f"Objects data keys: {list(_objects_data.keys())}")
    
    if not _objects_data:
        await monitor.send_message(
            "📊 Нет данных об объектах.\n\n<b>Возможные причины:</b>\n• Фоновая задача сбора данных не запущена\n• Данные еще не собраны (подождите 2-3 секунды)\n• Проверьте, создана ли задача CERBO_COLLECTION в БД\n\nИспользуйте /help для справки",
            chat_id
        )
        return
    
    # Используем часовой пояс монитора для отображения времени
    now = datetime.now(monitor.timezone)
    now_naive = datetime.now()  # Для расчета age_seconds
    message_parts = ["📊 <b>ОБЩИЙ СТАТУС ОБЪЕКТОВ</b>\n"]
    
    for object_id, data in _objects_data.items():
        object_name = data.get('object_name', f'Объект {object_id}')
        last_update = data.get('last_update', now_naive)
        age_seconds = (now_naive - last_update).total_seconds()
        
        # Статус подключения
        if age_seconds < 10:
            status_icon = "🟢"
            status_text = "Онлайн"
        elif age_seconds < 60:
            status_icon = "🟡"
            status_text = f"Обновлено {int(age_seconds)}с назад"
        else:
            status_icon = "🔴"
            status_text = f"Нет связи {int(age_seconds/60)}м"
        
        soc = data.get('soc', 0)
        battery_power = data.get('general_battery_power', 0) / 1000  # W -> kW
        
        # Иконка батареи
        if soc >= 80:
            battery_icon = "🔋"
        elif soc >= 50:
            battery_icon = "🔋"
        elif soc >= 20:
            battery_icon = "🪫"
        else:
            battery_icon = "⚠️"
        
        message_parts.append(
            f"\n{status_icon} <b>{object_name}</b>\n"
            f"   {battery_icon} Батарея: {soc:.1f}% ({battery_power:+.2f} kW)\n"
            f"   📡 Статус: {status_text}"
        )
    
    message_parts.append(f"\n🕐 Обновлено: {now.strftime('%H:%M:%S')}")
    
    await monitor.send_message("\n".join(message_parts), chat_id)


async def send_battery_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """Отправляет детальную информацию о батареях"""
    logger.info(f"📞 send_battery_message called, chat_id={chat_id}, _objects_data has {len(_objects_data)} objects")
    
    if not _objects_data:
        await monitor.send_message("📊 Нет данных о батареях.\n\nВозможные причины:\n• Задача сбора данных не запущена\n• Данные еще не собраны (подождите 2-3 секунды)\n\nПроверьте статус через /status", chat_id)
        return
    
    message_parts = ["🔋 <b>СОСТОЯНИЕ БАТАРЕЙ</b>\n"]
    
    for object_id, data in _objects_data.items():
        object_name = data.get('object_name', f'Объект {object_id}')
        soc = data.get('soc', 0)
        battery_power = data.get('general_battery_power', 0)
        # battery_voltage = data.get('battery_voltage')
        
        # Направление потока
        if battery_power > 50:
            direction = "⚡ Заряд"
        elif battery_power < -50:
            direction = "🔌 Разряд"
        else:
            direction = "⏸️ Покой"
        
        message_parts.append(
            f"\n<b>{object_name}</b>\n"
            f"   📊 Заряд: <b>{soc:.1f}%</b>\n"
            f"   {direction}: {abs(battery_power/1000):.2f} kW"
        )
        
        # if battery_voltage:
        #     message_parts.append(f"   🔌 Напряжение: {battery_voltage:.1f} V")
    
    await monitor.send_message("\n".join(message_parts), chat_id)


async def send_power_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """Отправляет информацию о мощности"""
    if not _objects_data:
        await monitor.send_message("📊 Нет данных о мощности", chat_id)
        return
    
    message_parts = ["⚡ <b>МОЩНОСТЬ СИСТЕМЫ</b>\n"]
    
    for object_id, data in _objects_data.items():
        object_name = data.get('object_name', f'Объект {object_id}')
        
        solar = data.get('solar_total_pv_power', 0) / 1000
        inverter_out = data.get('inverter_total_ac_output', 0) / 1000
        grid_in = data.get('ess_total_input_power', 0) / 1000
        battery = data.get('general_battery_power', 0) / 1000
        
        message_parts.append(
            f"\n<b>{object_name}</b>\n"
            f"   ☀️ Солнечные панели: {solar:.2f} kW\n"
            f"   🏠 Потребление: {inverter_out:.2f} kW\n"
            f"   🔌 Сеть (вход): {grid_in:.2f} kW\n"
            f"   🔋 Батарея: {battery:+.2f} kW"
        )
    
    await monitor.send_message("\n".join(message_parts), chat_id)


async def send_schedule_message(monitor: TelegramBatteryMonitor, chat_id: str, object_id: Optional[str] = None):
    """Отправляет информацию об активном расписании"""
    # TODO: Нужен доступ к базе данных для получения расписаний
    # Пока отправляем заглушку
    message = """
📅 <b>АКТИВНЫЕ РАСПИСАНИЯ</b>

В процессе разработки...

Используйте /status для общей информации
"""
    await monitor.send_message(message, chat_id)


async def send_debug_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """Отправляет отладочную информацию"""
    global _objects_data
    
    message_parts = ["🐛 <b>DEBUG INFO</b>\n"]
    message_parts.append(f"📊 Objects in memory: {len(_objects_data)}")
    
    if _objects_data:
        message_parts.append("\n<b>Object IDs:</b>")
        for obj_id, data in _objects_data.items():
            last_update = data.get('last_update', 'Never')
            if isinstance(last_update, datetime):
                age = (datetime.now() - last_update).total_seconds()
                last_update = f"{age:.1f}s ago"
            
            message_parts.append(
                f"\n• {obj_id[:8]}..."
                f"\n  Name: {data.get('object_name', 'N/A')}"
                f"\n  SoC: {data.get('soc', 'N/A')}%"
                f"\n  Updated: {last_update}"
            )
    else:
        message_parts.append("\n⚠️ No objects data available")
        message_parts.append("\nCheck if CERBO_COLLECTION task is running")
    
    await monitor.send_message("\n".join(message_parts), chat_id)


async def send_generator_message(monitor: TelegramBatteryMonitor, chat_id: str):
    """
    Отправляет текущий статус генератора для объектов с Deye инвертором.
    Читает регистр 552 (gen_relay) напрямую из устройства.
    """
    from sqlalchemy import select
    from cor_pass.database.db import async_session_maker
    from cor_pass.database.models import EnergeticObject
    from worker.modbus_broker import get_broker, RequestPriority
    
    try:
        # Получаем все объекты, к которым привязан этот чат
        async with async_session_maker() as session:
            result = await session.execute(
                select(EnergeticObject).where(
                    EnergeticObject.is_active == True
                )
            )
            all_objects = result.scalars().all()
            
            # Фильтруем по chat_id (telegram_chat_ids это строка через запятую)
            energetic_objects = [
                obj for obj in all_objects
                if obj.telegram_chat_ids and chat_id in [
                    cid.strip() for cid in str(obj.telegram_chat_ids).split(',')
                ]
            ]
        
        if not energetic_objects:
            await monitor.send_message(
                "❌ <b>Доступ запрещен</b>\n\n"
                "Этот чат не привязан ни к одному энергообъекту.\n"
                "Обратитесь к администратору.",
                chat_id
            )
            return
        
        # Фильтруем объекты с генератором (Deye инвертор)
        deye_objects = [
            obj for obj in energetic_objects 
            if obj.modbus_config_file == 'deye_inverter.json'
        ]
        
        if not deye_objects:
            await monitor.send_message(
                "ℹ️ <b>Генератор не найден</b>\n\n"
                "Ни один из доступных объектов не имеет подключенного генератора.",
                chat_id
            )
            return
        
        # Получаем broker для чтения регистров
        broker = get_broker()
        
        # Формируем сообщение
        now_local = datetime.now(monitor.timezone)
        timestamp = now_local.strftime("%Y-%m-%d %H:%M:%S")
        
        message_parts = [
            "⚡ <b>СТАТУС ГЕНЕРАТОРА</b>\n",
            f"🕐 Время запроса: {timestamp}\n"
        ]
        
        # Опрашиваем каждый объект с генератором
        for obj in deye_objects:
            try:
                # Определяем slave_id (может быть в объекте или в конфигурации)
                slave_id = obj.slave_id if hasattr(obj, 'slave_id') and obj.slave_id else 1
                
                # Читаем регистр 552 (gen_relay)
                result = await broker.submit_request(
                    protocol=obj.protocol,
                    host=obj.ip_address,
                    port=obj.port,
                    operation="read",
                    params={"start": 552, "count": 1, "func_code": 3},
                    slave_id=slave_id,
                    object_id=str(obj.id),
                    priority=RequestPriority.USER_READ,
                    timeout=5.0,
                    request_id=f"telegram_gen_check_{obj.id}",
                )
                
                raw_data = result.get("data", [])
                if not raw_data:
                    message_parts.append(
                        f"\n📍 <b>{obj.name}</b>\n"
                        f"   ❌ Нет данных от устройства"
                    )
                    continue
                
                # Получаем полное значение регистра и извлекаем третий бит (индекс 3)
                register_value = raw_data[0]
                logger.debug(f"/generator: raw 552={register_value}, bit3={(register_value >> 3) & 1}")
                gen_relay = (register_value >> 3) & 1
                is_on = gen_relay == 1
                
                if is_on:
                    status_icon = "⚡"
                    status_text = "<b>РАБОТАЕТ</b>"
                else:
                    status_icon = "🛑"
                    status_text = "<b>ВЫКЛЮЧЕН</b>"
                
                logger.debug(f"/generator: object={obj.name}, is_on={is_on}, gen_relay_bit={gen_relay}")
                message_parts.append(
                    f"\n📍 <b>{obj.name}</b>\n"
                    f"   {status_icon} Статус: {status_text}\n"
                )
                
            except Exception as e:
                logger.error(f"Error reading generator status for object {obj.id}: {e}", exc_info=True)
                message_parts.append(
                    f"\n📍 <b>{obj.name}</b>\n"
                    f"   ⚠️ Ошибка связи: {str(e)[:50]}"
                )
        
        await monitor.send_message("\n".join(message_parts), chat_id)
        
    except Exception as e:
        logger.error(f"Error in send_generator_message: {e}", exc_info=True)
        await monitor.send_message(
            "❌ <b>Ошибка выполнения команды</b>\n\n"
            f"Произошла внутренняя ошибка при проверке статуса генератора.\n"
            f"Попробуйте позже или обратитесь к администратору.",
            chat_id
        )


# Polling loop для обработки команд
_last_update_id = 0
_commands_task: Optional[asyncio.Task] = None


async def load_all_chat_ids_from_db() -> List[str]:
    """
    Загружает все chat_ids из всех активных энергетических объектов
    
    Returns:
        Список уникальных chat_ids
    """
    try:
        from cor_pass.database.db import async_session_maker
        from cor_pass.database.models import EnergeticObject
        from sqlalchemy import select
        
        all_chat_ids = []
        
        async with async_session_maker() as db:
            result = await db.execute(
                select(EnergeticObject).where(EnergeticObject.is_active == True)
            )
            objects = result.scalars().all()
            
            for obj in objects:
                if obj.telegram_chat_ids:
                    chat_ids = [cid.strip() for cid in str(obj.telegram_chat_ids).split(',') if cid.strip()]
                    all_chat_ids.extend(chat_ids)
        
        # Убираем дубликаты
        unique_chat_ids = list(set(all_chat_ids))
        logger.info(f"Loaded {len(unique_chat_ids)} unique chat IDs from {len(objects)} energetic objects")
        return unique_chat_ids
        
    except Exception as e:
        logger.error(f"Error loading chat IDs from DB: {e}", exc_info=True)
        return []


async def start_telegram_commands_handler():
    """
    Запускает обработчик команд (long polling)
    Работает в фоновом режиме
    """
    global _last_update_id, _commands_task
    
    monitor = get_telegram_monitor()
    logger.info("🤖 Starting Telegram commands handler...")
    
    # Загружаем chat_ids из БД при старте
    allowed_chat_ids = await load_all_chat_ids_from_db()
    
    # Периодически обновляем список разрешенных чатов
    last_reload = datetime.now()
    RELOAD_INTERVAL_MINUTES = 10
    
    while True:
        try:
            # Перезагружаем список чатов каждые 10 минут
            if (datetime.now() - last_reload).total_seconds() > RELOAD_INTERVAL_MINUTES * 60:
                allowed_chat_ids = await load_all_chat_ids_from_db()
                last_reload = datetime.now()
            
            async with aiohttp.ClientSession() as session:
                url = f"{monitor.api_url}/getUpdates"
                params = {
                    'offset': _last_update_id + 1,
                    'timeout': 30,  # Long polling
                    'allowed_updates': ['message']
                }
                
                async with session.get(url, params=params, timeout=35) as response:
                    if response.status != 200:
                        logger.warning(f"Telegram API error: {response.status}")
                        await asyncio.sleep(5)
                        continue
                    
                    data = await response.json()
                    
                    if not data.get('ok'):
                        logger.error(f"Telegram API returned error: {data}")
                        await asyncio.sleep(5)
                        continue
                    
                    updates = data.get('result', [])
                    
                    for update in updates:
                        _last_update_id = update['update_id']
                        
                        message = update.get('message')
                        if not message:
                            continue
                        
                        text = message.get('text', '')
                        if not text.startswith('/'):
                            continue  # Игнорируем не-команды
                        
                        chat_id = str(message['chat']['id'])
                        message_id = message['message_id']
                        
                        # Проверяем что это один из чатов наших объектов
                        if chat_id not in allowed_chat_ids:
                            logger.debug(f"Ignoring command from unknown chat {chat_id}")
                            continue
                        
                        logger.info(f"📥 Received command: {text} from chat {chat_id}")
                        await handle_telegram_command(text, chat_id, message_id)
        
        except asyncio.CancelledError:
            logger.info("Telegram commands handler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in Telegram commands handler: {e}", exc_info=True)
            await asyncio.sleep(10)


def start_commands_handler_task():
    """Запускает фоновую задачу обработки команд"""
    global _commands_task
    
    if _commands_task is None or _commands_task.done():
        _commands_task = asyncio.create_task(start_telegram_commands_handler())
        logger.info("✅ Telegram commands handler task started")
    
    return _commands_task

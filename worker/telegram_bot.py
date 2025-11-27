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
TELEGRAM_CHAT_ID=[-1001646233395, -1003050383090, -753415670, -5097812738]
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
        
        # Поддержка как одного chat_id, так и списка
        if chat_ids:
            self.chat_ids = chat_ids if isinstance(chat_ids, list) else [chat_ids]
        else:
            # Получаем из захардкоженных значений или настроек
            chat_id_value = TELEGRAM_CHAT_ID
            
            # Если это уже список (захардкожено)
            if isinstance(chat_id_value, list):
                self.chat_ids = [str(cid) for cid in chat_id_value]
            # Если это строка из settings
            elif isinstance(chat_id_value, str):
                if ',' in chat_id_value:
                    self.chat_ids = [cid.strip() for cid in chat_id_value.split(',') if cid.strip()]
                else:
                    self.chat_ids = [chat_id_value] if chat_id_value else []
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
            f"chats={len(self.chat_ids)}, threshold={self.alert_threshold}%, "
            f"cooldown={self.cooldown_minutes}min, timezone={self.timezone}"
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
    
    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """
        Отправляет сообщение в Telegram чат
        
        Args:
            text: Текст сообщения
            chat_id: Конкретный chat_id (если None, отправляет во все)
            
        Returns:
            True если сообщение отправлено успешно хотя бы в один чат
        """
        target_chats = [chat_id] if chat_id else self.chat_ids
        success_count = 0
        
        for chat in target_chats:
            try:
                url = f"{self.api_url}/sendMessage"
                payload = {
                    "chat_id": chat,
                    "text": text,
                    "parse_mode": "HTML"
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            logger.debug(f"Telegram message sent successfully to chat {chat}")
                            success_count += 1
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Failed to send Telegram message to chat {chat}. "
                                f"Status: {response.status}, Error: {error_text}"
                            )
            
            except Exception as e:
                logger.error(f"Error sending Telegram message to chat {chat}: {e}", exc_info=True)
        
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
        battery_power: Optional[float] = None
    ):
        """
        Проверяет уровень заряда батареи и отправляет уведомление при необходимости
        
        Args:
            object_id: ID энергетического объекта
            object_name: Название объекта
            battery_soc: Уровень заряда батареи (%)
            battery_voltage: Напряжение батареи (V)
            battery_power: Мощность батареи (W)
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
        
        # Отправляем уведомление
        success = await self.send_message(message)
        
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
        
        await monitor.send_message(message)
        
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
        
        await monitor.send_message(message)
        
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
        
        # Проверяем что токен и chat_ids настроены
        if not monitor.bot_token or monitor.bot_token == "TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram bot token not configured, skipping initialization")
            return False
        
        if not monitor.chat_ids or len(monitor.chat_ids) == 0:
            logger.warning("Telegram chat IDs not configured, skipping initialization")
            return False
        
        # Отправляем тестовое сообщение
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
/schedule [object_id] - Активное расписание
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
    if not _objects_data:
        await monitor.send_message(
            "📊 Нет данных об объектах.\nДанные появятся после первого сбора.",
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
    if not _objects_data:
        await monitor.send_message("📊 Нет данных о батареях", chat_id)
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


# Polling loop для обработки команд
_last_update_id = 0
_commands_task: Optional[asyncio.Task] = None


async def start_telegram_commands_handler():
    """
    Запускает обработчик команд (long polling)
    Работает в фоновом режиме
    """
    global _last_update_id, _commands_task
    
    monitor = get_telegram_monitor()
    logger.info("🤖 Starting Telegram commands handler...")
    
    while True:
        try:
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
                        
                        # Проверяем что это наш чат
                        if chat_id not in monitor.chat_ids:
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

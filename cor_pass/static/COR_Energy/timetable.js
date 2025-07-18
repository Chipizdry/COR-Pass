
function getShiftedTime(h, m, shiftHours) {
    const date = new Date();
    date.setUTCHours(h);
    date.setUTCMinutes(m);
    date.setUTCSeconds(0);
    date.setUTCMilliseconds(0);
    date.setUTCHours(date.getUTCHours() + shiftHours);
    return {
        hours: date.getUTCHours(),
        minutes: date.getUTCMinutes(),
    };
}

function formatIsoTimeWithShift(h, m) {
    const shifted = getShiftedTime(h, m, -3);
    return `${String(shifted.hours).padStart(2, '0')}:${String(shifted.minutes).padStart(2, '0')}:00.000Z`;
}


function initScheduleTable() {
    fetchAllSchedulePeriods().then(() => {
        renderScheduleTable();
    });
}

// Отрисовка таблицы расписания
function renderScheduleTable() {
    const tbody = document.getElementById('scheduleTableBody');
    tbody.innerHTML = '';
    
    schedulePeriods.sort((a, b) => {
        if (a.startHour === b.startHour) {
            return a.startMinute - b.startMinute;
        }
        return a.startHour - b.startHour;
    });
    
    schedulePeriods.forEach((period, index) => {
        const row = document.createElement('tr');
        row.dataset.periodId = period.id;
        
        const endTime = calculateEndTime(
            period.startHour, 
            period.startMinute, 
            period.durationHour, 
            period.durationMinute
        );
        
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>
                <input type="number" class="time-input" min="0" max="23" value="${period.startHour}" 
                    onchange="updateSchedulePeriod('${period.id}', 'startHour', this.value)"> :
                <input type="number" class="time-input" min="0" max="59" value="${period.startMinute}" 
                    onchange="updateSchedulePeriod('${period.id}', 'startMinute', this.value)">
            </td>
            <td>
                <input type="number" class="time-input" min="0" max="23" value="${period.durationHour}" 
                    onchange="updateSchedulePeriod('${period.id}', 'durationHour', this.value)"> ч
                <input type="number" class="time-input" min="0" max="59" value="${period.durationMinute}" 
                    onchange="updateSchedulePeriod('${period.id}', 'durationMinute', this.value)"> м
            </td>
            <td>${endTime.hour}:${endTime.minute.toString().padStart(2, '0')}</td>
            <td>
                    <input type="number" class="integer-input" min="-100000" max="100000" step="10" value="${period.feedIn}" 
                     onchange="updateSchedulePeriod('${period.id}', 'feedIn', this.value)">
            </td>
            <td>
                <input type="number" class="integer-input" min="0" max="100" value="${period.batteryLevel}" 
                    onchange="updateSchedulePeriod('${period.id}', 'batteryLevel', this.value)">
            </td>
            <td>
                <input type="number" class="integer-input" min="0" max="32767" value="${period.chargeEnabled}" 
                    onchange="updateSchedulePeriod('${period.id}', 'chargeEnabled', this.value)">
            </td>
            <td>
                <select class="toggle-active" name="active" onchange="updateSchedulePeriod('${period.id}', 'active', this.value)">
                    <option value="true" ${period.active ? 'selected' : ''}>Вкл</option>
                    <option value="false" ${!period.active ? 'selected' : ''}>Выкл</option>
                </select>
            </td>
            <td>
                <button onclick="saveSchedulePeriod(this)" class="action-btn save-btn" title="Сохранить">💾</button>
                <button onclick="deleteSchedulePeriod(this)" class="action-btn delete-btn" title="Удалить">❌</button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    document.getElementById('toggleScheduleBtn').textContent = 
        scheduleEnabled ? 'Авто' : 'Ручной';
    renderTimeline(); 
}

// Расчет времени окончания периода
function calculateEndTime(startHour, startMinute, durationHour, durationMinute) {
    let endHour = startHour + durationHour;
    let endMinute = startMinute + durationMinute;
    
    if (endMinute >= 60) {
        endHour += Math.floor(endMinute / 60);
        endMinute = endMinute % 60;
    }
    
    endHour = endHour % 24;
    
    return {
        hour: endHour,
        minute: endMinute
    };
}


// Добавление нового периода
async function addSchedulePeriod() {
    if (schedulePeriods.length >= 10) {
        alert('Максимальное количество периодов - 10');
        return;
    }

    // Собираем занятые интервалы (в минутах)
    const occupied = Array(1440).fill(false);
    schedulePeriods.forEach(p => {
        let start = p.startHour * 60 + p.startMinute;
        let duration = p.durationHour * 60 + p.durationMinute;
        for (let i = 0; i < duration; i++) {
            occupied[(start + i) % 1440] = true; // учитывать переход за полночь
        }
    });

    // Ищем первый свободный 60-минутный интервал
    let found = false;
    let nextStartHour = 0;
    for (let hour = 0; hour < 24; hour++) {
        const start = hour * 60;
        let free = true;
        for (let i = 0; i < 60; i++) {
            if (occupied[(start + i) % 1440]) {
                free = false;
                break;
            }
        }
        if (free) {
            nextStartHour = hour;
            found = true;
            break;
        }
    }

    if (!found) {
        alert('Нет свободного одностороннего часового интервала для добавления нового периода.');
        return;
    }

    const start_time = `${String(nextStartHour).padStart(2, '0')}:00:00`;

    const scheduleData = {
        start_time: start_time,
        duration_hours: 1,
        duration_minutes: 0,
        grid_feed_w: 0,
        battery_level_percent: 50,
        charge_battery_value: 500,
        is_manual_mode: false
    };

    try {
        const response = await fetch('/api/modbus/schedules/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(scheduleData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
        }

        const newSchedule = await response.json();

        const startTime = new Date(`1970-01-01T${newSchedule.start_time}`);
        const startHour = startTime.getHours();
        const startMinute = startTime.getMinutes();

        let durationHour = 0;
        let durationMinute = 0;
        if (newSchedule.duration) {
            const durationRegex = /PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/;
            const matches = newSchedule.duration.match(durationRegex);
            if (matches) {
                durationHour = matches[1] ? parseInt(matches[1]) : 0;
                durationMinute = matches[2] ? parseInt(matches[2]) : 0;
            }
        }

        const newPeriod = {
            id: newSchedule.id,
            startHour,
            startMinute,
            durationHour,
            durationMinute,
            feedIn: newSchedule.grid_feed_w || 0,
            batteryLevel: newSchedule.battery_level_percent || 0,
            chargeEnabled: newSchedule.charge_battery_value || 500,
            active: newSchedule.is_manual_mode,
            isManualMode: newSchedule.is_manual_mode
        };

        schedulePeriods.push(newPeriod);
        renderScheduleTable();
        showNotification('Новый период успешно создан', 'success');

    } catch (error) {
        console.error('Ошибка при создании периода:', error);
        showNotification(error.message || 'Ошибка при создании периода', 'error');
    }
}


// Обновление параметров периода
function updateSchedulePeriod(id, field, value) {
    const period = schedulePeriods.find(p => p.id === id);
    if (!period) return;
    
    // Преобразуем значение в нужный тип
    let convertedValue;
    
    // Для полей типа boolean (select)
    if (field === 'chargeEnabled' || field === 'active') {
        convertedValue = value === 'true' || value === true;
    } 
    // Для числовых полей
    else {
        convertedValue = Number(value);
        
        // Валидация значений
        if (field === 'startHour' && (convertedValue < 0 || convertedValue > 23)) return;
        if ((field === 'startMinute' || field === 'durationMinute') && (convertedValue < 0 || convertedValue > 59)) return;
        if (field === 'durationHour' && convertedValue < 0) return;
        if (field === 'batteryLevel' && (convertedValue < 0 || convertedValue > 100)) return;
        if (field === 'chargeEnabled' && (convertedValue < 0 || convertedValue > 32767)) return;
    }
    
    period[field] = convertedValue;
}

function formatIsoTime(h, m) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00.000Z`;
}

// Сохранение периода (отправка на сервер)
async function saveSchedulePeriod(buttonElement) {
    const row = buttonElement.closest('tr');
    const id = row.dataset.periodId;

    const startHour = parseInt(row.querySelector('input[onchange*="startHour"]').value);
    const startMinute = parseInt(row.querySelector('input[onchange*="startMinute"]').value);
    const durationHour = parseInt(row.querySelector('input[onchange*="durationHour"]').value);
    const durationMinute = parseInt(row.querySelector('input[onchange*="durationMinute"]').value);
    const feedIn = parseFloat(row.querySelector('input[onchange*="feedIn"]').value);
    const batteryLevel = parseInt(row.querySelector('input[onchange*="batteryLevel"]').value);
    const chargeEnabled = parseInt(row.querySelector('input[onchange*="chargeEnabled"]').value);
    const active = row.querySelector('select[name="active"]').value === 'true';
    const isManualMode = active; 

   // const formattedStartTime = formatIsoTime(startHour, startMinute); // "08:00:00.000Z"
    const formattedStartTime = formatIsoTimeWithShift(startHour, startMinute); 
    const dataToSend = {
        start_time: formattedStartTime,
        duration_hours: durationHour,
        duration_minutes: durationMinute,
        grid_feed_w: feedIn,
        battery_level_percent: batteryLevel,
        charge_battery_value: chargeEnabled,
        is_manual_mode: isManualMode
    };

    console.log("Отправляем данные:", dataToSend);

    try {
        const response = await fetch(`/api/modbus/schedules/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(dataToSend)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ Успешно сохранено:', data);

        const periodIndex = schedulePeriods.findIndex(p => p.id.toString() === id);
        if (periodIndex !== -1) {
            schedulePeriods[periodIndex] = {
                ...schedulePeriods[periodIndex],
                startHour,
                startMinute,
                durationHour,
                durationMinute,
                feedIn,
                batteryLevel,
                chargeEnabled,
                active
            };
        }

        renderScheduleTable();
        showNotification('Период успешно сохранен', 'success');

    } catch (error) {
        console.error('❌ Ошибка сохранения:', error);
        showNotification(error.message || 'Ошибка при сохранении периода', 'error');
    }
}

// Удаление периода
async function deleteSchedulePeriod(buttonElement) {
    // Получаем ID периода из атрибута data-id кнопки
    const row = buttonElement.closest('tr');
    const id = row.dataset.periodId;
    
    if (!confirm('Вы уверены, что хотите удалить этот период?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/modbus/schedules/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
        }
        
        // Удаляем период из локального массива
        schedulePeriods = schedulePeriods.filter(p => p.id.toString() !== id);
        
        renderScheduleTable();
        showNotification('Период успешно удален', 'success');
    } catch (error) {
        console.error('Ошибка при удалении:', error);
        showNotification(error.message || 'Ошибка при удалении периода', 'error');
    }
}

// Включение/отключение всего расписания
async function toggleSchedule() {
    scheduleEnabled = !scheduleEnabled;

    const updatePromises = schedulePeriods.map(async period => {
        const dataToSend = {
         //   start_time: formatIsoTime(period.startHour, period.startMinute),
            start_time: formatIsoTimeWithShift(period.startHour, period.startMinute),
            duration_hours: period.durationHour,
            duration_minutes: period.durationMinute,
            grid_feed_w: period.feedIn,
            battery_level_percent: period.batteryLevel,
            charge_battery_value: period.chargeEnabled,
            is_manual_mode: scheduleEnabled // 👈 массово устанавливаем
        };

        try {
            const response = await fetch(`/api/modbus/schedules/${period.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataToSend)
            });

            if (!response.ok) {
                const err = await response.json().catch(() => null);
                throw new Error(err?.message || `HTTP ${response.status}`);
            }

            // Обновим в локальном массиве
            period.active = scheduleEnabled;
        } catch (error) {
            console.error(`Ошибка обновления периода ${period.id}:`, error);
        }
    });

    await Promise.all(updatePromises);
    
    renderScheduleTable();
    showNotification(
        scheduleEnabled ? 'Авто режим активирован' : 'Ручное управление',
        'success'
    );
}


// Инициализация таблицы при загрузке страницы
document.addEventListener('DOMContentLoaded', initScheduleTable);


function renderTimeline() {
    const container = document.getElementById('timelinePeriods');
    const hoursContainer = document.getElementById('timelineHours');
    
    // Очищаем контейнеры
    container.innerHTML = '';
    hoursContainer.innerHTML = '';
    
    // Добавляем часы (00:00 - 23:00)
    for (let i = 0; i < 24; i++) {
        const hourElem = document.createElement('div');
        hourElem.className = 'timeline-hour';
        hourElem.textContent = `${i.toString().padStart(2, '0')}:00`;
        hoursContainer.appendChild(hourElem);
    }
    
    // Определяем общее количество периодов для расчета шага высоты
    const activePeriodsCount = schedulePeriods.filter(p => p.active).length;
    const heightStep = activePeriodsCount > 0 ? 100 / (activePeriodsCount + 1) : 0;
    
    // Добавляем периоды
    let periodIndex = 0;
    schedulePeriods.forEach((period, index) => {
        if (!period.active) return;
    
        const startMinutes = period.startHour * 60 + period.startMinute;
        const durationMinutes = period.durationHour * 60 + period.durationMinute;
        const endMinutes = startMinutes + durationMinutes;
    
        const bottomPosition = 5 + (periodIndex * heightStep);
    
        const addPeriodBlock = (start, width, label) => {
            const periodElem = document.createElement('div');
            periodElem.className = 'timeline-period';
            periodElem.style.left = `${(start / 1440) * 100}%`;
            periodElem.style.width = `${(width / 1440) * 100}%`;
            periodElem.style.backgroundColor = periodColors[index % periodColors.length];
            periodElem.style.height = `8px`;
            periodElem.style.bottom = `${bottomPosition}%`;
    
            periodElem.setAttribute('data-tooltip', label);
    
            periodElem.addEventListener('click', () => {
                const rows = document.querySelectorAll('#scheduleTableBody tr');
                if (rows[index]) {
                    rows[index].style.backgroundColor = '#ffff99';
                    setTimeout(() => {
                        rows[index].style.backgroundColor = '';
                    }, 2500);
                    rows[index].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
    
            container.appendChild(periodElem);
        };
    
        // Текст подсказки
        const label = `Период ${index + 1}\n` +
            `Начало: ${period.startHour}:${period.startMinute.toString().padStart(2, '0')}\n` +
            `Длительность: ${period.durationHour}ч ${period.durationMinute}м\n` +
            `Мощность: ${period.feedIn} кВт\n` +
            `Заряд: ${period.chargeEnabled}`;
    
        if (endMinutes <= 1440) {
            // Не пересекает полночь
            addPeriodBlock(startMinutes, durationMinutes, label);
        } else {
            // Пересекает полночь — нужно разделить
            const untilMidnight = 1440 - startMinutes;
            const afterMidnight = endMinutes - 1440;
    
            // Часть до 00:00
            addPeriodBlock(startMinutes, untilMidnight, label);
    
            // Часть после 00:00
            addPeriodBlock(0, afterMidnight, label);
        }
    
        periodIndex++;
    });
}


// Функция для показа уведомлений
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 500);
    }, 3000);
}

async function fetchAllSchedulePeriods() {
    try {
        const response = await fetch('/api/modbus/schedules/', {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const periods = await response.json();

        // Преобразуем полученные данные в формат, используемый на фронтенде
        const formattedPeriods = periods.map(period => {
            const startTime = new Date(`1970-01-01T${period.start_time}`);
            let startHour = startTime.getHours();
            let startMinute = startTime.getMinutes();

            // сдвигаем +3 ЧАСА сразу после получения, локально используем уже сдвинутое
            ({ hours: startHour, minutes: startMinute } = getShiftedTime(startHour, startMinute, 3));


            let durationHour = 0;
            let durationMinute = 0;
            if (period.duration) {
                const durationRegex = /PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/;
                const matches = period.duration.match(durationRegex);
                if (matches) {
                    durationHour = matches[1] ? parseInt(matches[1]) : 0;
                    durationMinute = matches[2] ? parseInt(matches[2]) : 0;
                }
            }

            return {
                id: period.id,
                startHour,
                startMinute,
                durationHour,
                durationMinute,
                feedIn: period.grid_feed_w,
                batteryLevel: period.battery_level_percent,
                chargeEnabled:period.charge_battery_value,
                active: period.is_manual_mode
            };
        });

        // ✅ Сортировка по времени старта (раньше — выше)
        formattedPeriods.sort((a, b) => {
            const timeA = a.startHour * 60 + a.startMinute;
            const timeB = b.startHour * 60 + b.startMinute;
            return timeA - timeB;
        });

        schedulePeriods = formattedPeriods;

        renderScheduleTable();
        renderTimeline();

        return formattedPeriods;

    } catch (error) {
        console.error('Ошибка при загрузке периодов:', error);
        showNotification('Ошибка при загрузке расписания', 'error');
        return [];
    }
}

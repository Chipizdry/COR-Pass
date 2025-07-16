


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
                    onchange="updateSchedulePeriod(${period.id}, 'startHour', this.value)"> :
                <input type="number" class="time-input" min="0" max="59" value="${period.startMinute}" 
                    onchange="updateSchedulePeriod(${period.id}, 'startMinute', this.value)">
            </td>
            <td>
                <input type="number" class="time-input" min="0" max="23" value="${period.durationHour}" 
                    onchange="updateSchedulePeriod(${period.id}, 'durationHour', this.value)"> ч
                <input type="number" class="time-input" min="0" max="59" value="${period.durationMinute}" 
                    onchange="updateSchedulePeriod(${period.id}, 'durationMinute', this.value)"> м
            </td>
            <td>${endTime.hour}:${endTime.minute.toString().padStart(2, '0')}</td>
            <td>
                <input type="number" class="integer-input" min="0" max="100" step="0.1" value="${period.feedIn}" 
                    onchange="updateSchedulePeriod(${period.id}, 'feedIn', this.value)">
            </td>
            <td>
                <input type="number" class="integer-input" min="0" max="100" value="${period.batteryLevel}" 
                    onchange="updateSchedulePeriod(${period.id}, 'batteryLevel', this.value)">
            </td>
            <td>
                <select class="toggle-active" name="chargeEnabled" onchange="updateSchedulePeriod('${period.id}', 'chargeEnabled', this.value)">
                    <option value="true" ${period.chargeEnabled ? 'selected' : ''}>Вкл</option>
                    <option value="false" ${!period.chargeEnabled ? 'selected' : ''}>Выкл</option>
                </select>
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
        scheduleEnabled ? 'Ручной' : 'Авто';
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

    // Подготовка данных для отправки на бэкенд
    const scheduleData = {
        start_time: "00:00:00", // формат без миллисекунд — сервер добавит сам
        duration_hours: 1,
        duration_minutes: 0,
        grid_feed_w: 0,
        battery_level_percent: 50,
        charge_battery: true,
        is_manual_mode: false // 👈 контролирует поле "Активен"
    };

    try {
        const response = await fetch('/api/modbus/schedules/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(scheduleData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
        }

        const newSchedule = await response.json();

        // Разбор start_time (например "01:00:00.000Z")
        const startTime = new Date(`1970-01-01T${newSchedule.start_time}`);
        const startHour = startTime.getHours();
        const startMinute = startTime.getMinutes();

        // Разбор длительности в формате "PT1H30M"
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

        // Добавляем период с учетом того, что active = is_manual_mode
        const newPeriod = {
            id: newSchedule.id,
            startHour,
            startMinute,
            durationHour,
            durationMinute,
            feedIn: newSchedule.grid_feed_w || 0,
            batteryLevel: newSchedule.battery_level_percent || 0,
            chargeEnabled: newSchedule.charge_battery,
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
        if (field === 'startHour' && (convertedValue < 0 || convertedValue > 23)) {
            return;
        }
        if ((field === 'startMinute' || field === 'durationMinute') && 
            (convertedValue < 0 || convertedValue > 59)) {
            return;
        }
        if (field === 'durationHour' && convertedValue < 0) {
            return;
        }
        if (field === 'batteryLevel' && (convertedValue < 0 || convertedValue > 100)) {
            return;
        }
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
    const chargeEnabled = row.querySelector('select[name="chargeEnabled"]').value === 'true';
    const active = row.querySelector('select[name="active"]').value === 'true';
    const isManualMode = active; 

    const formattedStartTime = formatIsoTime(startHour, startMinute); // "08:00:00.000Z"

    const dataToSend = {
        start_time: formattedStartTime,
        duration_hours: durationHour,
        duration_minutes: durationMinute,
        grid_feed_w: feedIn,
        battery_level_percent: batteryLevel,
        charge_battery: chargeEnabled,
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
function toggleSchedule() {
    scheduleEnabled = !scheduleEnabled;
    renderScheduleTable();
    
    // Здесь может быть вызов API для сохранения состояния
    console.log('Расписание', scheduleEnabled ? 'включено' : 'отключено');
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
        const endMinutes = startMinutes + period.durationHour * 60 + period.durationMinute;
        
        const periodElem = document.createElement('div');
        periodElem.className = 'timeline-period';
        periodElem.title = `Период ${index + 1}: ${period.startHour}:${period.startMinute.toString().padStart(2, '0')} - ${calculateEndTime(period.startHour, period.startMinute, period.durationHour, period.durationMinute).hour}:${calculateEndTime(period.startHour, period.startMinute, period.durationHour, period.durationMinute).minute.toString().padStart(2, '0')}`;
        
        // Позиционирование и размер
        periodElem.style.left = `${(startMinutes / 1440) * 100}%`;
        periodElem.style.width = `${((endMinutes - startMinutes) / 1440) * 100}%`;
        periodElem.style.backgroundColor = periodColors[index % periodColors.length];
        
        // Фиксированная высота и позиционирование по вертикали
        const fixedHeight = 8; // Фиксированная высота в пикселях
        periodElem.style.height = `${fixedHeight}px`;
        
        // Расположение от низа в зависимости от порядкового номера
        const bottomPosition = 5 + (periodIndex * heightStep);
        periodElem.style.bottom = `${bottomPosition}%`;
        periodElem.setAttribute('data-tooltip', 
            `Период ${index + 1}\n` +
            `Начало: ${period.startHour}:${period.startMinute.toString().padStart(2, '0')}\n` +
            `Длительность: ${period.durationHour}ч ${period.durationMinute}м\n` +
            `Мощность: ${period.feedIn} кВт\n` +
            `Заряд: ${period.chargeEnabled ? 'Вкл' : 'Выкл'}`
        );
        // Клик по периоду прокручивает к соответствующей строке в таблице
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
            // Парсим время начала
            const startTime = new Date(`1970-01-01T${period.start_time}`);
            const startHour = startTime.getHours();
            const startMinute = startTime.getMinutes();
            
            // Парсим длительность (ISO 8601 формат, например "PT1H30M")
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
                startHour: startHour,
                startMinute: startMinute,
                durationHour: durationHour,
                durationMinute: durationMinute,
                feedIn: period.grid_feed_w,
                batteryLevel: period.battery_level_percent,
                chargeEnabled: period.charge_battery,
                active: period.is_manual_mode
                
            };
        });
        
        // Обновляем глобальный массив периодов
        schedulePeriods = formattedPeriods;
        
        // Перерисовываем таблицу и временную шкалу
        renderScheduleTable();
        renderTimeline();
        
        return formattedPeriods;
        
    } catch (error) {
        console.error('Ошибка при загрузке периодов:', error);
        showNotification('Ошибка при загрузке расписания', 'error');
        return [];
    }
}



function initScheduleTable() {
    renderScheduleTable();
}

// Отрисовка таблицы расписания
function renderScheduleTable() {
    const tbody = document.getElementById('scheduleTableBody');
    tbody.innerHTML = '';
    
    // Сортируем периоды по времени начала
    schedulePeriods.sort((a, b) => {
        if (a.startHour === b.startHour) {
            return a.startMinute - b.startMinute;
        }
        return a.startHour - b.startHour;
    });
    
    schedulePeriods.forEach((period, index) => {
        const row = document.createElement('tr');
        
        // Рассчитываем время окончания
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
                <input type="number" class="kw-input" min="0" max="100" step="0.1" value="${period.feedIn}" 
                    onchange="updateSchedulePeriod(${period.id}, 'feedIn', this.value)">
            </td>
            <td>
                <input type="number" class="percent-input" min="0" max="100" value="${period.batteryLevel}" 
                    onchange="updateSchedulePeriod(${period.id}, 'batteryLevel', this.value)">
            </td>
            <td>
                <select class="toggle-active" onchange="updateSchedulePeriod(${period.id}, 'chargeEnabled', this.value === 'true')">
                    <option value="true" ${period.chargeEnabled ? 'selected' : ''}>Вкл</option>
                    <option value="false" ${!period.chargeEnabled ? 'selected' : ''}>Выкл</option>
                </select>
            </td>
            <td>
                <select class="toggle-active" onchange="updateSchedulePeriod(${period.id}, 'active', this.value === 'true')">
                    <option value="true" ${period.active ? 'selected' : ''}>Вкл</option>
                    <option value="false" ${!period.active ? 'selected' : ''}>Выкл</option>
                </select>
            </td>
            <td>
                <button onclick="saveSchedulePeriod(${period.id})" class="action-btn save-btn" title="Сохранить">💾</button>
                <button onclick="deleteSchedulePeriod(${period.id})" class="action-btn delete-btn" title="Удалить">❌</button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    // Обновляем состояние кнопки включения/отключения расписания
    document.getElementById('toggleScheduleBtn').textContent = 
        scheduleEnabled ? 'Отключить расписание' : 'Включить расписание';
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
function addSchedulePeriod() {
    if (schedulePeriods.length >= 10) {
        alert('Максимальное количество периодов - 10');
        return;
    }
    
    // Находим максимальный ID
    const maxId = schedulePeriods.reduce((max, period) => Math.max(max, period.id), 0);
    
    // Добавляем новый период с дефолтными значениями
    const newPeriod = {
        id: maxId + 1,
        startHour: 0,
        startMinute: 0,
        durationHour: 1,
        durationMinute: 0,
        feedIn: 0,
        batteryLevel: 50,
        chargeEnabled: true,
        active: true
    };
    
    schedulePeriods.push(newPeriod);
    renderScheduleTable();
}

// Обновление параметров периода
function updateSchedulePeriod(id, field, value) {
    const period = schedulePeriods.find(p => p.id === id);
    if (!period) return;
    
    // Преобразуем значение в нужный тип
    let convertedValue;
    if (field === 'chargeEnabled' || field === 'active') {
        convertedValue = value === 'true';
    } else {
        convertedValue = Number(value);
    }
    
    // Валидация значений
    if (field === 'startHour' && (convertedValue < 0 || convertedValue > 23)) {
        return;
    }
    if ((field === 'startMinute' || field === 'durationMinute') && (convertedValue < 0 || convertedValue > 59)) {
        return;
    }
    if (field === 'durationHour' && convertedValue < 0) {
        return;
    }
    if (field === 'batteryLevel' && (convertedValue < 0 || convertedValue > 100)) {
        return;
    }
    
    period[field] = convertedValue;
}

// Сохранение периода (отправка на сервер)
function saveSchedulePeriod(id) {
    const period = schedulePeriods.find(p => p.id === id);
    if (!period) return;
    
    // Здесь должна быть логика отправки данных на сервер
    console.log('Сохранение периода:', period);
    
    // После успешного сохранения можно обновить таблицу
    renderScheduleTable();
    alert('Период сохранен успешно!');
}

// Удаление периода
function deleteSchedulePeriod(id) {
    if (!confirm('Вы уверены, что хотите удалить этот период?')) {
        return;
    }
    
    schedulePeriods = schedulePeriods.filter(p => p.id !== id);
    renderScheduleTable();
    
    // Здесь может быть вызов API для удаления на сервере
    console.log('Период удален:', id);
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



    
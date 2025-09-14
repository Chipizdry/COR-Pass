





// Функция для сохранения настроек графика в localStorage
function saveChartSettings() {
    const chartType = currentChartType;
    const currentRangeType = document.getElementById('timeRangeSelect').value;

    const settings = {
        chartType,
        currentRangeType
    };

    if (currentRangeType === "custom") {
        settings.customStartDate = document.getElementById("startDate").value;
        settings.customEndDate = document.getElementById("endDate").value;
    } else {
        if (chartType === "line") {
            settings.lineTimeRange = currentRangeType;
        } else if (chartType === "bar") {
            settings.barTimeRange = currentRangeType;
        }
    }

    localStorage.setItem("chartSettings", JSON.stringify(settings));
}




// Функция для загрузки настроек графика из localStorage
function loadChartSettings() {
    const savedSettings = localStorage.getItem('chartSettings');
    if (savedSettings) {
        try {
            const settings = JSON.parse(savedSettings);
            console.log('Chart settings loaded:', settings);
            
            // Восстанавливаем тип графика
            if (settings.chartType && ['line', 'bar'].includes(settings.chartType)) {
                currentChartType = settings.chartType;
                document.getElementById('chartTypeSelect').value = currentChartType;
            }
            
            // Восстанавливаем временной диапазон
            if (settings. LineTimeRange) {
                document.getElementById('timeRangeSelect').value = settings. LineTimeRange;
            }
            
            // Восстанавливаем диапазон для столбчатого графика
            if (settings.BarTimeRange) {
                currentBarTimeRange = settings.BarTimeRange;
            }
            
            return settings;
        } catch (e) {
            console.error('Error parsing chart settings:', e);
            return null;
        }
    }
    return null;
}



function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}




// Унифицированный форматтер для дат/времени
function formatDateLabel(dateStr, startDate, endDate, chartType = 'line') {
    const date = new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z')); // приводим к UTC, если без Z
    const totalDurationMs = endDate - startDate;
    const totalHours = totalDurationMs / (1000 * 60 * 60);

    if (chartType === 'line') {
        // для линейных графиков
        if (totalHours <= 24) {
            // в пределах суток — время
            return date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                timeZone: 'Europe/Moscow'
            });
        } else {
            // больше суток — дата + время
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Europe/Moscow'
            });
        }
    }

    if (chartType === 'bar') {
        if (totalHours <= 48) {
            // до 2 суток → часы
            return date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Europe/Moscow'
            });
        } else if (totalHours <= 24 * 31) {
            // до месяца → день.месяц
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                timeZone: 'Europe/Moscow'
            });
        } else {
            // больше месяца → месяц.год
            return date.toLocaleDateString('ru-RU', {
                month: '2-digit',
                year: 'numeric',
                timeZone: 'Europe/Moscow'
            });
        }
    }

    return date.toISOString();
}



// Функции для управления индикатором загрузки
function showChartLoading() {
    document.getElementById('chartLoadingOverlay').style.display = 'flex';
}

function hideChartLoading() {
    document.getElementById('chartLoadingOverlay').style.display = 'none';
}
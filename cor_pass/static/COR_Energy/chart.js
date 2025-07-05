

async function fetchMeasurements(page = 1) {
    try {
        isLoading = true;
        document.getElementById('loadingIndicator').style.display = 'inline';
        
        const response = await fetch(`/api/modbus/measurements/?page=${page}&page_size=100`);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        
        isLoading = false;
        document.getElementById('loadingIndicator').style.display = 'none';
        
        return data.items || [];
    } catch (error) {
        console.error('Error fetching measurements:', error);
        isLoading = false;
        document.getElementById('loadingIndicator').style.display = 'none';
        return [];
    }
}


   // Функция для загрузки и отображения конкретной страницы
async function loadAndDisplayPage(page) {
    if (isLoading || currentPage === page) return;
    
    currentPage = page;
    document.getElementById('currentPageDisplay').textContent = `Текущая страница: ${currentPage}`;
    
    const newMeasurements = await fetchMeasurements(page);
    if (newMeasurements.length > 0) {
        allMeasurements[currentPage - 1] = newMeasurements;
        updateChartData();
    }
}


// Инициализация ползунка
function initPageSlider() {
    const slider = document.getElementById('pageSlider');
    
    slider.addEventListener('input', function() {
        isSliderMoving = true;
    });
    
    slider.addEventListener('change', async function() {
        const page = parseInt(this.value);
        await loadAndDisplayPage(page);
        isSliderMoving = false;
    });
}


// Функция для обработки данных измерений
function processMeasurementsData(measurements) {
    if (!measurements) return { labels: [], loadPower: [], solarPower: [], batteryPower: [], essTotalInputPower: [] };
    
    const sortedMeasurements = [...measurements].sort((a, b) => 
        new Date(a.measured_at) - new Date(b.measured_at));
    
    const labels = [];
    const loadPower = [];
    const solarPower = [];
    const batteryPower = [];
    const essTotalInputPower = [];
    
    sortedMeasurements.forEach(measurement => {
        // Предполагаем, что сервер присылает время в UTC
        const date = new Date(measurement.measured_at + 'Z'); // UTC время

        const timeStr = date.toLocaleTimeString('ru-RU', { 
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Europe/Moscow' // Пусть браузер сам корректирует
        });

        labels.push(timeStr);
        
        loadPower.push(Math.round(measurement.inverter_total_ac_output / 10) / 100);
        solarPower.push(Math.round(measurement.solar_total_pv_power / 10) / 100);
        batteryPower.push(Math.round(measurement.general_battery_power / 10) / 100);
        essTotalInputPower.push(Math.round(measurement.ess_total_input_power / 10) / 100);
    });

    return { labels, loadPower, solarPower, batteryPower, essTotalInputPower };
}



// Функция для инициализации графика
function initPowerChart() {
    const ctx = document.getElementById('powerChart').getContext('2d');
    
    if (powerChart) {
        powerChart.destroy();
    }
    
    powerChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Мощность нагрузки (кВт)',
                    data: [],
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Солнечная генерация (кВт)',
                    data: [],
                    borderColor: 'rgba(255, 159, 64, 1)',
                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Мощность батареи (кВт)',
                    data: [],
                    borderColor: 'rgba(153, 102, 255, 1)',
                    backgroundColor: 'rgba(153, 102, 255, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Общая входная мощность ESS (кВт)',
                    data: [],
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Время'
                    },
                    grid: {
                        display: false
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Мощность (кВт)'
                    },
                    min: -20,
                    max: 20,
                    ticks: {
                        stepSize: 5
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw.toFixed(2)} кВт`;
                        }
                    }
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            }
        }
    });
}

// Функция для обновления данных графика
function updateChartData() {
    if (!allMeasurements[currentPage - 1]) return;
    
    const { labels, loadPower, solarPower, batteryPower, essTotalInputPower } = 
        processMeasurementsData(allMeasurements[currentPage - 1]);
    
    if (!powerChart) return;
    
    powerChart.data.labels = labels;
    powerChart.data.datasets[0].data = loadPower;
    powerChart.data.datasets[1].data = solarPower;
    powerChart.data.datasets[2].data = batteryPower;
    powerChart.data.datasets[3].data = essTotalInputPower;

     // Автоматически подстраиваем масштаб по Y
     const allData = [...loadPower, ...solarPower, ...batteryPower, ...essTotalInputPower];
     const maxPower = Math.max(...allData);
     const minPower = Math.min(...allData);
     
     powerChart.options.scales.y.max = Math.ceil(maxPower / 10) * 10 + 5;
     powerChart.options.scales.y.min = Math.floor(minPower / 10) * 10 - 5;
    
    powerChart.update();
}


// Основная функция запуска
async function startChartUpdates() {
    initPowerChart();
    initPageSlider();
    
    // Инициализируем массив для хранения всех страниц
    allMeasurements = new Array(60);
    
    // Первоначальная загрузка первой страницы
    await loadAndDisplayPage(1);
    
    // Периодическое обновление только первой страницы
    chartUpdateInterval = setInterval(async () => {
        if (!isSliderMoving) {
            const newMeasurements = await fetchMeasurements(1);
            if (newMeasurements.length > 0) {
                allMeasurements[0] = newMeasurements;
                if (currentPage === 1) {
                    updateChartData();
                }
            }
        }
    }, 1000);
}



function stopChartUpdates() {
    if (chartUpdateInterval) {
        clearInterval(chartUpdateInterval);
        chartUpdateInterval = null;
    }
    if (powerChart) {
        powerChart.destroy();
        powerChart = null;
    }
}

// Останавливаем обновления при закрытии вкладки
window.addEventListener('beforeunload', () => {
    stopChartUpdates();
});

// Запускаем при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    startChartUpdates();
});
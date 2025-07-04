






async function fetchMeasurements() {
    try {
        const response = await fetch('/api/modbus/measurements/?page=1&page_size=60');
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        return data.items;
    } catch (error) {
        console.error('Error fetching measurements:', error);
        return [];
    }
}


// Функция для обработки данных измерений и подготовки для графика
function processMeasurementsData(measurements) {
    const sortedMeasurements = [...measurements].sort((a, b) => 
        new Date(a.measured_at) - new Date(b.measured_at));
    
    const labels = [];
    const loadPower = [];
    const solarPower = [];
    const batteryPower = [];
    const essTotalInputPower = []; 
    
    sortedMeasurements.forEach(measurement => {
        labels.push(new Date(measurement.measured_at).toLocaleTimeString());
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
    
    // Если график уже существует, сначала уничтожаем его
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
                    min: -120,
                    max: 120,
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
async function updateChartData() {
    try {
        // Получаем свежие данные
        const measurements = await fetchMeasurements();
        console.log('Fetched measurements:', measurements);
        // Если данных нет, ничего не делаем
        if (!measurements || measurements.length === 0) return;
        
        // Обрабатываем данные
        const { labels, loadPower, solarPower, batteryPower, essTotalInputPower } = processMeasurementsData(measurements);

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
    } catch (error) {
        console.error('Error updating chart:', error);
    }
}


function startChartUpdates() {
    // Инициализируем график
    initPowerChart();
    
    // Первое обновление данных
    updateChartData();
    
    // Устанавливаем интервал обновления (например, каждые 5 секунд)
    chartUpdateInterval = setInterval(updateChartData, 1000);
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



// Добавляем элемент для выбора количества страниц
function initPagesPerScreenControl() {
    // Проверяем, не добавлен ли уже элемент
    if (document.getElementById('pagesPerScreenSelect')) return;
    
    const control = document.createElement('div');
    control.className = 'pages-control';
    control.innerHTML = `
        <label>Страниц на экран:</label>
        <select id="pagesPerScreenSelect">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
        </select>
    `;
    document.querySelector('.chart-controls').prepend(control);
    
    document.getElementById('pagesPerScreenSelect').addEventListener('change', function() {
        pagesPerScreen = parseInt(this.value);
        updateChartData();
    });
}


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


// Модифицированная функция загрузки страниц
async function loadPages(startPage) {
    if (isLoading) return;
    
    isLoading = true;
    document.getElementById('loadingIndicator').style.display = 'inline';
    
    try {
        // Загружаем все страницы для текущего диапазона
        const pagePromises = [];
        for (let i = 0; i < pagesPerScreen; i++) {
            const page = startPage + i;
            if (page <= 100) {
                allMeasurements[page - 1] = undefined;
            }
            if (page > 100) break; // Не превышаем максимальное количество страниц
            
            if (!allMeasurements[page - 1]) {
                pagePromises.push(fetchMeasurements(page));
            }
        }
        
        const results = await Promise.all(pagePromises);
        
        // Сохраняем загруженные данные
        results.forEach((measurements, index) => {
            const page = startPage + index;
            if (measurements && measurements.length > 0) {
                allMeasurements[page - 1] = measurements;
            }
        });
        
        currentPage = startPage;
        document.getElementById('currentPageDisplay').textContent = 
           `Страницы: ${currentPage}–${Math.min(currentPage + pagesPerScreen - 1, 100)}`
            
        updateChartData();
    } catch (error) {
        console.error('Error loading pages:', error);
    } finally {
        isLoading = false;
        document.getElementById('loadingIndicator').style.display = 'none';
    }
}


// Инициализация ползунка
function initPageSlider() {
    const slider = document.getElementById('pageSlider');
    if (!slider) return;
    
    slider.addEventListener('input', function() {
        isSliderMoving = true;
    });
    
    slider.addEventListener('change', async function() {
        const page = parseInt(this.value);
        // Корректируем номер страницы с учетом количества страниц на экран
        const startPage = Math.min(page, 100 - pagesPerScreen + 1);
        await loadPages(startPage);
        isSliderMoving = false;
    });
}


// Функция для обработки данных измерений
function processMeasurementsData(measurements) {
    if (!measurements) return { labels: [], loadPower: [], solarPower: [], batteryPower: [], essTotalInputPower: [] };
    
    // Сортируем по возрастанию времени (старые данные сначала)
    const sortedMeasurements = [...measurements].sort((a, b) => 
        new Date(a.measured_at) - new Date(b.measured_at));
    
    const labels = [];
    const loadPower = [];
    const solarPower = [];
    const batteryPower = [];
    const essTotalInputPower = [];
    
    sortedMeasurements.forEach(measurement => {
        const date = new Date(measurement.measured_at + 'Z');
        const timeStr = date.toLocaleTimeString('ru-RU', { 
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Europe/Moscow'
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
                    type: 'category',
                    title: {
                        display: true,
                        text: 'Время'
                    },
                    grid: {
                        display: false
                    },
                    // Убрали reverse: true, так как данные теперь правильно сортируются
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
    let combinedLabels = [];
    let combinedLoadPower = [];
    let combinedSolarPower = [];
    let combinedBatteryPower = [];
    let combinedEssTotalInputPower = [];

  //  console.log(`==== Обновление графика ====`);
  //  console.log(`Текущий диапазон: страницы ${currentPage}–${currentPage + pagesPerScreen - 1}`);

    for (let i = pagesPerScreen - 1; i >= 0; i--) {
        const page = currentPage + i;
        if (page > 100) continue;

        const measurements = allMeasurements[page - 1];
        if (measurements) {
            const {
                labels,
                loadPower,
                solarPower,
                batteryPower,
                essTotalInputPower
            } = processMeasurementsData(measurements);
    
       //     console.log(`Страница ${page}: от ${labels[0]} до ${labels[labels.length - 1]}`);

            // Вставляем в конец — чтобы сохранить хронологию
            combinedLabels.push(...labels);
            combinedLoadPower.push(...loadPower);
            combinedSolarPower.push(...solarPower);
            combinedBatteryPower.push(...batteryPower);
            combinedEssTotalInputPower.push(...essTotalInputPower);
        } else {
            console.log(`Страница ${page} — пусто или не загружена`);
        }
    }

    if (!powerChart || combinedLabels.length === 0) return;

    powerChart.data.labels = combinedLabels;
    powerChart.data.datasets[0].data = combinedLoadPower;
    powerChart.data.datasets[1].data = combinedSolarPower;
    powerChart.data.datasets[2].data = combinedBatteryPower;
    powerChart.data.datasets[3].data = combinedEssTotalInputPower;

    const allData = [
        ...combinedLoadPower,
        ...combinedSolarPower,
        ...combinedBatteryPower,
        ...combinedEssTotalInputPower
    ];

    const maxPower = Math.max(...allData);
    const minPower = Math.min(...allData);

    powerChart.options.scales.y.max = Math.ceil(maxPower / 10) * 10 + 5;
    powerChart.options.scales.y.min = Math.floor(minPower / 10) * 10 - 5;

   // console.log(`Всего точек: ${combinedLabels.length}`);
   // console.log(`==== Конец обновления ====\n`);

    powerChart.update();
}

// Основная функция запуска
async function startChartUpdates() {    
    // Инициализируем график
    initPowerChart();
    
    // Инициализируем элементы управления
    initPageSlider();
    initPagesPerScreenControl();
    
    // Инициализируем массив для хранения всех страниц
    allMeasurements = new Array(100);
    
    // Первоначальная загрузка
    await loadPages(1);
    
    // Периодическое обновление
    if (!chartUpdateInterval) {
        chartUpdateInterval = setInterval(async () => {
            if (!isSliderMoving && currentPage === 1) {
                const newMeasurements = await fetchMeasurements(1);
                if (newMeasurements.length > 0) {
                    allMeasurements[0] = newMeasurements;
                    updateChartData();
                }
            }
        }, 1000);
    }
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

// Добавляем стили для нового элемента управления
const style = document.createElement('style');
style.textContent = `
    .pages-control {
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .pages-control label {
        font-size: 14px;
        font-weight: bold;
    }
    .pages-control select {
        padding: 5px;
        border-radius: 4px;
        border: 1px solid #ccc;
    }
`;
document.head.appendChild(style);
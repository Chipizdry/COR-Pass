


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
    
    // Скрываем элемент по умолчанию
    control.style.display = 'none';
}



// Функция для загрузки данных по временному диапазону
async function loadDataForTimeRange(range) {
    const now = new Date();
    let startDate;
    let intervals = 60;
    
    switch(range) {
        case '1h': 
            startDate = new Date(now.getTime() - 3600000);
            intervals = 120;
            break;
        case '6h': 
            startDate = new Date(now.getTime() - 6 * 3600000);
            intervals = 360;
            break;
        case '12h': 
            startDate = new Date(now.getTime() - 12 * 3600000);
            intervals = 144;
            break;
        case '24h': 
            startDate = new Date(now.getTime() - 24 * 3600000);
            intervals = 96;
            break;
        case '3d': 
            startDate = new Date(now.getTime() - 3 * 24 * 3600000);
            intervals = 72;
            break;
        case '7d': 
            startDate = new Date(now.getTime() - 7 * 24 * 3600000);
            intervals = 168;
            break;
        case '30d': 
            startDate = new Date(now.getTime() - 30 * 24 * 3600000);
            intervals = 120;
            break;
        default: return;
    }
    
    try {
        isLoading = true;
        document.getElementById('loadingIndicator').style.display = 'inline';
        
        // Форматируем даты без миллисекунд
        const formatDateForAPI = (date) => {
            return date.toISOString().replace(/\.\d{3}Z$/, '');
        };
        
        const params = new URLSearchParams({
            start_date: formatDateForAPI(startDate),
            end_date: formatDateForAPI(now),
            intervals: intervals
        });
        
        const url = `/api/modbus/measurements/averaged/?${params.toString()}`;
       // console.log('Fetching data from:', url);
        
        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { detail: response.statusText };
            }
            console.error('Server error details:', errorData);
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
      //  console.log('Received data:', data);
        
        allMeasurements = [];
        if (data && data.length > 0) {
            allMeasurements[0] = data;
            currentPage = 1;
            updateChartData();
        }
    } catch (error) {
        console.error('Error loading time range data:', error);
        alert(`Ошибка загрузки данных: ${error.message}`);
    } finally {
        isLoading = false;
        document.getElementById('loadingIndicator').style.display = 'none';
    }
}



function initTimeRangeControl() {
    // Установим текущую дату в кастомных полях
    const now = new Date();
    const oneDayAgo = new Date(now.getTime() - (24 * 3600000));
    document.getElementById('startDate').value = formatDateTimeLocal(oneDayAgo);
    document.getElementById('endDate').value = formatDateTimeLocal(now);
    
    // Обработчик изменения периода
    document.getElementById('timeRangeSelect').addEventListener('change', function() {
        const isRealtime = this.value === 'realtime';
        const isCustom = this.value === 'custom';
        
        // Управление видимостью элементов
        document.querySelector('.pages-control').style.display = isRealtime ? 'flex' : 'none';
        document.querySelector('.time-range-slider-container').style.display = isRealtime ? 'block' : 'none';
        document.querySelector('.time-display').style.display = isRealtime ? 'block' : 'none';
        document.getElementById('customDateRange').style.display = isCustom ? 'flex' : 'none';
        
        if (isRealtime) {
            startLiveUpdates();
        } else if (isCustom) {
            // Останавливаем обновления в реальном времени
            stopChartUpdates();
        } else {
            // Загружаем данные для выбранного диапазона
            stopChartUpdates();
            loadDataForTimeRange(this.value);
        }
    });
    
    // Обработчик для кастомного диапазона
    document.getElementById('applyCustomRange').addEventListener('click', function() {
        const startDate = new Date(document.getElementById('startDate').value);
        const endDate = new Date(document.getElementById('endDate').value);
        
        if (!startDate || !endDate) {
            alert('Пожалуйста, выберите обе даты');
            return;
        }
        
        if (startDate >= endDate) {
            alert('Конечная дата должна быть позже начальной');
            return;
        }
        
        stopChartUpdates();
        fetchAveragedMeasurements(startDate, endDate);
    });
    
    // Запускаем режим реального времени по умолчанию
    startLiveUpdates();
}

async function fetchAveragedMeasurements(startDate, endDate) {
    try {
        isLoading = true;
        document.getElementById('loadingIndicator').style.display = 'inline';
        
        const durationHours = (endDate - startDate) / (1000 * 60 * 60);
        let intervals;
        
        if (durationHours <= 1) intervals = 120;
        else if (durationHours <= 6) intervals = 180;
        else if (durationHours <= 24) intervals = 96;
        else intervals = 120;
        
        const formatDateForAPI = (date) => {
            return date.toISOString().replace(/\.\d{3}Z$/, '');
        };
        
        const params = new URLSearchParams({
            start_date: formatDateForAPI(startDate),
            end_date: formatDateForAPI(endDate),
            intervals: intervals
        });
        
        const url = `/api/modbus/measurements/averaged/?${params.toString()}`;
       // console.log('Fetching custom data from:', url);
        
        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка при загрузке данных');
        }
        
        const data = await response.json();
        
        allMeasurements = [];
        if (data && data.length > 0) {
            allMeasurements[0] = data;
            currentPage = 1;
            updateChartData();
        }
    } catch (error) {
        console.error('Error fetching averaged measurements:', error);
        alert(`Ошибка загрузки данных: ${error.message}`);
    } finally {
        isLoading = false;
        document.getElementById('loadingIndicator').style.display = 'none';
    }
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
    const soc =[];
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
        soc.push(measurement.soc);
    });

    return { labels, loadPower, solarPower, batteryPower, essTotalInputPower,soc };
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
                    label: 'Нагрузка(кВт)',
                    data: [],
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y' // Основная ось Y
                },
                {
                    label: 'Солнечная генерация (кВт)',
                    data: [],
                    borderColor: 'rgba(255, 159, 64, 1)',
                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: 'Мощность батареи (кВт)',
                    data: [],
                    borderColor: 'rgba(153, 102, 255, 1)',
                    backgroundColor: 'rgba(153, 102, 255, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: 'Входная мощность ESS(кВт)',
                    data: [],
                    borderColor: 'rgba(255, 99, 132, 1)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: 'Батарея (%)',
                    data: [],
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'soc-y', // Ось для SOC
                    borderDash: [5, 5], // Пунктирная линия
                    hidden: false // Показываем по умолчанию
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
                    },
                    position: 'left'
                },
                'soc-y': {
                    title: {
                        display: true,
                        text: 'Заряд (%)'
                    },
                    min: 0,
                    max: 100,
                    ticks: {
                        stepSize: 10
                    },
                    position: 'right',
                    grid: {
                        drawOnChartArea: false // Не показываем сетку для SOC
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
                            let label = context.dataset.label || '';
                            if (label.includes('SOC')) {
                                return `${label}: ${context.raw}%`;
                            }
                            return `${label}: ${context.raw.toFixed(2)} кВт`;
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
    let combinedSoc = [];
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
                soc,
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
            combinedSoc.push(...soc);
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
    powerChart.data.datasets[4].data = combinedSoc;

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
    // Инициализация графика и элементов управления
    initPowerChart();
    initPageSlider();
    initTimeRangeControl();
    
    // Инициализация массива измерений
    allMeasurements = new Array(100);
    
    // Запуск режима реального времени
    startLiveUpdates();
}

function startLiveUpdates() {
    // Останавливаем предыдущие обновления, если они есть
    stopChartUpdates();
    
    // Загружаем первую страницу
    loadPages(1);
    
    // Запускаем интервал обновлений
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




function stopChartUpdates() {
    if (chartUpdateInterval) {
        clearInterval(chartUpdateInterval);
        chartUpdateInterval = null;
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


function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}
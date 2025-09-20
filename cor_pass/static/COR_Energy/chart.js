


// Функция для загрузки энергетических данных по временному диапазону
async function loadEnergyDataForTimeRange(range, objectName = null) {
    const now = new Date();
    let startDate;
    let intervalMinutes = 30; // по умолчанию 30 минут

    switch(range) {
        case 'today':
            startDate = new Date(now);
            startDate.setHours(0, 0, 0, 0);
            intervalMinutes = 30;
            break;

        case 'this_week':
            startDate = new Date(now);
            const day = startDate.getDay();
            const diff = (day === 0 ? -6 : 1) - day;
            startDate.setDate(startDate.getDate() + diff);
            startDate.setHours(0, 0, 0, 0);
            intervalMinutes = 30 * 24; // 1 день в минутах
            break;

        case '1d':
            startDate = new Date(now.getTime() - 24 * 3600000);
            intervalMinutes = 30;
            break;

        case '7d':
            startDate = new Date(now.getTime() - 7 * 24 * 3600000);
            intervalMinutes = 60 * 12; // 12 Часов в минутах
            break;

        case '30d':
            startDate = new Date(now.getTime() - 30 * 24 * 3600000);
            intervalMinutes = 60 * 24; // 1 день в минутах
            break;

        default:
            console.error('Неверный диапазон:', range);
            return;
    }

    try {
        isLoading = true;
        showChartLoading();

        const formatDateForAPI = (date) => {
            return date.toISOString().replace(/\.\d{3}Z$/, '');
        };


        const params = new URLSearchParams({
            start_date: formatDateForAPI(startDate),
            end_date: formatDateForAPI(now),
            interval_minutes: intervalMinutes
        });

        if (objectName) {
            params.append('object_name', objectName);
        }

        const url = `/api/modbus/measurements/energy/?${params.toString()}`;
        console.log('Fetching energy data with URL:', url);

        const response = await fetch(url, {
            headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { detail: response.statusText };
            }
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        console.log('==== Energy data received ====');
        console.log('range:', range, 'objectName:', objectName);
        console.log('raw data:', data);

        if (data && data.intervals && data.intervals.length > 0) {

            console.log('Intervals count:', data.intervals.length);
            // Формируем данные для графика
            const chartData = processEnergyDataWithPlaceholders(data);

            data.intervals.forEach((i, idx) => {
                console.log(idx, i.interval_start, i.solar_energy_kwh, i.load_energy_kwh, i.grid_energy_kwh, i.battery_energy_kwh);
            });


            // Рисуем график
            updateBarChart(chartData);

            // Выводим итоговые значения
            if (data.totals) {
                updateTotalsDisplay(data.totals);
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки энергетических данных:', error);
        alert(`Ошибка загрузки данных: ${error.message}`);
    } finally {
        isLoading = false;
        hideChartLoading();
    }
}


// Функция для обновления итогов
function updateTotalsDisplay(totals) {
    document.getElementById('totalSolar').innerText = totals.solar_energy_total + ' кВт·ч';
    document.getElementById('totalLoad').innerText = totals.load_energy_total + ' кВт·ч';
    document.getElementById('totalGridImport').innerText = totals.grid_import_total + ' кВт·ч';
    document.getElementById('totalGridExport').innerText = totals.grid_export_total + ' кВт·ч';
  //  document.getElementById('totalBattery').innerText = totals.battery_energy_total + ' кВт·ч';
}



async function loadEnergyDataForCustomRange(startDate, endDate, objectName = null) {
    try {
        isLoading = true;
        document.getElementById('chartLoadingOverlay').style.display = 'flex';

        const durationHours = (endDate - startDate) / (1000 * 60 * 60);
        let intervalMinutes = 30; // по умолчанию 30 минут

        // Автоматически увеличиваем интервал для больших периодов
        if (durationHours > 24 * 7) { // больше недели
            intervalMinutes = 60 * 24; // 1 день
        } else if (durationHours > 24 * 3) { // больше 3 дней
            intervalMinutes = 60 * 12; // 12 часов
        } else if (durationHours > 24) { // больше суток
            intervalMinutes = 60 * 6; // 6 часов
        } else if (durationHours > 12) { // больше 12 часов
            intervalMinutes = 60; // 1 час
        }

        const formatDateForAPI = (date) => date.toISOString().replace(/\.\d{3}Z$/, '');
       
         // Формируем параметры для query string
         const params = new URLSearchParams({
            start_date: formatDateForAPI(startDate),
            end_date: formatDateForAPI(endDate),
            interval_minutes: intervalMinutes
        });

        if (objectName) {
            params.append('object_name', objectName);
        }

        const url = `/api/modbus/measurements/energy/?${params.toString()}`;
        console.log('Fetching energy data from:', url);
        
        const response = await fetch(url, { 
            headers: { 'Accept': 'application/json' } 
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Energy data received:', data);

        if (data && data.intervals && data.intervals.length > 0) {
            // Формируем данные для графика
            const chartData = processEnergyDataWithPlaceholders(data);

            // Рисуем график
            updateBarChart(chartData);

            // Выводим итоговые значения
            if (data.totals) {
                updateTotalsDisplay(data.totals);
            }
        } else {
            console.warn('No energy data found for the selected range');
            alert('Нет данных по энергии для выбранного периода');
        }
    } catch (error) {
        console.error('Error loading custom energy data:', error);
        alert(`Ошибка загрузки данных: ${error.message}`);
    } finally {
        isLoading = false;
        document.getElementById('chartLoadingOverlay').style.display = 'none';
    }
}



function initChartTypeControl() {
    const chartTypeSelect = document.getElementById('chartTypeSelect');
    if (!chartTypeSelect) return; // если вдруг элемент не найден

    // Загружаем сохраненные настройки при инициализации
   // loadChartSettings();

    chartTypeSelect.addEventListener('change', function() {
        currentChartType = this.value;
        // Сохраняем настройки сразу после изменения
        saveChartSettings();
        // сначала всё останавливаем
        stopChartUpdates();

        // Уничтожаем оба графика, если они есть
        if (powerChart) { powerChart.destroy(); powerChart = null; }
        if (energyChart) { energyChart.destroy(); energyChart = null;}

        // обновляем селектор периодов под выбранный тип
        updateTimeRangeOptions(currentChartType);

        if (currentChartType === 'line') {
            document.getElementById('energyTotals').classList.add('hidden');  // 🔹 всегда скрываем в line
            initPowerChart();   // заново создаём line chart
            startLiveUpdates(); // включаем live режим
        } else if (currentChartType === 'bar') {
            document.getElementById('energyTotals').classList.remove('hidden'); // 🔹 показываем в bar
            loadEnergyDataForTimeRange('today'); // рисуем bar chart
        }
    });
}

function updateBarChart(chartData) {
    const ctx = document.getElementById('powerChart').getContext('2d');

    if (energyChart) {
        energyChart.destroy();
    }

    if (!chartData || chartData.length === 0) return;

    const startDate = new Date(chartData[0].interval);
    const endDate = new Date(chartData[chartData.length - 1].interval);

    // Создаем полный набор интервалов (включая пропущенные)
    const allIntervals = createCompleteIntervals(chartData, startDate, endDate);
    
    // Вычисляем среднюю высоту для заглушек
    const averageHeight = calculateAverageHeight(allIntervals);
    
    const labels = allIntervals.map(interval => 
        formatDateLabel(interval.interval_start, startDate, endDate, 'bar')
    );

    energyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Солнечная энергия (кВт·ч)',
                    data: allIntervals.map(interval => 
                        interval.isPlaceholder ? averageHeight * 0.8 : interval.solar
                    ),
                    backgroundColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(200, 200, 200, 0.5)' : 'rgba(255, 206, 86, 0.7)'
                    ),
                    borderColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(150, 150, 150, 0.8)' : 'rgba(255, 206, 86, 1)'
                    ),
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9
                },
                {
                    label: 'Нагрузка (кВт·ч)',
                    data: allIntervals.map(interval => 
                        interval.isPlaceholder ? averageHeight * 0.6 : interval.load
                    ),
                    backgroundColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(200, 200, 200, 0.5)' : 'rgba(75, 192, 192, 0.7)'
                    ),
                    borderColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(150, 150, 150, 0.8)' : 'rgba(75, 192, 192, 1)'
                    ),
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9
                },
                {
                    label: 'Сеть (кВт·ч)',
                    data: allIntervals.map(interval => 
                        interval.isPlaceholder ? averageHeight * 0.4 : interval.grid
                    ),
                    backgroundColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(200, 200, 200, 0.5)' : 'rgba(255, 99, 132, 0.7)'
                    ),
                    borderColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(150, 150, 150, 0.8)' : 'rgba(255, 99, 132, 1)'
                    ),
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9
                },
                {
                    label: 'Батарея (кВт·ч)',
                    data: allIntervals.map(interval => 
                        interval.isPlaceholder ? averageHeight * 0.2 : interval.battery
                    ),
                    backgroundColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(200, 200, 200, 0.5)' : 'rgba(153, 102, 255, 0.7)'
                    ),
                    borderColor: allIntervals.map(interval => 
                        interval.isPlaceholder ? 'rgba(150, 150, 150, 0.8)' : 'rgba(153, 102, 255, 1)'
                    ),
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { 
                    position: 'top',
                    labels: {
                        filter: function(item, chart) {
                            // Скрываем легенду для заглушек
                            return !item.text.includes('Заглушка');
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const datasetLabel = context.dataset.label || '';
                            const value = context.raw;
                            const dataIndex = context.dataIndex;
                            const interval = allIntervals[dataIndex];
                            
                            if (interval && interval.isPlaceholder) {
                                return `${datasetLabel}: Нет данных`;
                            }
                            return `${datasetLabel}: ${value.toFixed(2)} кВт·ч`;
                        },
                        afterLabel: function(context) {
                            const dataIndex = context.dataIndex;
                            const interval = allIntervals[dataIndex];
                            if (interval && interval.isPlaceholder) {
                                return `Пропущенный интервал (${interval.measurement_count || 0} измерений)`;
                            }
                            return null;
                        },
                        title: function(context) {
                            const dataIndex = context[0].dataIndex;
                            const interval = allIntervals[dataIndex];
                            if (interval && interval.isPlaceholder) {
                                return 'Нет данных';
                            }
                            return context[0].label;
                        }
                    }
                }
            },
            scales: {
                x: { 
                    stacked: true,
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        callback: function(value, index) {
                            const interval = allIntervals[index];
                            if (interval && interval.isPlaceholder) {
                                return '∅'; // Специальный символ для пропущенных интервалов
                            }
                            return this.getLabelForValue(value);
                        }
                    }
                },
                y: {
                    stacked: false,
                    title: { display: true, text: 'Энергия (кВт·ч)' },
                    beginAtZero: true
                }
            }
        }
    });
}

// Функция для вычисления средней высоты столбцов
function calculateAverageHeight(intervals) {
    const validIntervals = intervals.filter(interval => !interval.isPlaceholder);
    
    if (validIntervals.length === 0) return 1; // Значение по умолчанию
    
    let total = 0;
    let count = 0;
    
    validIntervals.forEach(interval => {
        if (interval.solar !== null && interval.solar > 0) {
            total += interval.solar;
            count++;
        }
        if (interval.load !== null && interval.load > 0) {
            total += interval.load;
            count++;
        }
        if (interval.grid !== null && Math.abs(interval.grid) > 0) {
            total += Math.abs(interval.grid);
            count++;
        }
        if (interval.battery !== null && Math.abs(interval.battery) > 0) {
            total += Math.abs(interval.battery);
            count++;
        }
    });
    
    return count > 0 ? total / count : 1;
}




function updateTimeRangeOptions(chartType) {
    const timeRangeSelect = document.getElementById('timeRangeSelect');
    if (!timeRangeSelect) return;

    // очищаем старые опции
    timeRangeSelect.innerHTML = '';

    const ranges = chartType === 'line' ? lineTimeRanges : barTimeRanges;

    ranges.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.value;
        opt.textContent = r.label;
        timeRangeSelect.appendChild(opt);
    });

    // выбираем первую опцию по умолчанию
    timeRangeSelect.value = ranges[0].value;
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
        
        if (currentChartType === 'line') {
            document.getElementById('energyTotals').classList.add('hidden');  // 🔹 всегда скрываем в line
            if (isRealtime) {
                startLiveUpdates();
            } else if (isCustom) {
                stopChartUpdates();
            } else {
                stopChartUpdates();
                loadDataForTimeRange(this.value);
            }
        } else if (currentChartType === 'bar') {
            document.getElementById('energyTotals').classList.remove('hidden'); // 🔹 показываем в bar
            document.querySelector('.pages-control').style.display =  'none';
            if (isCustom) {
                stopChartUpdates();
            } else {
                currentBarTimeRange = this.value;
                loadEnergyDataForTimeRange(currentBarTimeRange);
            }
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

    if (currentChartType === 'line') {
        fetchAveragedMeasurements(startDate, endDate);
    } else if (currentChartType === 'bar') {
        // Для столбчатого графика сохраняем custom как текущий диапазон
        currentBarTimeRange = 'custom';
        saveChartSettings();
        loadEnergyDataForCustomRange(startDate, endDate);
    }
});
        // Запускаем режим реального времени по умолчанию
        startLiveUpdates();


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
    if (!measurements) return { labels: [], loadPower: [], solarPower: [], batteryPower: [], essTotalInputPower: [], soc: [] };
    
    const sortedMeasurements = [...measurements].sort((a, b) => 
        new Date(a.measured_at) - new Date(b.measured_at)
    );

    const labels = [];
    const soc = [];
    const loadPower = [];
    const solarPower = [];
    const batteryPower = [];
    const essTotalInputPower = [];

    const totalDurationMs = new Date(sortedMeasurements.at(-1)?.measured_at) - new Date(sortedMeasurements[0]?.measured_at);

    sortedMeasurements.forEach(measurement => {
        labels.push(
            formatDateLabel(measurement.measured_at, totalDurationMs, sortedMeasurements.length, 'line')
        );
        loadPower.push(Math.round(measurement.inverter_total_ac_output / 10) / 100);
        solarPower.push(Math.round(measurement.solar_total_pv_power / 10) / 100);
        batteryPower.push(Math.round(measurement.general_battery_power / 10) / 100);
        essTotalInputPower.push(Math.round(measurement.ess_total_input_power / 10) / 100);
        soc.push(measurement.soc);
    });

    return { labels, loadPower, solarPower, batteryPower, essTotalInputPower, soc };
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
    powerChart.update();
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
    }, 900);
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


function formatDateLabel(dateString, startDate, endDate, chartType) {
    const date = new Date(dateString);
    
    if (chartType === 'bar') {
        const duration = endDate - startDate;
        const days = duration / (1000 * 60 * 60 * 24);
        
        if (days <= 1) {
            // Для периода до 1 дня: показываем часы и минуты
            return date.toLocaleTimeString('ru-RU', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } else if (days <= 7) {
            // Для периода до недели: показываем день и время
            return date.toLocaleString('ru-RU', { 
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit'
            });
        } else {
            // Для больших периодов: показываем только дату
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit'
            });
        }
    }
    
    return date.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}




// === Обработка данных от сервера ===
function processEnergyDataWithPlaceholders(serverData) {
    if (!serverData || !serverData.intervals || serverData.intervals.length === 0) {
        return [];
    }

    // Просто преобразуем интервалы в нужный формат
    return serverData.intervals.map(interval => ({
        interval: interval.interval_start,
        interval_start: interval.interval_start,
        solar: interval.solar_energy_kwh,
        load: interval.load_energy_kwh,
        grid: interval.grid_energy_kwh,
        battery: interval.battery_energy_kwh,
        isPlaceholder: false   // всегда реальные данные
    }));
}

// === Достраивание временного ряда с заглушками ===
function createCompleteIntervals(chartData, startDate, endDate) {
    if (!chartData || chartData.length === 0) return [];

    // Определяем шаг интервала строго по данным
    const firstInterval = new Date(chartData[0].interval);
    const secondInterval = chartData.length > 1 ? new Date(chartData[1].interval) : null;

    let intervalStepMs;
    if (secondInterval) {
        intervalStepMs = secondInterval - firstInterval;
    } else {
        intervalStepMs = 30 * 60 * 1000; // fallback 30 минут
    }

    const completeIntervals = [];
    // 🚀 Начинаем от первого интервала из данных
    let currentTime = new Date(firstInterval);

    while (currentTime <= endDate) {
        const matchingData = chartData.find(data => {
            const dataTime = new Date(data.interval).getTime();
            return Math.abs(dataTime - currentTime.getTime()) < intervalStepMs / 2;
        });

        if (matchingData) {
            completeIntervals.push({ ...matchingData, isPlaceholder: false });
        } else {
            completeIntervals.push({
                interval: currentTime.toISOString(),
                interval_start: currentTime.toISOString(),
                solar: null,
                load: null,
                grid: null,
                battery: null,
                isPlaceholder: true
            });
        }

        currentTime = new Date(currentTime.getTime() + intervalStepMs);
    }

    return completeIntervals;
}
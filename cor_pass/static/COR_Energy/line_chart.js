




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
        case '3h': 
            startDate = new Date(now.getTime() - 3 * 3600000);
            intervals = 360;
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
            intervals = 240;
            break;
        default: return;
    }
    
    try {
        isLoading = true;
        showChartLoading();

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
        hideChartLoading();
    }
}




// Функция для инициализации графика
function initPowerChart() {
    const ctx = document.getElementById('powerChart').getContext('2d');
    document.getElementById('energyTotals').classList.add('hidden'); 
    if (powerChart) {
        powerChart.destroy();
    }
    
    powerChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Нагрузка (кВт)',
                    data: [],
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y'
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
                    label: 'Электросеть(кВт)',
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
                    yAxisID: 'soc-y',
                    borderDash: [5, 5],
                    hidden: false
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
                        text: 'Время / Дата' // изменено: общее название
                    },
                    grid: { display: false }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Мощность (кВт)'
                    },
                    min: -20,
                    max: 20,
                    ticks: { stepSize: 5 },
                    position: 'left'
                },
                'soc-y': {
                    title: {
                        display: true,
                        text: 'Заряд (%)'
                    },
                    min: 0,
                    max: 100,
                    ticks: { stepSize: 10 },
                    position: 'right',
                    grid: { drawOnChartArea: false }
                }
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label.includes('Батарея (%)')) { // изменено: проверяем по названию
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





async function fetchAveragedMeasurements(startDate, endDate) {
    try {
        isLoading = true;
        showChartLoading();
        
        
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
        document.getElementById('chartLoadingOverlay').style.display = 'none';
    }
}
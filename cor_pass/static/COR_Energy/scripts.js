



    document.addEventListener("DOMContentLoaded", function() {

        fetchEss().then(() => {
            document.getElementById('State_Of_Сharge').value = initialSocValue;
            document.getElementById('socSliderValue').textContent = initialSocValue;
        });

       

            // Инициализация графика и элементов управления
        initPageSlider();
        initTimeRangeControl();
        initChartTypeControl(); // переключатель

        initPowerChart();
 

        // Инициализация массива измерений
        allMeasurements = new Array(100);

        makeModalDraggable('batteryModal');
        makeModalDraggable('RegistersModal');
        makeModalDraggable('loadSettingsModal');
        makeModalDraggable('GridSettingsModal');
        makeModalDraggable('SolarModal');
        makeModalDraggable('inverterModal');
        makeModalDraggable('ExcelModal');
    // Получаем элементы модальных окон
        const batteryModal = document.getElementById('batteryModal');
        const inverterModal = document.getElementById('inverterModal');
        const loadModal = document.getElementById('loadSettingsModal');
        const GridModal = document.getElementById('GridSettingsModal');
        const SolarPanelModal = document.getElementById('SolarModal');
        const TestRegistersModal = document.getElementById('RegistersModal');
        
        // Получаем иконки
        const batteryIcon = document.getElementById('batteryIcon');
        const inverterIcon = document.getElementById('inverterIcon');
        const loadIcon = document.getElementById('loadIcon'); 
        const gridIcon = document.getElementById('power-grid-icon');
        const solarIcon = document.getElementById('SolarBatteryIcon');
        
        // Получаем кнопки закрытия модальных окон 
        const closeBattery = document.getElementById('closeBattery');
        const closeInverter = document.getElementById('closeInverterModal');
        const closeLoad = document.getElementById('closeLoadSettings');
        const closeGrid = document.getElementById('closeGridSettings');
        const closeSolar = document.getElementById('closeSolarModal');
        const closeRegistersModal = document.getElementById('closeRegistersModal');
        
        // Открытие модального окна для батареи
        batteryIcon.onclick = function() {
            batteryModal.style.display = 'flex';
        }
        
        // Открытие модального окна для инвертора
        inverterIcon.onclick = function() {
            inverterModal.style.display = 'flex';
            
        }
            // Открытие модального окна для нагрузки
        loadIcon.onclick = function() {
            loadModal.style.display = 'flex';
        }

            // Открытие модального окна для сети
            gridIcon.onclick = function() {
            GridModal.style.display = 'flex';
        }
        
        // Открытие модального окна для солнечных панелей
        solarIcon.onclick = function() {
            SolarPanelModal.style.display = 'flex';
        }
        
        // Закрытие модальных окон
        closeBattery.onclick = function() {
            resetSocSlider();
            batteryModal.style.display = 'none';
        }
        closeInverter.onclick = function() {
            inverterModal.style.display = 'none';
        }
        closeLoad.onclick = function() {
            loadModal.style.display = 'none'; 
        }

        closeGrid.onclick = function() {
            GridModal.style.display = 'none'; 
        }

        closeSolar.onclick = function() {
            SolarPanelModal.style.display = 'none'; 
        }
    });
    


            function updateBatteryFlow(power) {
                const indicator = document.getElementById('batteryFlowIndicator');
                const label = document.getElementById('batteryFlowLabel');
                const maxPower = 140000;  // Вт
                const maxWidth = 1400;   // Половина общей ширины (2600 / 2)
                const centerX = 1525;    // Центр батареи
            
                const clampedPower = Math.max(-maxPower, Math.min(maxPower, power));
                const absPower = Math.abs(clampedPower);
                const fillWidth = (absPower / maxPower) * maxWidth;
            
                const xPosition = clampedPower >= 0
                    ? centerX
                    : centerX - fillWidth;
            
                // Цвет: зелёный (заряд) → красный (разряд)
                const level = absPower / maxPower;
                let fillColor;
                if (level <= 0.5) {
                    const r = Math.round(510 * level);
                    fillColor = `rgb(${r}, 255, 0)`;  // зелёный → жёлтый
                } else {
                    const g = Math.round(255 - (level - 0.5) * 510);
                    fillColor = `rgb(255, ${g}, 0)`;  // жёлтый → красный
                }
            
                // Обновление индикатора (если есть)
                if (indicator) {
                    indicator.setAttribute('x', xPosition);
                    indicator.setAttribute('width', fillWidth);
                    indicator.setAttribute('fill', fillColor);
                }
            
                // Обновление текста
                const kilowatts = (clampedPower / 1000).toFixed(1).replace('-0.0', '0.0');
                if (label) {
                    if (clampedPower < 0) {
                        label.textContent = `Разряд: ${Math.abs(kilowatts)} кВт`;
                    } else if (clampedPower > 0) {
                        label.textContent = `Заряд: ${kilowatts} кВт`;
                    } else {
                        label.textContent = `Нет потока`;
                    }
                }
            
                // Обновление линий батареи
                const batteryRectV = document.getElementById('batteryFlowRectV');
                const batteryRectH = document.getElementById('batteryFlowRectH');
                const batteryAnimV = document.getElementById('batteryFlowAnimV');
                const batteryAnimH = document.getElementById('batteryFlowAnimH');
                
                if (batteryRectV && batteryRectH && batteryAnimV && batteryAnimH) {
                    // Изменяем цвет обеих линий
                    batteryRectV.setAttribute('fill', fillColor);
                    batteryRectH.setAttribute('fill', fillColor);
                    
                    // Управляем анимацией в зависимости от направления потока
                    if (clampedPower < 0) {
                        // Разряд - поток вниз по вертикали и влево по горизонтали
                        batteryAnimV.setAttribute('from', '0,40');
                        batteryAnimV.setAttribute('to', '0,0');
                        batteryAnimH.setAttribute('from', '0,0');
                        batteryAnimH.setAttribute('to', '40,0');
                    } else if (clampedPower > 0) {
                        // Заряд - поток вверх по вертикали и вправо по горизонтали
                        batteryAnimV.setAttribute('from', '0,0');
                        batteryAnimV.setAttribute('to', '0,40');
                        batteryAnimH.setAttribute('from', '40,0');
                        batteryAnimH.setAttribute('to', '0,0');
                    } else {
                        // Нет потока - останавливаем анимацию
                        batteryAnimV.setAttribute('from', '0,0');
                        batteryAnimV.setAttribute('to', '0,0');
                        batteryAnimH.setAttribute('from', '0,0');
                        batteryAnimH.setAttribute('to', '0,0');
                    }
                }
            }
            
            
            
              // Функция для обновления индикатора нагрузки
              function updateLoadIndicator(powerKw) {
                const maxWidth = 1900;  // Максимальная ширина индикатора (в SVG)
                const maxPower = 160;   // Максимальная мощность (кВт)
            
                // Ограничиваем мощность
                powerKw = Math.min(Math.max(powerKw, 0), maxPower);
            
                // Вычисляем ширину в пикселях
                const width = (powerKw / maxPower) * maxWidth;
            
                // Цвет от зелёного к красному
                const hue = (1 - (powerKw / maxPower)) * 120;
                const color = `hsl(${hue}, 100%, 50%)`;
            
                // Обновляем атрибуты SVG индикатора
                const indicator = document.getElementById('loadIndicator');
                if (indicator) {
                    indicator.setAttribute('width', width);
                    indicator.setAttribute('fill', color);
                }
            
                // Обновление текста
                const label = document.getElementById('loadIndicatorLabel');
                if (label) {
                    const text = `Нагрузка:${powerKw.toFixed(1)} кВт`;
                    label.textContent = text;
                }
            
                // Обновление линии нагрузки
                const loadRect = document.getElementById('loadFlowRect');
                const loadAnim = document.getElementById('loadFlowAnim');
                const loadLine = document.getElementById('loadFlowLine');
                
                if (loadRect && loadAnim && loadLine) {
                    // Изменяем цвет
                    loadRect.setAttribute('fill', color);
                    
                    // Управляем анимацией
                    if (powerKw > 0) {
                        // Есть нагрузка - поток слева направо
                        loadAnim.setAttribute('from', '0,0');
                        loadAnim.setAttribute('to', '40,0');
                        
                        // Показываем линию
                        loadLine.style.display = '';
                    } else {
                        // Нет нагрузки - останавливаем анимацию
                        loadAnim.setAttribute('from', '0,0');
                        loadAnim.setAttribute('to', '0,0');
                        
                        // Можно раскомментировать, если нужно скрывать линию при отсутствии нагрузки
                        // loadLine.style.display = 'none';
                    }
                }
            }
           
            
            function updateSolarPowerIndicator(totalPower) {
                const maxWidth = 550;    // ширина SVG индикатора в пикселях (как у loadIndicator)
                const maxPower = 180000; // максимальная мощность для 100%
                
                // Ограничиваем мощность между 0 и maxPower
                totalPower = Math.min(Math.max(totalPower, 0), maxPower);
                
                // Вычисляем ширину индикатора
                const width = (totalPower / maxPower) * maxWidth;
                
                // Вычисляем цвет в HSL — от зелёного (120) к красному (0)
                const hue = (1 - totalPower / maxPower) * 120;
                const color = `hsl(${hue}, 100%, 50%)`;
                
                // Обновление индикатора (если есть)
                const indicator = document.getElementById('solarPowerIndicator');
                if (indicator) {
                    indicator.setAttribute('width', width);
                    indicator.setAttribute('fill', color);
                }
                
                // Обновление текста (если есть)
                const label = document.getElementById('solarPowerLabel');
                if (label) {
                    label.textContent = `Мощность: ${(totalPower/1000).toFixed(1)} кВт`;
                }
                
                // Обновление линии солнечных панелей
                const solarRectV = document.getElementById('solarFlowRectV');
                const solarRectH = document.getElementById('solarFlowRectH');
                const solarAnimV = document.getElementById('solarFlowAnimV');
                const solarAnimH = document.getElementById('solarFlowAnimH');
                
                if (solarRectV && solarRectH && solarAnimV && solarAnimH) {
                    // Изменяем цвет
                    solarRectV.setAttribute('fill', color);
                    solarRectH.setAttribute('fill', color);
                    
                    // Управляем анимацией
                    if (totalPower > 0) {
                        // Активная генерация - поток вверх по вертикали и вправо по горизонтали
                        solarAnimV.setAttribute('from', '0,40');
                        solarAnimV.setAttribute('to', '0,0');
                        solarAnimH.setAttribute('from', '40,0');
                        solarAnimH.setAttribute('to', '0,0');
                        
                        // Показываем линии
                        document.getElementById('solarLineV').style.display = '';
                        document.getElementById('solarLineH').style.display = '';
                    } else {
                        // Нет генерации - останавливаем анимацию и скрываем линии
                        solarAnimV.setAttribute('from', '0,0');
                        solarAnimV.setAttribute('to', '0,0');
                        solarAnimH.setAttribute('from', '0,0');
                        solarAnimH.setAttribute('to', '0,0');
                        
                        // Можно раскомментировать, если нужно скрывать линии при отсутствии генерации
                         document.getElementById('solarLineV').style.display = 'none';
                         document.getElementById('solarLineH').style.display = 'none';
                    }
                }
            }



            
            function updateNetworkFlow(power) {
                const indicator = document.getElementById('networkFlowIndicator');
                const label = document.getElementById('networkFlowLabel'); 
                const maxPower = 14000;   // Максимальная мощность, Вт
                const maxWidth = 80;      // Максимальная ширина заливки, px
                const baseX = 83;         // Центр индикатора
            
                // Ограничим мощность
                const clampedPower = Math.max(-maxPower, Math.min(maxPower, power));
                const absPower = Math.abs(clampedPower);
            
                // Ширина индикатора
                const fillWidth = (absPower / maxPower) * maxWidth;
            
                // Положение по X
                const xPosition = clampedPower >= 0 ? baseX - fillWidth : baseX;
            
                // Цвет: зелёный → жёлтый → красный
                const level = absPower / maxPower; // 0.0 – 1.0
                let fillColor;
            
                if (level <= 0.5) {
                    // от зелёного (0,255,0) к жёлтому (255,255,0)
                    const r = Math.round(510 * level); // 0 → 255
                    fillColor = `rgb(${r}, 255, 0)`;
                } else {
                    // от жёлтого (255,255,0) к красному (255,0,0)
                    const g = Math.round(255 - (level - 0.5) * 510); // 255 → 0
                    fillColor = `rgb(255, ${g}, 0)`;
                }
            
                // Обновление индикатора
                if (indicator) {
                    indicator.setAttribute('x', xPosition);
                    indicator.setAttribute('width', fillWidth);
                    indicator.setAttribute('fill', fillColor);
                }
            
                // Обновление линии сети
                const networkLine = document.getElementById('networkFlowLine');
                const flowRect = document.getElementById('gridFlowRect');
                const flowAnim = document.getElementById('gridFlowAnim');
                
                if (networkLine && flowRect && flowAnim) {
                    // Изменяем цвет
                    flowRect.setAttribute('fill', fillColor);
                    
                    // Меняем направление анимации в зависимости от направления потока
                    if (clampedPower < 0) {
                        // Отдача в сеть - поток справа налево
                        flowAnim.setAttribute('from', '40,0');
                        flowAnim.setAttribute('to', '0,0');
                    } else if (clampedPower > 0) {
                        // Потребление из сети - поток слева направо
                        flowAnim.setAttribute('from', '0,0');
                        flowAnim.setAttribute('to', '40,0');
                    } else {
                        // Нет потока - останавливаем анимацию
                        flowAnim.setAttribute('from', '0,0');
                        flowAnim.setAttribute('to', '0,0');
                    }
                }
            
                // Обновление текста
                if (label) {
                    const kilowatts = (clampedPower / 100).toFixed(1).replace('-0.0', '0.0');
                    if (clampedPower < 0) {
                        label.textContent = `Отдача: ${Math.abs(kilowatts)} кВт`;
                    } else if (clampedPower > 0) {
                        label.textContent = `Потребление: ${kilowatts} кВт`;
                    } else {
                        label.textContent = `Нет потока`;
                    }
                }
            }
            
            // Обновляем ширину и цвет заливки в зависимости от уровня заряда
            function updateBatteryFill(level) {
                const batteryFill = document.getElementById('batteryFill');
                
                // Рассчитываем сдвиг по оси X относительно уровня заряда
                const maxFillWidth = 2550; // максимальная ширина батареи
                const fillWidth = (level / 100) * maxFillWidth;
                const xPosition = 420 + (maxFillWidth - fillWidth); // сдвиг вправо по мере разряда
            
                // Меняем x-координату и ширину заливки
                batteryFill.setAttribute('x', xPosition);
                batteryFill.setAttribute('width', fillWidth);
            
                // Меняем цвет заливки в зависимости от уровня заряда
                if (level > 50) {
                    // От зеленого к желтому
                    batteryFill.setAttribute('fill', `rgb(${255 - (level - 50) * 5.1}, 255, 0)`);
                } else {
                    // От желтого к красному
                    batteryFill.setAttribute('fill', `rgb(255, ${level * 5.1}, 0)`);
                }
             }



        function updateBatteryLimitLine(minimumSocLimit) {
        const batteryLimitLine = document.getElementById('batteryLimitLine');
        const batteryLimitText = document.getElementById('batteryLimitText');
        
        if (minimumSocLimit === undefined || minimumSocLimit === null) {
            // Скрываем элементы, если значение не задано
            batteryLimitLine.setAttribute('opacity', '0');
            batteryLimitText.setAttribute('opacity', '0');
            return;
        }         
        // Рассчитываем позицию аналогично функции updateBatteryFill
        const maxFillWidth = 2550;
        const fillWidth = (minimumSocLimit / 100) * maxFillWidth;
        const xPosition = 420 + (maxFillWidth - fillWidth);          
        // Обновляем позицию линии и текста
        batteryLimitLine.setAttribute('x1', xPosition);
        batteryLimitLine.setAttribute('x2', xPosition);
        batteryLimitLine.setAttribute('opacity', '1');              
        batteryLimitText.setAttribute('x', xPosition+180);
        batteryLimitText.setAttribute('opacity', '1');
    }




    // Функция сброса ползунка лимита батареи
    function resetSocSlider() {
        const slider = document.getElementById('State_Of_Сharge');
        slider.value = initialSocValue;
        document.getElementById('socSliderValue').textContent = initialSocValue;
        const saveButton = document.getElementById('saveBatteryButton');
        isSliderChanged = false;
        saveButton.disabled = true; 
        // Очищаем таймер
        if (socChangeTimeout) {
            clearTimeout(socChangeTimeout);
            socChangeTimeout = null;
        }
    }


    function resetInverterSlider() {
        const slider = document.getElementById('InverterPowerSlider');
        slider.value = initialInverterPowerValue;
        document.getElementById('InverterSliderValue').textContent = initialInverterPowerValue;
        const saveButton = document.getElementById('saveInverterPower');
        isInverterSliderChanged = false;
        saveButton.disabled = true;
        // Очищаем таймер
        if (inverterChangeTimeout) {
            clearTimeout(inverterChangeTimeout);
            inverterChangeTimeout = null;
        }
    }



    function resetChargingSlider() {
        const slider = document.getElementById('ChargingCurrentSlider');
        slider.value = initialChargingCurrent;
        document.getElementById('ChargingSliderValue').textContent = initialChargingCurrent;
        chargingCurrentChanged = false;
    
        if (chargingChangeTimeout) {
            clearTimeout(chargingChangeTimeout);
            chargingChangeTimeout = null;
        }
    
        const saveButton = document.getElementById('saveInverterPower');
        if (!inverterPowerChanged && !chargingCurrentChanged) {
            saveButton.disabled = true;
        }
    }    

    


// Функция показа сообщения
function showConfirmationMessage(message, isSuccess) {
    const element = document.getElementById('confirmationMessage');
    const saveButton = document.getElementById('saveBatteryButton');
    element.textContent = message;
    element.style.color = isSuccess ? "rgb(11, 226, 11)" : "red";
    element.style.display = "block";
    saveButton.disabled = true; 
    setTimeout(() => {
        element.style.display = "none";
    }, 4000);
}

// Функция показа сообщения для отдачи в сеть
function showFeedInConfirmationMessage(message, isSuccess) {
    const element = document.getElementById('feedInConfirmationMessage');
    const saveButton = document.getElementById('saveFeedInButton');
    element.textContent = message;
    element.style.color = isSuccess ? "rgb(11, 226, 11)" : "red";
    element.style.display = "block";
    saveButton.disabled = true;
    setTimeout(() => {
        element.style.display = "none";
    }, 4000);
}

function showInverterConfirmationMessage(message, isSuccess) {
    const element = document.getElementById('InverterConfirmationMessage');
    const saveButton = document.getElementById('saveInverterPower');
    element.textContent = message;
    element.style.color = isSuccess ? "rgb(11, 226, 11)" : "red";
    element.style.display = "block";
    saveButton.disabled = true;
    setTimeout(() => {
        element.style.display = "none";
    }, 4000);
}

// Функция сброса ползунка отдачи в сеть
function resetFeedInSlider() {
    const slider = document.getElementById('feedInPowerSlider');
    slider.value = initialFeedInValue;
    document.getElementById('feedInSliderValue').textContent = initialFeedInValue;
    const saveButton = document.getElementById('saveFeedInButton');
    isFeedInSliderChanged = false;
    saveButton.disabled = true;
    // Очищаем таймер
    if (feedInChangeTimeout) {
        clearTimeout(feedInChangeTimeout);
        feedInChangeTimeout = null;
    }
}


// Функция для проверки состояния соединения
async function checkConnectionStatus() {
    try {
        const response = await fetch('/api/modbus/error_count');
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        updateConnectionIndicator(data.error_count);
        console.log('Ошибки:', data.error_count);
    } catch (error) {
        console.error('Error fetching connection status:', error);
        // Если запрос не удался, считаем что соединение плохое
        updateConnectionIndicator(9); // ERROR_THRESHOLD
    }
}


// Функция для обновления индикатора соединения
function updateConnectionIndicator(errorCount) {
    const indicator = document.getElementById('connectionIndicator');
    const ERROR_THRESHOLD = 9; // Должно совпадать с серверной константой
    
    if (errorCount >= ERROR_THRESHOLD) {
        indicator.classList.remove('active');
        indicator.style.backgroundColor = 'red';
    } else if (errorCount === 0) {
        indicator.classList.add('active');
        indicator.style.backgroundColor = 'rgb(7, 206, 7)';
    } else {
        // Промежуточное состояние (например, желтый для 1-8 ошибок)
        indicator.classList.remove('active');
        indicator.style.backgroundColor = 'yellow';
    }
}


// Функция для открытия модального окна регистров
function openRegistersModal() {
    const modal = document.getElementById('RegistersModal');
    modal.style.display = 'flex';
    
    // Сброс значений полей при открытии
    document.getElementById('slave_id').value = 100;
    document.getElementById('start_reg').value = 800;
    document.getElementById('end_reg').value = 830;
    document.getElementById('register_to_write').value = '';
    document.getElementById('register_value').value = '';
    
    // Скрываем блок результатов
    const output = document.getElementById('register_results_output');
    output.textContent = '';
    output.style.display = 'none';
    makeModalDraggable('RegistersModal');
}

async function testRegisters() {
    const slaveId = document.getElementById('slave_id').value;
    const startReg = document.getElementById('start_reg').value;
    const endReg = document.getElementById('end_reg').value;
    const output = document.getElementById('register_results_output');
    
    if (parseInt(startReg) > parseInt(endReg)) {
        alert("Начальный регистр должен быть меньше или равен конечному");
        return;
    }
    
    // Показываем загрузку (серый цвет)
    output.textContent = "Тестирование...";
    output.style.display = 'block';
    output.style.color = '#666';
    output.style.padding = '10px';
    output.style.borderRadius = '4px';
    
    try {
        const response = await fetch(`/api/modbus/test_dynamic_ess_registers?start=${startReg}&end=${endReg}&unit_id=${slaveId}`);
        const data = await response.json();
        
        let resultText = "";
        for (const [reg, value] of Object.entries(data)) {
            resultText += `${reg}: ${value}\n`;
        }
        
        // Успешный результат (зеленый)
        output.textContent = resultText;
        output.style.color = '#155724';
    } catch (error) {
        // Ошибка (красный)
        output.textContent = `Ошибка: ${error.message}`;
        output.style.color = '#721c24';
    }
}

async function writeRegister() {
    const slaveId = document.getElementById('slave_id').value;
    const register = document.getElementById('register_to_write').value;
    const value = document.getElementById('register_value').value;
    const output = document.getElementById('register_results_output');
    
    if (!slaveId || !register || !value) {
        alert("Все поля должны быть заполнены");
        return;
    }
    
    // Показываем загрузку (серый цвет)
    output.textContent = "Запись регистра...";
    output.style.display = 'block';
    output.style.color = '#666';
    output.style.padding = '10px';
    output.style.borderRadius = '4px';
    
    try {
        const response = await fetch(`/api/modbus/write_register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                slave_id: parseInt(slaveId),
                register_number: parseInt(register),
                value: parseInt(value)
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Успешная запись (зеленый)
            output.textContent = `Успешно записано:\nРегистр ${register}: ${value}\nSlave ID: ${slaveId}`;
            output.style.color = '#155724';
        } else {
            // Ошибка сервера (красный)
            output.textContent = `Ошибка: ${data.detail || 'Неизвестная ошибка'}`;
            output.style.color = '#721c24';
        }
    } catch (error) {
        // Ошибка сети (красный)
        output.textContent = `Ошибка: ${error.message}`;
        output.style.color = '#721c24';
    }
}


function downloadExcelFile() {
    const link = document.createElement('a');
    link.href = '/static/docs/register_map.xlsx';
    link.download = 'register_map.xlsx';
    link.click();
}



function checkViewport() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const orientation = width > height ? "landscape" : "portrait";
    
  //  console.log(`Viewport: ${width}x${height}, ${orientation}`);
  //  console.log(`Device pixel ratio: ${window.devicePixelRatio}`);
    
    // Проверка поддержки анимаций
    const animationSupport = 'animate' in document.createElement('div');
 //   console.log(`CSS Animations supported: ${animationSupport}`);
  }
  
  window.addEventListener('resize', checkViewport);
  checkViewport();




  document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('ExcelModal');
    const modalContent = document.getElementById('excel-modal-content');
    const loader = document.getElementById('modal-loader');
    const closeBtn = document.querySelector('.close');
    const processBtn = document.getElementById('process-excel-btn');
    
   // makeModalDraggable('ExelModal');
    // Открыть модальное окно при клике на кнопку
    processBtn.addEventListener('click', async function() {
        try {
            // Показать лоадер
            modal.style.display = 'block';
            loader.style.display = 'block';
            modalContent.innerHTML = '';
            
            // Запросить HTML с бэкенда
            const response = await fetch('/api/excel/process-register-map/');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const html = await response.text();
            modalContent.innerHTML = html;
            
        } catch (error) {
            console.error('Error:', error);
            modalContent.innerHTML = `
                <div class="error-message">
                    <h3>Error</h3>
                    <p>Failed to load Excel data: ${error.message}</p>
                </div>
            `;
        } finally {
            loader.style.display = 'none';
        }
    });
    
    // Закрыть модальное окно
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
   
});
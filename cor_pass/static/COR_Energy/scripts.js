



            document.addEventListener("DOMContentLoaded", function() {

                fetchEss().then(() => {
                    document.getElementById('State_Of_Сharge').value = initialSocValue;
                    document.getElementById('socSliderValue').textContent = initialSocValue;
                });
                makeModalDraggable('batteryModal');
             //   makeModalDraggable('inverterModal');
                makeModalDraggable('loadSettingsModal');
                makeModalDraggable('GridSettingsModal');
                makeModalDraggable('SolarModal');
            // Получаем элементы модальных окон
                const batteryModal = document.getElementById('batteryModal');
                const inverterModal = document.getElementById('inverterModal');
                const loadModal = document.getElementById('loadSettingsModal');
                const GridModal = document.getElementById('GridSettingsModal');
                const SolarPanelModal = document.getElementById('SolarModal');
                
                // Получаем иконки
                const batteryIcon = document.getElementById('batteryIcon');
                const inverterIcon = document.getElementById('inverterIcon');
                const loadIcon = document.getElementById('loadIcon'); 
                const gridIcon = document.getElementById('power-grid-icon');
                const solarIcon = document.getElementById('SolarBatteryIcon');
              
                // Получаем кнопки закрытия модальных окон 
                const closeBattery = document.getElementById('closeBattery');
                const closeInverter = document.getElementById('closeInverter');
                const closeLoad = document.getElementById('closeLoadSettings');
                const closeGrid = document.getElementById('closeGridSettings');
                const closeSolar = document.getElementById('closeSolarModal');
               
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
                const maxPower = 100000;  // Вт
                const maxWidth = 1300;   // Половина общей ширины (2600 / 2)
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
                const maxWidth = 2000;  // Максимальная ширина индикатора (в SVG)
                const maxPower = 150;   // Максимальная мощность (кВт)
            
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
                const maxPower = 150000; // максимальная мощность для 100%
                
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




    // Функция сброса ползунка
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





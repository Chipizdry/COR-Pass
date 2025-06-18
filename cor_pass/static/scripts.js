



            document.addEventListener("DOMContentLoaded", function() {
                makeModalDraggable('batteryModal');
             //   makeModalDraggable('inverterModal');
                makeModalDraggable('loadSettingsModal');
                makeModalDraggable('GridSettingsModal');
            // Получаем элементы модальных окон
                const batteryModal = document.getElementById('batteryModal');
                const inverterModal = document.getElementById('inverterModal');
                const loadModal = document.getElementById('loadSettingsModal');
                const GridModal = document.getElementById('GridSettingsModal');
                
                // Получаем иконки
                const batteryIcon = document.getElementById('batteryIcon');
                const inverterIcon = document.getElementById('inverterIcon');
                const loadIcon = document.getElementById('loadIcon'); 
                const gridIcon = document.getElementById('power-grid-icon');
              
                // Получаем кнопки закрытия модальных окон 
                const closeBattery = document.getElementById('closeBattery');
                const closeInverter = document.getElementById('closeInverter');
                const closeLoad = document.getElementById('closeLoadSettings');
                const closeGrid = document.getElementById('closeGridSettings');
               
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
                
               
                // Закрытие модальных окон
                closeBattery.onclick = function() {
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
            });
    


   
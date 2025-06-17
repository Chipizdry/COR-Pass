



            document.addEventListener("DOMContentLoaded", function() {
                makeModalDraggable('batteryModal');
             //   makeModalDraggable('inverterModal');
             //   makeModalDraggable('loadSettingsModal');
            // Получаем элементы модальных окон
                const batteryModal = document.getElementById('batteryModal');
                const inverterModal = document.getElementById('inverterModal');
                const loadModal = document.getElementById('loadSettingsModal');
                
                // Получаем иконкиc
                const batteryIcon = document.getElementById('batteryIcon');
                const inverterIcon = document.getElementById('inverterIcon');
                const loadIcon = document.getElementById('loadIcon'); 
              
                // Получаем кнопки закрытия модальных окон 
                const closeBattery = document.getElementById('closeBattery');
                const closeInverter = document.getElementById('closeInverter');
                const closeLoad = document.getElementById('closeLoadSettings');
               
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
            });
    


   
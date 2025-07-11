
async function printLabel(printerIp, templateNumber, content, resultElement = null) {
    if (resultElement) {
        resultElement.textContent = 'Отправка задания на печать...';
        resultElement.style.color = 'black';
    }
    
    const requestData = {
        printer_ip: printerIp,
        labels: [
            {
                model_id: templateNumber,
                content: content,
                uuid: Date.now().toString()  
            }
        ]
    };

    try {
        const response = await fetch('/api/print_labels', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + getToken()
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Unknown error');
        }

        const result = await response.json();
        console.log('Печать успешна:', result);
        
        if (resultElement) {
            resultElement.textContent = `Задание отправлено (IP: ${printerIp}, Шаблон: ${templateNumber})`;
            resultElement.style.color = 'green';
        }
        
        return result;
    } catch (error) {
        console.error('Ошибка:', error);
        
        if (resultElement) {
            resultElement.textContent = 'Ошибка при печати: ' + error.message;
            resultElement.style.color = 'red';
        }
        
        throw error;
    }
}



    // Функция проверки доступности принтера
    async function checkPrinterAvailability(ip = PRINTER_IP) {
        try {
            console.log(`[checkPrinterAvailability] Проверка IP: ${ip}`);
            const response = await fetch(`/api/check_printer?ip=${encodeURIComponent(ip)}`);
            console.log(`[checkPrinterAvailability] HTTP статус: ${response.status}`);

            const data = await response.json();
            console.log(`[checkPrinterAvailability] Ответ от сервера:`, data);

            return data.available;
        } catch (error) {
            console.error('[checkPrinterAvailability] Ошибка запроса:', error);
            return false;
        }
    }
    
    // Функция мониторинга состояния принтера
    function startPrinterMonitoring() {
        const statusElement = document.getElementById('printerStatus');
        const ipInput = document.getElementById('printerIp');

        setInterval(async () => {
            const ip = ipInput ? ipInput.value.trim() : PRINTER_IP;
            console.log(`[startPrinterMonitoring] Текущий IP: ${ip}`);

            const isAvailable = await checkPrinterAvailability(ip);

            console.log(`[startPrinterMonitoring] Статус принтера: ${isAvailable ? 'доступен' : 'недоступен'}`);

            statusElement.textContent = isAvailable ? 'Принтер доступен' : 'Принтер недоступен';
            statusElement.style.color = isAvailable ? 'green' : 'red';
        }, 3000);
    }
    

    // Функция добавления нового устройства
    async function addDevice() {
        const resultElement = document.getElementById('addDeviceResult');
        resultElement.textContent = '';
        
        // Получаем значения из полей формы
        const deviceType = document.getElementById('deviceType').value;
        const deviceId = document.getElementById('deviceId').value;
        const deviceIp = document.getElementById('deviceIp').value;
        const deviceLocation = document.getElementById('deviceLocation').value;
        const deviceInfo = document.getElementById('deviceInformation').value;


        // Проверяем обязательные поля
        if (!deviceType || !deviceId || !deviceIp) {
            resultElement.textContent = 'Пожалуйста, заполните все обязательные поля';
            resultElement.style.color = 'red';
            return;
        }

        // Проверяем валидность ID устройства
        const idNumber = parseInt(deviceId);
        if (isNaN(idNumber) || idNumber < 0 || idNumber > 65535) {
            resultElement.textContent = 'ID устройства должен быть числом от 0 до 65535';
            resultElement.style.color = 'red';
            return;
        }

        // Подготавливаем данные для отправки
        const deviceData = {
            device_class: deviceType,
            device_identifier: deviceId,
            ip_address: deviceIp,
            subnet_mask: "255.255.255.0", // По умолчанию
            gateway: "0.0.0.0", // По умолчанию
            port: 0, // По умолчанию
            comment: deviceInfo || "", 
            location: deviceLocation || "" // Если не указано - пустая строка
        };

        try {
            resultElement.textContent = 'Добавление устройства...';
            resultElement.style.color = 'black';
            
            // Отправляем запрос на сервер
            const response = await fetch('/api/printing_devices/', {
                method: 'POST',
                headers: {
                    'accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + localStorage.getItem('access_token')
                },
                body: JSON.stringify(deviceData)
            });

            if (!response.ok) {
                throw new Error(`Ошибка HTTP: ${response.status}`);
            }

            const result = await response.json();
            console.log('Устройство успешно добавлено:', result);
            resultElement.textContent = 'Устройство успешно добавлено!';
            resultElement.style.color = 'green';
            
            // Очищаем форму
            document.getElementById('deviceType').value = '';
            document.getElementById('deviceId').value = '';
            document.getElementById('deviceIp').value = '';
            document.getElementById('deviceLocation').value = '';
            
            // Закрываем модальное окно через 2 секунды
            setTimeout(() => {
                document.getElementById('addDeviceModal').style.display = 'none';
            }, 2000);
            
        } catch (error) {
            console.error('Ошибка при добавлении устройства:', error);
            resultElement.textContent = 'Произошла ошибка при добавлении устройства: ' + error.message;
            resultElement.style.color = 'red';
        }
    }




 // Функция для получения списка устройств и отображения в таблице
async function loadDevicesList() {
    const devicesListElement = document.getElementById('devicesList');
    devicesListElement.innerHTML = '<p>Загрузка списка устройств...</p>';
    
    try {
       
        const response = await fetch('/api/printing_devices/all', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + getToken()
            }
        });
        if (!response.ok) {
            throw new Error(`Ошибка HTTP: ${response.status}`);
        }
        
        const devices = await response.json();
        
        if (devices.length === 0) {
            devicesListElement.innerHTML = '<p>Устройства не найдены</p>';
            return;
        }
        
        // Создаем HTML для таблицы
        let tableHTML = `
            <table class="devices-table">
                <thead>
                    <tr>
                        <th>Тип</th>
                        <th>Идентификатор</th>
                        <th>IP-адрес</th>
                        <th>Местоположение</th>
                        <th>Комментарий</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Добавляем строки для каждого устройства
        devices.forEach(device => {
            tableHTML += `
                <tr>
                    <td>${device.device_class}</td>
                    <td>${device.device_identifier}</td>
                    <td>${device.ip_address}</td>
                    <td>${device.location || '-'}</td>
                    <td>${device.comment || '-'}</td>
                </tr>
            `;
        });
        
        tableHTML += `
                </tbody>
            </table>
        `;
        
        devicesListElement.innerHTML = tableHTML;
        
    } catch (error) {
        console.error('Ошибка при загрузке списка устройств:', error);
        devicesListElement.innerHTML = `<p style="color: red;">Ошибка при загрузке: ${error.message}</p>`;
    }
}   


// Обработчик для модального окна теста
document.getElementById('sendLabelButton').addEventListener('click', async () => {
    const testResult = document.getElementById('testResult');
    
    // Получаем значения из полей формы
    const printerIp = document.getElementById('printerIp').value.trim();
    const templateId = document.getElementById('template').value;
    const clinicId = document.getElementById('clinicId').value.trim();
    const caseCode = document.getElementById('caseCode').value.trim();
    const sampleNumber = document.getElementById('sampleNumber').value.trim();
    const cassetteNumber = document.getElementById('cassetteNumber').value.trim();
    const glassNumber = document.getElementById('glassNumber').value.trim();
    const staining = document.getElementById('staining').value.trim();
    const hopperNumber = document.getElementById('hopperNumber').value.trim();
    const patientCorId = document.getElementById('patientCorId').value.trim();
    
    // Проверка обязательных полей
    if (!printerIp) {
        testResult.textContent = 'Ошибка: Не указан IP-адрес принтера';
        testResult.style.color = 'red';
        return;
    }
    
    // Проверка валидности номера шаблона
    const templateNumber = parseInt(templateId);
    if (isNaN(templateNumber) || templateNumber < 0 || templateNumber > 65535) {
        testResult.textContent = 'Ошибка: Номер шаблона должен быть числом от 0 до 65535';
        testResult.style.color = 'red';
        return;
    }

    // Формируем строку content из всех параметров
    const content = [
        clinicId,
        caseCode,
        sampleNumber,
        cassetteNumber,
        glassNumber,
        staining,
        hopperNumber,
        patientCorId
    ].join('|');

    // Используем универсальную функцию печати
    await printLabel(printerIp, templateNumber, content, testResult);
});
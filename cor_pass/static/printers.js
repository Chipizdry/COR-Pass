
const PRINTER_IP = "192.168.154.193"; // Здесь вы можете задать или получить IP-адрес



document.getElementById('sendLabelButton').addEventListener('click', async () => {
    const apiUrl = '/api/print_labels'; 
    
    const requestData = {
        labels: [
            {
                model_id: 8,
                content: "FF|S24B0460|A|1|L0|H&E|?|TDAJ92Z7-1983M",
                uuid: Date.now().toString()  
            }
        ]
    };

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Unknown error');
        }

        const result = await response.json();
        console.log('Печать успешна:', result);
        alert('Задание отправлено на принтер');
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при печати: ' + error.message);
    }
});





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
    }, 2000);
}


async function addDevice() {
    // Получаем значения из полей формы
    const deviceType = document.getElementById('deviceType').value;
    const deviceId = document.getElementById('deviceId').value;
    const deviceIp = document.getElementById('deviceIp').value;
    const deviceLocation = document.getElementById('deviceLocation').value;

    // Проверяем обязательные поля
    if (!deviceType || !deviceId || !deviceIp) {
        alert('Пожалуйста, заполните все обязательные поля');
        return;
    }

    // Проверяем валидность ID устройства
    const idNumber = parseInt(deviceId);
    if (isNaN(idNumber) || idNumber < 0 || idNumber > 65535) {
        alert('ID устройства должен быть числом от 0 до 65535');
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
        comment: "", // Пока пустое
        location: deviceLocation || "" // Если не указано - пустая строка
    };

    try {
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
        alert('Устройство успешно добавлено!');
        
        // Закрываем модальное окно и обновляем список устройств
        document.getElementById('addDeviceModal').style.display = 'none';
        // Здесь можно вызвать функцию для обновления списка устройств
        // например: refreshDevicesList();
        
    } catch (error) {
        console.error('Ошибка при добавлении устройства:', error);
        alert('Произошла ошибка при добавлении устройства: ' + error.message);
    }
}


async function fetchDevices() {
    try {
        // Получаем токен из localStorage
        const token = localStorage.getItem('access_token');
        if (!token) {
            throw new Error('Токен доступа не найден');
        }

        const response = await fetch('/api/printing_devices/all?skip=0&limit=100', {
            method: 'GET',
            headers: {
                'accept': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });
        
        // Логируем полный ответ для отладки
        console.log('Полный ответ сервера:', {
            status: response.status,
            statusText: response.statusText,
            headers: Object.fromEntries(response.headers.entries()),
            url: response.url
        });

        if (!response.ok) {
            // Пытаемся получить текст ошибки, если есть
            let errorText = response.statusText;
            try {
                const errorData = await response.json();
                errorText = errorData.detail || JSON.stringify(errorData);
            } catch (e) {
                // Не удалось распарсить JSON с ошибкой
            }
            throw new Error(`Ошибка HTTP ${response.status}: ${errorText}`);
        }
        
        const devices = await response.json();
        console.log('Получен список устройств:', devices);
        displayDevices(devices);
        
        return devices; // Возвращаем данные для возможного дальнейшего использования
    } catch (error) {
        console.error('Ошибка при получении устройств:', error);
        
    }
}

// Функция для отображения устройств в таблице
function displayDevices(devices) {
    const tableBody = document.getElementById("devicesTableBody");
    tableBody.innerHTML = ""; // Очищаем таблицу
    
    devices.forEach(device => {
        const row = document.createElement("tr");
        
        row.innerHTML = `
            <td>${device.device_class || ''}</td>
            <td>${device.device_identifier || ''}</td>
            <td>${device.ip_address || ''}</td>
            <td>${device.subnet_mask || ''}</td>
            <td>${device.gateway || ''}</td>
            <td>${device.port || ''}</td>
            <td>${device.comment || ''}</td>
            <td>${device.location || ''}</td>
        `;
        
        tableBody.appendChild(row);
    });
}
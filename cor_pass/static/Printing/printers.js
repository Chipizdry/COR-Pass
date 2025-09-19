
async function printLabel(printerIp, templateNumber, content, resultElement = null) {
     checkToken();
    if (resultElement) {
        resultElement.textContent = 'Отправка задания на печать...';
        resultElement.style.color = 'black';
        resultElement.style.display = 'block'; // показать элемент
    }

    const requestData = {
        printer_ip: printerIp,
        labels: [
            {
                number_model_id: templateNumber,
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
            resultElement.style.display = 'block'; // показать
            setTimeout(() => {
                resultElement.style.display = 'none';
            }, 3000);
        }

        return result;
    } catch (error) {
        console.error('Ошибка:', error);

        if (resultElement) {
            resultElement.textContent = 'Ошибка при печати: ' + error.message;
            resultElement.style.color = 'red';
            resultElement.style.display = 'block'; // показать
            setTimeout(() => {
                resultElement.style.display = 'none';
            }, 3000);
        }

        throw error;
    }
}


    // Функция проверки доступности принтера
    async function checkPrinterAvailability(ip = PRINTER_IP) {
        try {
            console.log(`[checkPrinterAvailability] Проверка IP: ${ip}`);
            const response = await fetch(`/api/printer/check_printer?ip=${encodeURIComponent(ip)}`);
            console.log(`[checkPrinterAvailability] HTTP статус: ${response.status}`);

            const data = await response.json();
            console.log(`[checkPrinterAvailability] Ответ от сервера:`, data);

            return data.available;
        } catch (error) {
            console.error('[checkPrinterAvailability] Ошибка запроса:', error);
            return false;
        }
    }
    
 

// Функция мониторинга состояния всех принтеров
function startPrinterMonitoring() {
    let currentPrinterIndex = 0;
    
    // Функция для проверки одного принтера
    const checkNextPrinter = async () => {
        if (availablePrinters.length === 0) {
            return;
        }

        // Получаем текущий принтер (с циклическим перебором)
        const printer = availablePrinters[currentPrinterIndex];
        currentPrinterIndex = (currentPrinterIndex + 1) % availablePrinters.length;

        // Находим строку таблицы для этого принтера
        const row = document.querySelector(`tr[data-device-id="${printer.id}"]`);
        if (!row) return;

        // Находим индикатор статуса
        const statusIndicator = row.querySelector('.status-indicator');
        if (!statusIndicator) return;

        try {
            const isAvailable = await checkPrinterAvailability(printer.ip_address);
            
            // Сохраняем статус
            printerStatuses[printer.ip_address] = {
                available: isAvailable,
                lastChecked: new Date()
            };
            
            // Обновляем индикатор
            statusIndicator.style.backgroundColor = isAvailable ? 'green' : 'red';
            statusIndicator.title = `${printer.device_class} (${printer.ip_address})\n` +
                                  `Статус: ${isAvailable ? 'Доступен' : 'Недоступен'}\n` +
                                  `Последняя проверка: ${new Date().toLocaleTimeString()}`;
            
        } catch (error) {
            console.error(`Ошибка проверки принтера ${printer.ip_address}:`, error);
            statusIndicator.style.backgroundColor = 'orange';
            statusIndicator.title = `Ошибка проверки ${printer.ip_address}: ${error.message}`;
        }
    };

    // Запускаем проверку с интервалом
    const intervalId = setInterval(checkNextPrinter, 3000);
    
    // Возвращаем функцию для остановки мониторинга
    return () => clearInterval(intervalId);
}

    // Функция добавления нового устройства
    async function addDevice() {
        checkToken();
        const resultElement = document.getElementById('addDeviceResult');
        resultElement.textContent = '';
    
        // Получаем значения из полей формы (без deviceId)
        const deviceType = document.getElementById('deviceType').value;
        const deviceIp = document.getElementById('deviceIp').value;
        const deviceLocation = document.getElementById('deviceLocation').value;
        const deviceInfo = document.getElementById('deviceInformation').value;
    
        if (!deviceType || !deviceIp) {
            resultElement.textContent = 'Пожалуйста, заполните все обязательные поля';
            resultElement.style.color = 'red';
            return;
        }
    
        try {
            resultElement.textContent = 'Получение списка устройств...';
            resultElement.style.color = 'black';
    
            // Загружаем все текущие устройства
            const allDevicesResponse = await fetch('/api/printing_devices/all', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + getToken()
                }
            });
    
            if (!allDevicesResponse.ok) {
                throw new Error('Не удалось загрузить список устройств');
            }
    
            const devices = await allDevicesResponse.json();
    


            // Проверка на дублирование IP
                const duplicateIp = devices.find(device => device.ip_address === deviceIp);

                if (duplicateIp) {
                    resultElement.textContent = 'Устройство с таким IP уже существует!';
                    resultElement.style.color = 'red';

                    const ipInput = document.getElementById('deviceIp');
                    ipInput.style.border = '2px solid red';

                    setTimeout(() => {
                        ipInput.style.border = '';
                    }, 3000);

                    return;
                }



            // Находим максимальный device_identifier (среди числовых значений)
            let maxId = 0;
            for (const device of devices) {
                const id = parseInt(device.device_identifier);
                if (!isNaN(id) && id > maxId) {
                    maxId = id;
                }
            }
    




            const newDeviceId = (maxId + 1).toString();
    
            // Подготавливаем данные для отправки
            const deviceData = {
                device_class: deviceType,
                device_identifier: newDeviceId,
                ip_address: deviceIp,
                subnet_mask: "255.255.255.0",
                gateway: "0.0.0.0",
                port: 0,
                comment: deviceInfo || "",
                location: deviceLocation || ""
            };
    
            resultElement.textContent = 'Добавление устройства...';
    
            const response = await fetch('/api/printing_devices/', {
                method: 'POST',
                headers: {
                    'accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + getToken()
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
            document.getElementById('deviceIp').value = '';
            document.getElementById('deviceLocation').value = '';
            document.getElementById('deviceInformation').value = '';
    
            setTimeout(() => {
                resultElement.textContent = '';
               
            }, 1500);
    

            setTimeout(() => {
                resultElement.textContent = '';
                document.getElementById('addDeviceModal').style.display = 'none';
            }, 3000);
    
            loadDevicesList(); // Обновить таблицу
    
        } catch (error) {
            console.error('Ошибка при добавлении устройства:', error);
            resultElement.textContent = 'Ошибка при добавлении устройства: ' + error.message;
            resultElement.style.color = 'red';
        }
    }




// Обновленная функция loadDevicesList
async function loadDevicesList() {
    checkToken();
    const devicesListElement = document.getElementById('devicesList');
    if (!devicesListElement) return;

    try {
        devicesListElement.innerHTML = '<p>Загрузка списка устройств...</p>';
        
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
        
        // Сохраняем все устройства для отображения в таблице
        allPrinters = devices;
        
        availablePrinters = devices;
        
        // Обновляем выпадающий список в тестовой форме
        updatePrinterDropdown();
        
        // Создаем таблицу со всеми устройствами
        let tableHTML = `
            <table class="devices-table">
                <thead>
                    <tr>
                        <th>Тип</th>
                        <th>Идентификатор</th>
                        <th>IP-адрес</th>
                        <th>Местоположение</th>
                        <th>Комментарий</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Используем allPrinters вместо devices для отображения всех устройств
        allPrinters.forEach(device => {
            const lastStatus = printerStatuses[device.ip_address];
            const statusColor = lastStatus ? 
                (lastStatus.available ? 'green' : 'red') : 'gray';
            
            tableHTML += `
                <tr data-device-id="${device.id}">
                    <td>${device.device_class}</td>
                    <td>${device.device_identifier}</td>
                    <td><input type="text" class="editable-field ip-address" value="${device.ip_address}" data-original="${device.ip_address}"></td>
                    <td><input type="text" class="editable-field location" value="${device.location || ''}" data-original="${device.location || ''}"></td>
                    <td><input type="text" class="editable-field comment" value="${device.comment || ''}" data-original="${device.comment || ''}"></td>
                    <td class="actions">
                        <button class="action-btn save-btn" onclick="saveDeviceChanges('${device.id}')" title="Сохранить">💾</button>
                        <button class="action-btn delete-btn" onclick="deleteDevice('${device.id}')" title="Удалить">❌</button>
                        <div class="status-indicator" style="background-color: ${statusColor}" 
                             title="${lastStatus ? `Статус: ${lastStatus.available ? 'Доступен' : 'Недоступен'}\nПоследняя проверка: ${lastStatus.lastChecked.toLocaleTimeString()}` : 'Статус неизвестен'}"></div>
                    </td>
                </tr>
            `;
        });
        
        tableHTML += `
                </tbody>
            </table>
        `;
        
        devicesListElement.innerHTML = tableHTML;
        
        return devices;
    } catch (error) {
        console.error('Ошибка при загрузке списка устройств:', error);
        devicesListElement.innerHTML = `<p style="color: red;">Ошибка при загрузке: ${error.message}</p>`;
        throw error;
    }
}

// Функция для сохранения изменений устройства
async function saveDeviceChanges(deviceId) {
    checkToken();
    const row = document.querySelector(`tr[data-device-id="${deviceId}"]`);
    if (!row) return;

    // Получаем все необходимые данные из строки таблицы
    const deviceClass = row.querySelector('td:first-child').textContent;
    const deviceIdentifier = row.querySelector('td:nth-child(2)').textContent;
    const ipAddress = row.querySelector('.ip-address').value;
    const location = row.querySelector('.location').value;
    const comment = row.querySelector('.comment').value;

    // Формируем полный объект данных согласно API
    const deviceData = {
        device_class: deviceClass,
        device_identifier: deviceIdentifier,
        ip_address: ipAddress,
        subnet_mask: "255.255.255.0", // Значение по умолчанию
        gateway: "0.0.0.0", // Значение по умолчанию
        port: 0, // Значение по умолчанию
        comment: comment,
        location: location
    };

    try {
        const response = await fetch(`/api/printing_devices/${deviceId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + getToken()
            },
            body: JSON.stringify(deviceData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Ошибка HTTP: ${response.status}`);
        }

        const result = await response.json();
        console.log('Устройство успешно обновлено:', result);

        // Обновляем оригинальные значения в data-атрибутах
        row.querySelector('.ip-address').dataset.original = ipAddress;
        row.querySelector('.location').dataset.original = location;
        row.querySelector('.comment').dataset.original = comment;

        // Показываем уведомление вместо alert
        showNotification('Изменения успешно сохранены!', 'success');
        updatePrinterDropdown(); // Обновляем список принтеров

    } catch (error) {
        console.error('Ошибка при сохранении изменений:', error);
        
        // Показываем более информативное сообщение об ошибке
        let errorMessage = 'Ошибка при сохранении: ';
        if (error.message.includes('422')) {
            errorMessage += 'Неверные данные. Проверьте введенные значения.';
        } else {
            errorMessage += error.message;
        }
        
        showNotification(errorMessage, 'error');
        
        // Восстанавливаем оригинальные значения
        row.querySelector('.ip-address').value = row.querySelector('.ip-address').dataset.original;
        row.querySelector('.location').value = row.querySelector('.location').dataset.original;
        row.querySelector('.comment').value = row.querySelector('.comment').dataset.original;
    }
}

// Вспомогательная функция для показа уведомлений
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 500);
    }, 3000);
}

// Функция для удаления устройства
async function deleteDevice(deviceId) {
    checkToken();
    if (!confirm('Вы уверены, что хотите удалить это устройство?')) {
        return;
    }

    try {
        const response = await fetch(`/api/printing_devices/${deviceId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + getToken()
            }
        });

        console.log("Ответ:",response);
        if (!response.ok) {
            throw new Error(`Ошибка HTTP: ${response.status}`);
        }

        // Удаляем строку из таблицы
        document.querySelector(`tr[data-device-id="${deviceId}"]`).remove();
        alert('Устройство успешно удалено!');
        updatePrinterDropdown(); // Обновляем список принтеров
        loadDevicesList();
    } catch (error) {
        console.error('Ошибка при удалении устройства:', error);
        alert('Ошибка при удалении: ' + error.message);
    }
}




function sendToPrint() {
    const formData = new FormData();
    formData.append("content", document.getElementById("labelText").value);
  
    fetch(`/api/print_code_label`, {
      method: "POST",
      body: formData
    })
    .then(res => res.json())
    .then(data => alert("Статус: " + data.status));
  }



document.getElementById('sendLabelButton').addEventListener('click', async () => {
    checkToken();
    const testResult = document.getElementById('testResult');

    const printerIp = document.getElementById('printerIp').value.trim();
    const selectedOption = Array.from(document.getElementById('printerIps').options)
        .find(opt => opt.value === printerIp);

    const deviceType = selectedOption ? selectedOption.dataset.type : null;

    if (deviceType === 'scanner_docs') {
        await scanDocument();
        return; // завершаем, чтобы не идти в печать
    }

    // --- иначе это принтер ---
    const hopperNumber = document.getElementById('hopperNumber').value.trim();
    const templateId = document.getElementById('template').value;
    const clinicId = document.getElementById('clinicId').value.trim();
    const caseCode = document.getElementById('caseCode').value.trim();
    const sampleNumber = document.getElementById('sampleNumber').value.trim();
    const cassetteNumber = document.getElementById('cassetteNumber').value.trim();
    const glassNumber = document.getElementById('glassNumber').value.trim();
    const staining = document.getElementById('staining').value.trim();
    const patientCorId = document.getElementById('patientCorId').value.trim();

    const templateNumber = parseInt(templateId);
    if (isNaN(templateNumber) || templateNumber < 0 || templateNumber > 65535) {
        testResult.textContent = 'Ошибка: Номер шаблона должен быть числом от 0 до 65535';
        testResult.style.color = 'red';
        return;
    }

    const content = [
        hopperNumber,
        clinicId,
        caseCode,
        sampleNumber,
        cassetteNumber,
        glassNumber,
        staining,
        patientCorId
    ].join('|');

    console.log("Печать:", content);
    await printLabel(printerIp, templateNumber, content, testResult);
});
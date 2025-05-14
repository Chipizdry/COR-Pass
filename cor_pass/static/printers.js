
const PRINTER_IP = "192.168.154.209"; // Здесь вы можете задать или получить IP-адрес



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
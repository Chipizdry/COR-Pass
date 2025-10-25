

function updatePrinterDropdown() {
    const printerInput = document.getElementById('printerIp');
    const datalist = document.getElementById('printerIps');
    if (!printerInput || !datalist) return;

    if (!Array.isArray(availablePrinters)) {
        console.error('availablePrinters не является массивом:', availablePrinters);
        availablePrinters = [];
    }

    const currentValue = printerInput.value;
    datalist.innerHTML = '';

    if (availablePrinters.length > 0) {
        availablePrinters.forEach(printer => {
            const option = document.createElement('option');
            option.value = printer.ip_address;
            option.textContent = `${printer.device_class} | ${printer.ip_address}${printer.location ? ` (${printer.location})` : ''}`;
            option.dataset.type = printer.device_class;
            datalist.appendChild(option);
        });
    }

    if (currentValue) {
        printerInput.value = currentValue;
    }

    // Обработчик выбора принтера
    printerInput.addEventListener('input', function() {
        const selectedOption = Array.from(datalist.options).find(opt => opt.value === this.value);
        if (selectedOption) {
            const type = selectedOption.dataset.type;
            updateTestModalByType(type);  // ← используем уже готовую функцию
        } else {
            updateTestModalByType(null);  // ничего не выбрано
        }
    });

    // Первичная инициализация
    printerInput.dispatchEvent(new Event('input'));
}




function updateTestModalByType(type) {
    const allGroups = [
        'labelText', 'templateNumber', 'hopperNumberContainer',
        'ClinicCaseNumber', 'GlassCassetteNumber', 'StainingType',
        'scannerContainer', 'sendLabelButton','testResult','StickerPrint',
        'glassNumberForm'
    ];

    allGroups.forEach(id => {
        const el = document.getElementById(id);
        hide(el);
    });

    switch (type) {
        case 'GlassPrinter':
            show(document.getElementById('glassNumberForm'));
            show(document.getElementById('templateNumber'));
            show(document.getElementById('ClinicCaseNumber'));
            show(document.getElementById('GlassCassetteNumber'));
            show(document.getElementById('StainingType'));
            show(document.getElementById('sendLabelButton'));
        break;

        case 'CassetPrinter':
            show(document.getElementById('templateNumber'));
            show(document.getElementById('ClinicCaseNumber'));
            show(document.getElementById('GlassCassetteNumber'));
            show(document.getElementById('StainingType'));
            show(document.getElementById('sendLabelButton'));
            break;

        case 'CassetPrinterHopper':
            show(document.getElementById('templateNumber'));
            show(document.getElementById('hopperNumberContainer'));
            show(document.getElementById('ClinicCaseNumber'));
            show(document.getElementById('GlassCassetteNumber'));
            show(document.getElementById('StainingType'));
            show(document.getElementById('sendLabelButton'));
            hide(document.getElementById('glassNumberForm'));
            break;

        case 'StickerPrinter':
            show(document.getElementById('StickerPrint'));
            show(document.getElementById('labelText'));
            show(document.querySelector('#testModal button[onclick="sendToPrint()"]'));
            break;

        case 'scanner_docs':
            show(document.getElementById('sendLabelButton'));
            hide(document.getElementById('templateNumber'));
            hide(document.getElementById('ClinicCaseNumber'));
            hide(document.getElementById('GlassCassetteNumber'));
            hide(document.getElementById('StainingType'));
            hide(document.getElementById('TestPrinting'));
           
            break;
    }
}



function hide(el) {
    if (el) el.classList.add('hidden');
  }
  
  function show(el) {
    if (el) el.classList.remove('hidden');
  }





async function scanDocument() {
    const testResult = document.getElementById('testResult');
    const scanPreview = document.getElementById('scanPreview');
    const scannerIp = document.getElementById('printerIp').value; // IP из dropdown
    const scannerPort = document.getElementById('scannerPort')?.value || 8080;

    if (!scannerIp) {
        testResult.textContent = 'Выберите сканер из списка!';
        testResult.style.color = 'red';
        scanPreview.style.display = 'none';
        hide(document.getElementById('scannerContainer'));
        return;
    }

    // Показываем статус процесса
    show(testResult);
    testResult.textContent = 'Выполняется сканирование...';
    testResult.style.color = 'black';
    scanPreview.style.display = 'none';
    hide(document.getElementById('scannerContainer'));

    try {
        const response = await fetch(
            `/api/scanner/scan?scanner_ip=${encodeURIComponent(scannerIp)}&scanner_port=${scannerPort}`, 
            {
                method: 'GET',
                headers: {
                    'Authorization': 'Bearer ' + getToken()
                }
            }
        );

        if (!response.ok) {
            throw new Error(`Ошибка HTTP: ${response.status}`);
        }

        // Превращаем ответ (JPEG) в объект URL для <img>
        console.log('Запрос на сканирование', scannerIp, scannerPort);
        const blob = await response.blob();
        console.log('Размер blob:', blob.size);
        const url = URL.createObjectURL(blob);

        // Показываем скан и контейнер
        scanPreview.src = url;
        scanPreview.style.display = 'block';
    
        show(document.getElementById('scannerContainer'));
        testResult.textContent = 'Сканирование завершено!';
        testResult.style.color = 'green';
    } catch (error) {
        console.error('Ошибка при сканировании:', error);
        testResult.textContent = 'Ошибка сканирования: ' + error.message;
        testResult.style.color = 'red';
        scanPreview.style.display = 'none';
        hide(document.getElementById('scannerContainer'));
    }
}
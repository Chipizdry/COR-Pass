


async function startMonitoringAxioma(objectData) {
    const INTERVAL = 2000; // интервал между циклами
    const INVERTER_MAX_POWER = 80000; // 80 кВт
    setDeviceVisibility("Generator", "hidden"); 

    while (true) {
        console.log("---- Цикл обновления Axioma ----");
        try {
           
          
            const host = objectData.ip_address;
            const port = objectData.port;
            const slave = objectData.slave_id || objectData.slave || 1;
            const object_id = objectData.id;
            const protocol = objectData.protocol;

            switch (protocol) {
                case "modbus_over_tcp":
                  

                    break;

                case "COR-Bridge":
                   
                    break;

                default:
                    console.warn("Неизвестный протокол Axioma:", protocol);
                    return; // выход из функции
            }

        } catch (err) {
            console.error("Ошибка мониторинга Axioma:", err);
        }

        await new Promise(resolve => setTimeout(resolve, INTERVAL));
    }
}


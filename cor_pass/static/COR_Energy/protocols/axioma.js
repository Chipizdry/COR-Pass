const deviceId = "COR-B0B21CA3435C";
let axiomaWS = null;

async function startMonitoringAxioma(objectData) {
    const INTERVAL = 2000;
    setDeviceVisibility("Generator", "hidden");

    const protocol = objectData.protocol;

    switch (protocol) {

        case "modbus_over_tcp":
            // старый polling (если понадобится)
            while (true) {
                console.log("---- Цикл обновления Axioma (TCP) ----");
                await new Promise(r => setTimeout(r, INTERVAL));
            }
            break;

        case "COR-Bridge":
            console.log("🚀 Запуск COR-Bridge WS мониторинга");
            startAxiomaCORBridgeWS(objectData);
            break;

        default:
            console.warn("Неизвестный протокол Axioma:", protocol);
    }
}

function hexToAscii(hex) {
    if (!hex || typeof hex !== "string") return "";

    let result = "";
    for (let i = 0; i < hex.length; i += 2) {
        const byte = parseInt(hex.substr(i, 2), 16);
        if (!isNaN(byte)) {
            result += String.fromCharCode(byte);
        }
    }
    return result;
}






function startAxiomaCORBridgeWS(objectData) {
    const deviceId = "COR-B0B21CA3435C";

    console.log("🚀 Инициализация Axioma COR-Bridge WS", { deviceId });

    if (!deviceId) {
        console.error("❌ device_id не задан для COR-Bridge");
        return;
    }

    const wsUrl =
        `wss://dev-corid.cor-medical.ua/dev-modbus/responses` +
        `?device_id=${deviceId}`;

    console.log("🌐 WS URL:", wsUrl);

    // защита от повторного запуска
    if (axiomaWS && axiomaWS.readyState === WebSocket.OPEN) {
        console.warn("⚠️ WS уже запущен");
        return;
    }

    axiomaWS = new WebSocket(wsUrl);

    axiomaWS.onopen = () => {
        console.log("✅ Axioma COR-Bridge WS подключён");
    };

    axiomaWS.onmessage = (event) => {
    console.log("📩 WS сообщение получено:", event.data);

    try {
        const raw = JSON.parse(event.data);
        console.log("🧩 WS JSON распарсен:", raw);

        const hex = raw?.data?.hex_response;

        if (!hex) {
            console.warn("⚠️ Нет data.hex_response в сообщении", raw);
            return;
        }

        console.log("🔢 hex_response:", hex);

        const parsed = parseQPIGS(hex);

        if (!parsed) {
            console.warn("⚠️ QPIGS не распарсен");
            return;
        }

        console.log("🔍 QPIGS parsed:", parsed);

        window.lastData = {
            ...window.lastData,

            battery1Voltage: parsed.batteryVoltage,
            battery1SOC: parsed.batterySOC,
            battery1Current: parsed.batteryChargeCurrent,
            battery1Temperature: parsed.inverterTemp,

            outputVoltage: parsed.outputVoltage,
            outputFrequency: parsed.outputFrequency,
            outputPower: parsed.outputActivePower,
            loadPercent: parsed.loadPercent,

            pvVoltage: parsed.pvVoltage,
            pvCurrent: parsed.pvChargeCurrent
        };

        console.log("📊 lastData обновлён:", window.lastData);
        updateUIByData(window.lastData);

    } catch (e) {
        console.error("❌ Ошибка обработки WS:", e, event.data);
    }
};


    axiomaWS.onerror = (err) => {
        console.error("❌ Axioma WS ошибка:", err);
    };

    axiomaWS.onclose = (e) => {
        console.warn("🔌 Axioma WS закрыт", {
            code: e.code,
            reason: e.reason,
            wasClean: e.wasClean
        });

        axiomaWS = null;

        console.log("⏳ Переподключение через 3 секунды...");
        setTimeout(() => startAxiomaCORBridgeWS(objectData), 3000);
    };
}

function stopAxiomaWS() {
    if (axiomaWS) {
        console.log("🛑 Остановка Axioma WS");
        axiomaWS.close();
        axiomaWS = null;
    }
}


function parseQPIGS(hexResponse) {
    console.log("➡️ parseQPIGS вход:", hexResponse);

    const ascii = hexToAscii(hexResponse).trim();
    console.log("🔤 ASCII:", ascii);

    if (!ascii.startsWith("(")) {
        console.warn("❌ Не QPIGS:", ascii);
        return null;
    }

    const clean = ascii.replace(/[()]/g, "");
    const parts = clean.split(/\s+/);

    console.log("🧩 QPIGS parts:", parts);

    if (parts.length < 17) {
        console.warn("❌ Недостаточно полей QPIGS:", parts.length, parts);
        return null;
    }

    const result = {
        gridVoltage: parseFloat(parts[0]),
        gridFrequency: parseFloat(parts[1]),
        outputVoltage: parseFloat(parts[2]),
        outputFrequency: parseFloat(parts[3]),
        outputApparentPower: parseInt(parts[4]),
        outputActivePower: parseInt(parts[5]),
        loadPercent: parseInt(parts[6]),
        busVoltage: parseInt(parts[7]),
        batteryVoltage: parseFloat(parts[8]),
        batteryChargeCurrent: parseInt(parts[9]),
        batterySOC: parseInt(parts[10]),
        inverterTemp: parseInt(parts[11]),
        pvChargeCurrent: parseInt(parts[12]),
        pvVoltage: parseFloat(parts[13]),
        batteryVoltageSCC: parseFloat(parts[14]),
        batteryDischargeCurrent: parseInt(parts[15]),
        statusBits: parts[16]
    };

    console.log("✅ QPIGS результат:", result);
    return result;
}

// hex_response -> QFLAG парсер
function parseQFLAG(hexResponse) {
    if (!hexResponse) return null;

    const ascii = hexToAscii(hexResponse).trim();
    console.log("🔤 ASCII QFLAG:", ascii);

    // Ожидаем что ASCII будет типа "EAKUVXYZ ..." или "(EAKUVXYZ)<cr>"
    // убираем скобки и <cr>
    const clean = ascii.replace(/[()\r\n]/g, "");
    if (!clean.startsWith("E") && !clean.startsWith("D")) {
        console.warn("❌ Не похоже на QFLAG:", clean);
        return null;
    }

    // QFLAG по протоколу: ExxxDxxx
    const flags = {
        A: clean.includes("A"), // Enable/disable silence buzzer
        B: clean.includes("B"), // Enable/Disable overload bypass
        J: clean.includes("J"), // Enable/Disable power saving
        K: clean.includes("K"), // LCD escape after 1min
        U: clean.includes("U"), // Overload restart
        V: clean.includes("V"), // Over temperature restart
        X: clean.includes("X"), // Backlight
        Y: clean.includes("Y"), // Alarm on primary source interrupt
        Z: clean.includes("Z"), // Fault code record
    };

    console.log("✅ QFLAG parsed:", flags);
    return flags;
}



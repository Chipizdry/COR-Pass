

let axiomaWS = null;
 const INVERTER_MAX_POWER = 11000;
 
async function startMonitoringAxioma(objectData) {
    const INTERVAL = 1000;

    setDeviceVisibility("Generator", "hidden");

    switch (objectData.protocol) {

        case "modbus_over_tcp":
            while (true) {
                await new Promise(r => setTimeout(r, INTERVAL));
            }
            break;

        case "COR-Bridge":
            console.log("🚀 Запуск COR-Bridge WS мониторинга");

            const corBridgeId = objectData.cor_bridges?.[0];

            if (!corBridgeId) {
                console.error("❌ У объекта нет cor_bridges");
                return;
            }

            const deviceId = await resolveCORBridgeDeviceId(corBridgeId);
            console.log("🔍 Полученный device_id:", deviceId);

            if (!deviceId) {
                console.error("❌ Не удалось получить device_id");
                return;
            }

            startAxiomaCORBridgeWS(deviceId);
            break;

        default:
            console.warn("Неизвестный протокол Axioma:", objectData.protocol);
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


/*
function startAxiomaCORBridgeWS(objectData) {
    const deviceId = "COR-B0B21CA3435C";
    console.log("🚀 Инициализация Axioma COR-Bridge WS", { deviceId });

    if (!deviceId) {
        console.error("❌ device_id не задан для COR-Bridge");
        return;
    }

    const wsUrl = `wss://dev-corid.cor-medical.ua/dev-modbus/responses?device_id=${deviceId}`;
    console.log("🌐 WS URL:", wsUrl);

    if (axiomaWS && axiomaWS.readyState === WebSocket.OPEN) {
        console.warn("⚠️ WS уже запущен");
        return;
    }

    axiomaWS = new WebSocket(wsUrl);

    axiomaWS.onopen = () => console.log("✅ Axioma COR-Bridge WS подключён");

    axiomaWS.onmessage = (event) => {
        console.log("📩 WS сообщение получено:", event.data);

        try {
            const raw = JSON.parse(event.data);
           // console.log("🧩 WS JSON распарсен:", raw);

            const hex = raw?.data?.hex_response;
            if (!hex) {
                console.warn("⚠️ Нет data.hex_response в сообщении", raw);
                return;
            }

          //  console.log("🔢 hex_response:", hex);

            // Универсальный парсер
            const parsed = parseAxiomaHex(hex);

            if (!parsed) {
                console.warn("⚠️ Данные не распознаны");
                return;
            }

            // Обновляем lastData
            window.lastData = { ...window.lastData, ...parsed };
            console.log("📊 lastData обновлён:", window.lastData);




            updateUIByData(window.lastData);

        } catch (e) {
            console.error("❌ Ошибка обработки WS:", e, event.data);
        }
    };

    axiomaWS.onerror = (err) => console.error("❌ Axioma WS ошибка:", err);

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

*/



function startAxiomaCORBridgeWS(deviceId) {
   
     console.log("🚀 Инициализация Axioma COR-Bridge WS", { deviceId });

    if (!deviceId) {
        console.error("❌ device_id не задан");
        return;
    }

    const wsUrl =
        `wss://dev-corid.cor-medical.ua/dev-modbus/responses?device_id=${deviceId}`;

    console.log("🌐 WS URL:", wsUrl);

    if (axiomaWS && axiomaWS.readyState === WebSocket.OPEN) {
        console.warn("⚠️ WS уже запущен");
        return;
    }

    axiomaWS = new WebSocket(wsUrl);

    axiomaWS.onopen = () =>
        console.log("✅ Axioma COR-Bridge WS подключён");

    axiomaWS.onmessage = (event) => {
        console.log("📩 WS сообщение получено:", event.data);

        try {
            const raw = JSON.parse(event.data);
           // console.log("🧩 WS JSON распарсен:", raw);

            const hex = raw?.data?.hex_response;
            if (!hex) {
                console.warn("⚠️ Нет data.hex_response в сообщении", raw);
                return;
            }

          //  console.log("🔢 hex_response:", hex);

            // Универсальный парсер
            const parsed = parseAxiomaHex(hex);

            if (!parsed) {
                console.warn("⚠️ Данные не распознаны");
                return;
            }

            // Обновляем lastData
            window.lastData = { ...window.lastData, ...parsed };
            console.log("📊 lastData обновлён:", window.lastData);




            updateUIByData(window.lastData);

        } catch (e) {
            console.error("❌ Ошибка обработки WS:", e, event.data);
        }
    };

    axiomaWS.onerror = (err) => console.error("❌ Axioma WS ошибка:", err);

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

/**
 * Универсальный парсер для разных типов данных
 */

/*
function parseAxiomaHex(hexResponse) {
    if (!hexResponse) return null;

    const ascii = hexToAscii(hexResponse).trim();
    console.log("🔤 ASCII вход:", ascii);

    // Чистим управляющие символы
    const clean = ascii.replace(/[()\r\n]/g, "");

    // Определяем тип данных
    if (clean.startsWith("E") || clean.startsWith("D")) {
        // QFLAG
        return parseQFLAG(clean);
    } else if (ascii.startsWith("(")) {
        // QPIGS
        return parseQPIGS(hexResponse);
    } else {
        console.warn("❌ Неизвестный формат данных:", clean);
        return null;
    }
}
*/


function parseAxiomaHex(hexResponse) {
    if (!hexResponse) return null;

    const ascii = hexToAscii(hexResponse).trim();
    console.log("🔤 ASCII вход:", ascii);

    const clean = ascii.replace(/[()\r\n\x03\x19]/g, "").trim();
    const parts = clean.split(/\s+/);

    // ---------- QFLAG ----------
    if (/^[ED][A-Z]/.test(clean)) {
        return parseQFLAG(clean);
    }

    // ---------- QPIGS ----------
    // Признак: первые два поля — числа с точкой
    if (
        parts.length >= 17 &&
        !isNaN(parseFloat(parts[0])) &&
        !isNaN(parseFloat(parts[1])) &&
        parts[0].includes(".")
    ) {
        return parseQPIGS(hexResponse);
    }

    // ---------- QPGSn ----------
    // Признак: первый символ 0/1 + серийник
    if (
        parts.length >= 18 &&
        (parts[0] === "0" || parts[0] === "1") &&
        /^[A-Z0-9]+$/i.test(parts[1])
    ) {
        return parseQPGS(parts);
    }

    console.warn("❌ Неизвестный формат данных:", clean);
    return null;
}


/**
 * Парсер QFLAG
 */
function parseQFLAG(ascii) {
    // Пример входа: EADJDKUVXYZ
    // E — включено, D — выключено, буквы после них — что именно

    if (!ascii || ascii.length < 2) return null;

    const flagsMap = {
        A: "silenceBuzzer",
        B: "overloadBypass",
        J: "powerSaving",
        K: "lcdEscape",
        U: "overloadRestart",
        V: "overTempRestart",
        X: "backlight",
        Y: "alarmOnPrimaryInterrupt",
        Z: "faultCodeRecord"
    };

    const result = {};

    // Берём последовательность после E или D
    const regex = /([ED])([A-Z])/g;
    let match;
    while ((match = regex.exec(ascii)) !== null) {
        const status = match[1] === "E"; // E = true, D = false
        const letter = match[2];
        if (flagsMap[letter]) result[flagsMap[letter]] = status;
    }

    console.log("✅ QFLAG parsed:", result);
    return result;
}

/**
 * Парсер QPIGS (оставлен без изменений)
 */
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

    const apparentPower = parseFloat(parts[4]); // VA

    const outputVoltage = parseFloat(parts[2]) || 1; // V, защита от 0
    const outputCurrent = apparentPower / outputVoltage; // A

    const result = {
        inputVoltage: parseFloat(parts[0]),
        inputFrequency: parseFloat(parts[1]),
        outputVoltage: outputVoltage,
        outputFrequency: parseFloat(parts[3]),
        outputApparentPower: apparentPower,
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
        statusBits: parts[16],
        outputCurrent: outputCurrent
    };

    console.log("✅ QPIGS результат:", result);


     // --- Добавляем обновление индикатора нагрузки ---
    if ( result.outputActivePower != null) {
        const INVERTER_MAX_POWER = 11000; // можно вынести глобально
        updatePowerByName(
            "Load",
            PowerToIndicator(result.outputActivePower, INVERTER_MAX_POWER)
        );
        const loadIndicatorLabel = document.querySelector("#loadIndicatorLabel");
        if (loadIndicatorLabel) {
            loadIndicatorLabel.textContent = formatPowerLabel(result.outputActivePower, "load");
        }
    }

  

 // --- АКБ ---
const chargeCurrent = Number(result.batteryChargeCurrent) || 0;

const dischargeCurrent = Number(result.batteryDischargeCurrent) || 0;

const batteryVoltage = Number(result.batteryVoltage) || 0;
const batteryCurrent = chargeCurrent > 0 ? -chargeCurrent : dischargeCurrent;
let inputPower = result.apparentPower || 0;

result.batteryCurrent = batteryCurrent;
let batteryTotalPower = 0;

if (chargeCurrent >0) {
    batteryTotalPower = -batteryVoltage * chargeCurrent;

    if(result.inputVoltage !== 0) {
        inputPower = apparentPower + Math.abs(batteryTotalPower);
    }


} else if (dischargeCurrent > 0) {
    batteryTotalPower = batteryVoltage * dischargeCurrent;

    if(result.inputVoltage !== 0) {
        inputPower = apparentPower - Math.abs(batteryTotalPower);
    }


}
 if(result.inputVoltage == 0) {inputPower = 0;}
result.inputPower = inputPower;

if (!isFinite(batteryTotalPower)) {
    batteryTotalPower = 0;
}


result.batteryTotalPower = batteryTotalPower;
 updateBatteryFill(result.batterySOC);
// UI
if (result.batteryTotalPower != null) {
    const INVERTER_MAX_POWER = 11000;
    updatePowerByName( "Battery", PowerToIndicator(result.batteryTotalPower,  INVERTER_MAX_POWER ) );
     batteryFlowLabel.textContent = formatPowerLabel(result.batteryTotalPower, "battery");
    console.log("🔋 batteryTotalPower:", result.batteryTotalPower);

}



if (result.inputPower != null) {
    const INVERTER_MAX_POWER = 11000;
    updatePowerByName("Grid", PowerToIndicator(result.inputPower, INVERTER_MAX_POWER));
    networkFlowLabel.textContent = formatPowerLabel((result.inputPower), "grid");
}

    return result;
}




function parseQPGS(parts) {
    console.log("➡️ parseQPGS parts:", parts);

    const result = {
        parallelExist: parts[0] === "1",
        serialNumber: parts[1],
        workMode: parts[2],
        faultCode: parseInt(parts[3]),

        gridVoltage: parseFloat(parts[4]),
        gridFrequency: parseFloat(parts[5]),

        outputVoltage: parseFloat(parts[6]),
        outputFrequency: parseFloat(parts[7]),

        outputApparentPower: parseInt(parts[8]),
        outputActivePower: parseInt(parts[9]),
        loadPercent: parseInt(parts[10]),

        batteryVoltage: parseFloat(parts[11]),
        batteryChargeCurrent: parseInt(parts[12]),
        batterySOC: parseInt(parts[13]),

        pvVoltage: parseFloat(parts[14]),
        totalChargeCurrent: parseInt(parts[15]),

        totalOutputApparentPower: parseInt(parts[16]),
        totalOutputActivePower: parseInt(parts[17]),
        totalLoadPercent: parseInt(parts[18]),

        inverterStatusBits: parts[19],

        outputMode: parseInt(parts[20]),          // T
        chargerPriority: parseInt(parts[21]),     // U

        maxChargerCurrent: parseInt(parts[22]),   // VV
        maxChargerRange: parseInt(parts[23]),     // WW
        maxACChargerCurrent: parseInt(parts[24]), // ZZ

        pvChargeCurrent: parseInt(parts[25]),     // XX
        batteryDischargeCurrent: parseInt(parts[26]) // YYY
    };

    console.log("✅ QPGS parsed:", result);

   
    return result;
}





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

            const cmd = raw?.data?.cmd;
            const hex = raw?.data?.hex_response;

            if (!cmd || !hex) {
                console.warn("⚠️ Нет cmd или hex_response", raw);
            setIconStatus("Grid", "offline"); 
            setIconStatus("Battery", "offline");
            setIconStatus("Inverter", "offline");
            setIconStatus("Load", "offline");
            setIconStatus("Solar", "offline"); 
            setDeviceVisibility("ErrorIcon", "visible");

                return;
            }

            const parsed = parseAxiomaByCmd(cmd, hex);

          

            if (!parsed) {
                console.warn("⚠️ Данные не распознаны");
                return;
            }

            window.lastData = { ...window.lastData, ...parsed };
            console.log("📊 lastData обновлён:", window.lastData);

            updateUIByData(window.lastData);
              // OFFLINE — бледно-серый
              //  setIconStatus("Grid", "offline");

              //setIconStatus("Grid", "normal");
              setDeviceVisibility("ErrorIcon", "hidden");  

                // Авария — красный
                //setIconStatus("Battery", "alarm");

                // Предупреждение — оранжевый
                //setIconStatus("Inverter", "warning");


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

function parseAxiomaByCmd(cmd, hexResponse) {

    const ascii = hexToAscii(hexResponse)
        .replace(/[()\r\n\x03\x19]/g, "")
        .trim();

    // ✅ Все команды QPGS, QPGS0, QPGS1... идут в один парсер
    if (cmd.startsWith("QPGS")) {
        return parseQPGSn(cmd, ascii);
    }

    switch (cmd) {

        case "QPIGS":
            return parseQPIGS(hexResponse);

        case "QFLAG":
            return parseQFLAG(ascii);

        case "QPIWS":
            return parseQPIWS(ascii);    

        default:
            console.warn("❌ Неизвестная команда:", cmd);
            return null;
    }
}
/**
 * Парсер QFLAG
 */
function parseQFLAG(hexOrAscii) {
    if (!hexOrAscii) return null;

    // Если пришла hex-строка — конвертируем в ASCII
    let ascii;
    if (/^[0-9A-Fa-f]+$/.test(hexOrAscii.replace(/\s/g, ''))) {
        ascii = '';
        for (let i = 0; i < hexOrAscii.length; i += 2) {
            const hexByte = hexOrAscii.substr(i, 2);
            if (hexByte.trim() === '') continue;
            ascii += String.fromCharCode(parseInt(hexByte, 16));
        }
    } else {
        ascii = hexOrAscii;
    }

    // Расшифровка всех флагов QFLAG
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
    let currentState = null;

    // Убираем скобки, пробелы и символ конца строки
    ascii = ascii.replace(/[()\s\r\n]/g, "").trim();

    for (let i = 0; i < ascii.length; i++) {
        const ch = ascii[i].toUpperCase();

        if (ch === "E") {
            currentState = true;  // все последующие буквы включены
        } 
        else if (ch === "D") {
            currentState = false; // все последующие буквы выключены
        }
        else if (flagsMap[ch] && currentState !== null) {
            result[flagsMap[ch]] = currentState;
        }
    }

    console.log("✅ QFLAG parsed:", result);
    return result;
}

function parseQPGSn(cmd, asciiResponse) {

    // cmd может быть "QPGS" или "QPGS0"
    let unitIndex = null;

    if (cmd.length === 5) {
        unitIndex = parseInt(cmd.replace("QPGS", ""), 10);
    }

    const clean = asciiResponse
        .replace(/[()\r\n]/g, "")
        .trim();

    const parts = clean.split(/\s+/);

    if (parts.length < 18) {
        console.warn("❌ Недостаточно полей QPGS:", parts.length, parts);
        return null;
    }

    const result = {
        unit: unitIndex, // null если просто QPGS

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
        totalOutputActivePower: parseInt(parts[17])
    };

    // Полный пакет (27 полей)
    if (parts.length >= 27) {

        result.totalLoadPercent = parseInt(parts[18]);
        result.inverterStatusBits = parts[19];

        result.outputMode = parseInt(parts[20]);
        result.chargerPriority = parseInt(parts[21]);

        result.maxChargerCurrent = parseInt(parts[22]);
        result.maxChargerRange = parseInt(parts[23]);
        result.maxACChargerCurrent = parseInt(parts[24]);

        result.pvChargeCurrent = parseInt(parts[25]);
        result.batteryDischargeCurrent = parseInt(parts[26]);
    }

    console.log(`✅ ${cmd} parsed (${parts.length} fields):`, result);

    return result;
}


/**
 * Парсер QPIWS — Device Warning Status inquiry
 * Возвращает битовую маску предупреждений a0–a31
 */
function parseQPIWS(asciiResponse) {

    if (!asciiResponse) return null;

    // Убираем скобки, CR/LF и мусор
    const clean = asciiResponse
        .replace(/[()\r\n]/g, "")
        .trim();

    // Ответ должен быть 32 символа "0/1"
    if (clean.length < 32) {
        console.warn("❌ QPIWS: недостаточно бит:", clean.length, clean);
        return null;
    }

    // Берём первые 32 бита
    const bits = clean.substring(0, 32).split("");

    // Таблица предупреждений по документации
    const warningsMap = [
        { bit: 0,  name: "reserved0", description: "Reserved" },

        { bit: 1,  name: "inverterFault", description: "Inverter fault" },
        { bit: 2,  name: "busOverFault", description: "Bus Over Fault" },
        { bit: 3,  name: "busUnderFault", description: "Bus Under Fault" },
        { bit: 4,  name: "busSoftFail", description: "Bus Soft Fail Fault" },

        { bit: 5,  name: "lineFail", description: "LINE_FAIL Warning" },
        { bit: 6,  name: "opvShort", description: "OPVShort Warning" },

        { bit: 7,  name: "inverterVoltageLow", description: "Inverter voltage too low" },
        { bit: 8,  name: "inverterVoltageHigh", description: "Inverter voltage too high" },

        { bit: 9,  name: "overTemperature", description: "Over temperature" },
        { bit: 10, name: "fanLocked", description: "Fan locked" },
        { bit: 11, name: "batteryVoltageHigh", description: "Battery voltage high" },

        { bit: 12, name: "batteryLowAlarm", description: "Battery low alarm" },

        { bit: 13, name: "reserved13", description: "Reserved" },

        { bit: 14, name: "batteryUnderShutdown", description: "Battery under shutdown" },

        { bit: 15, name: "reserved15", description: "Reserved" },

        { bit: 16, name: "overload", description: "Over load" },

        { bit: 17, name: "eepromFault", description: "Eeprom fault" },

        { bit: 18, name: "inverterOverCurrent", description: "Inverter Over Current Fault" },
        { bit: 19, name: "inverterSoftFail", description: "Inverter Soft Fail Fault" },
        { bit: 20, name: "selfTestFail", description: "Self Test Fail Fault" },

        { bit: 21, name: "opDcVoltageOver", description: "OP DC Voltage Over Fault" },
        { bit: 22, name: "batteryOpen", description: "Bat Open Fault" },
        { bit: 23, name: "currentSensorFail", description: "Current Sensor Fail Fault" },
        { bit: 24, name: "batteryShort", description: "Battery Short Fault" },

        { bit: 25, name: "powerLimit", description: "Power limit Warning" },
        { bit: 26, name: "pvVoltageHigh", description: "PV voltage high Warning" },

        { bit: 27, name: "mpptOverloadFault", description: "MPPT overload fault" },
        { bit: 28, name: "mpptOverloadWarning", description: "MPPT overload warning" },

        { bit: 29, name: "batteryTooLowToCharge", description: "Battery too low to charge" },

        { bit: 30, name: "reserved30", description: "Reserved" },
        { bit: 31, name: "reserved31", description: "Reserved" }
    ];

    // Формируем результат
    const result = {
        rawBits: clean,
        activeWarnings: [],
        activeFaults: []
    };

    // a1 определяет Fault/Warning для некоторых битов
    const inverterFaultMain = bits[1] === "1";

    warningsMap.forEach(item => {

        if (bits[item.bit] === "1") {

            // По документации: bits 9,10,11,16 зависят от a1
            let type = "warning";

            if ([9,10,11,16].includes(item.bit)) {
                type = inverterFaultMain ? "fault" : "warning";
            }

            // Остальные жёстко Fault
            if ([1,2,3,4,7,8,18,19,20,21,22,23,24].includes(item.bit)) {
                type = "fault";
            }

            const entry = {
                bit: item.bit,
                name: item.name,
                description: item.description,
                type
            };

            if (type === "fault") {
                result.activeFaults.push(entry);
            } else {
                result.activeWarnings.push(entry);
            }
        }
    });

    console.log("✅ QPIWS parsed:", result);

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

        setIconStatus("Grid", "normal");
        setIconStatus("Battery", "normal");
        setIconStatus("Inverter", "normal");
        setIconStatus("Load", "normal");
        setIconStatus("Solar", "normal");
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

if(chargeCurrent === 0 && dischargeCurrent ===0) {
    batteryTotalPower = 0;
    inputPower = apparentPower;
}

 if(result.inputVoltage == 0) {inputPower = 0;}
result.inputPower = inputPower;


// --- Input current ---
let inputCurrent = 0;
if (result.inputVoltage > 0 && isFinite(result.inputPower)) {
    inputCurrent = result.inputPower / result.inputVoltage;
}
result.inputCurrent = inputCurrent;


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



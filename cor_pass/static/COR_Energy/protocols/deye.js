
async function startMonitoringDeye(objectData) {
    const INTERVAL = 2000; // интервал между циклами
   
    while (true) {
        console.log("---- Цикл обновления Deye ----");

        try {
            let gridData, solarData, genData, battData;
          
            const host = objectData.ip_address; 
            const port = objectData.port;
            const slave = objectData.slave || 1;  // если slave нет в базе — ставим 1
            const protocol = objectData.protocol;

            switch (protocol) {
                case "modbus_tcp":
                    gridData  = await readInverterGridRegisters(host, port, slave);
                    solarData = await readSunPanelRegisters(host, port, slave);
                    genData   = await readGeneratorRegisters(host, port, slave);
                    battData  = await readBatteryRegisters(host, port, slave);
                /*
                    updatePowerByName("Battery",95);
                    updatePowerByName("Generator", 15);
                    updatePowerByName("Grid", -65);
                    updatePowerByName("Solar", 75);
                    updatePowerByName("Load", 35);
                    updateBatteryFill(55);  */
                    break;

                case "COR-Bridge":
                    gridData  = await readInverterGridWS(host, port, slave);
                    solarData = await readSunPanelWS(host, port, slave);
                    genData   = await readGeneratorWS(host, port, slave);
                    battData  = await readBatteryWS(host, port, slave);
                    break;

                default:
                    console.warn("Неизвестный протокол Deye:", protocol);
                    return; // выход из функции
            }

            // Обновляем UI
            if (gridData) updatePowerByName("Grid", gridData.totalPower);
            if (solarData) updatePowerByName("Solar", solarData.PV1InputPower);
            if (genData) updatePowerByName("Generator", genData.GenTotalPower);
            if (battData) {
                updatePowerByName("Battery", battData.battery1Power);
                updateBatteryFill(battData.battery1SOC);
            }

        } catch (err) {
            console.error("Ошибка мониторинга Deye:", err);
        }

        await new Promise(resolve => setTimeout(resolve, INTERVAL));
    }
}









async function readDeyeRegisters(host, port, slave) {
const results = {};

// Первый блок: напряжения и мощности фаз (598-609)
try {
    const resp1 = await fetch(`/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=598&count=12&func=3`, {
        headers: { 'accept': 'application/json' }
    });
    const data1 = await resp1.json();
    console.log("Данные первого блока:", data1); 
    if (data1.ok && data1.data && data1.data.length === 12) {
            results.phaseVoltageA = data1.data[0] * 0.1;
            results.phaseVoltageB = data1.data[1] * 0.1;
            results.phaseVoltageC = data1.data[2] * 0.1;
            results.lineVoltageAB = data1.data[3] * 0.1;
            results.lineVoltageBC = data1.data[4] * 0.1;
            results.lineVoltageCA = data1.data[5] * 0.1;

            results.powerA = data1.data[6];
            results.powerB = data1.data[7];
            results.powerC = data1.data[8];

            results.totalPower = data1.data[9];
            results.totalApparentPower = data1.data[10];
            results.gridFrequency = data1.data[11];
        }
} catch (err) {
    console.error("Ошибка чтения первого блока регистров:", err);
}

// Второй блок: токи и мощности внешней сети (610-620)
try {
    const resp2 = await fetch(`/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=610&count=11&func=3`, {
        headers: { 'accept': 'application/json' }
    });
    const data2 = await resp2.json();
    console.log("Данные второго блока:", data2); 
    if (data2.ok && data2.data && data2.data.length === 11) {
            results.currentA = data2.data[0] * 0.01;
            results.currentB = data2.data[1] * 0.01;
            results.currentC = data2.data[2] * 0.01;
            results.outCurrentA = data2.data[3] * 0.01;
            results.outCurrentB = data2.data[4] * 0.01;
            results.outCurrentC = data2.data[5] * 0.01;
            results.outPowerA = data2.data[6];
            results.outPowerB = data2.data[7];
            results.outPowerC = data2.data[8];
            results.outTotalPower = data2.data[9];
            results.outTotalApparentPower = data2.data[10];
        }
} catch (err) {
    console.error("Ошибка чтения второго блока регистров:", err);
}
   console.log("Обработанные результаты:", results); 
return results;


}





async function readSunPanelRegisters(host, port, slave) {
    const results = {};

    // Описание регистров: start и коэффициент масштабирования
    const registers = [
        { start: 672, name: "PV1InputPower", scale: 1 },
        { start: 673, name: "PV2InputPower", scale: 1 },
        { start: 674, name: "PV3InputPower", scale: 1 },
        { start: 675, name: "PV4InputPower", scale: 1 },
        { start: 676, name: "DCVoltage1", scale: 0.1 },
        { start: 677, name: "DCCurrent1", scale: 0.1 },
        { start: 678, name: "DCVoltage2", scale: 0.1 },
        { start: 679, name: "DCCurrent2", scale: 0.1 },
        { start: 680, name: "DCVoltage3", scale: 0.1 },
        { start: 681, name: "DCCurrent3", scale: 0.1 },
        { start: 682, name: "DCVoltage4", scale: 0.1 },
        { start: 683, name: "DCCurrent4", scale: 0.1 }
    ];

    // Считаем все регистры за один раз
    const startRegister = registers[0].start;
    const count = registers.length;

    try {
        const resp = await fetch(`/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=${startRegister}&count=${count}&func=3`, {
            headers: { 'accept': 'application/json' }
        });
        const data = await resp.json();
        console.log("Сырые данные SUN Panel:", data);

        if (data.ok && data.data && data.data.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });
        }

    } catch (err) {
        console.error("Ошибка чтения SUN Panel регистров:", err);
    }

    console.log("Обработанные результаты SUN Panel:", results);
    return results;
}

async function readGeneratorRegisters(host, port, slave) {
    const results = {};

    // Описание регистров генератора: start и коэффициент масштабирования
    const registers = [
        { start: 661, name: "GenPhaseVoltageA", scale: 0.1 },
        { start: 662, name: "GenPhaseVoltageB", scale: 0.1 },
        { start: 663, name: "GenPhaseVoltageC", scale: 0.1 },
        { start: 664, name: "GenPhasePowerA", scale: 1 },
        { start: 665, name: "GenPhasePowerB", scale: 1 },
        { start: 666, name: "GenPhasePowerC", scale: 1 },
        { start: 667, name: "GenTotalPower", scale: 1 }
    ];

    // Считаем все регистры за один запрос
    const startRegister = registers[0].start;
    const count = registers.length;

    try {
        const resp = await fetch(`/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=${startRegister}&count=${count}&func=3`, {
            headers: { 'accept': 'application/json' }
        });
        const data = await resp.json();
          console.log("Сырые данные Generator:", data);
          if (data.ok && data.data && data.data.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });
        }
    } catch (err) {
        console.error("Ошибка чтения регистров генератора:", err);
    }

    console.log("Обработанные результаты генератора:", results);
    return results;
}


async function readInverterGridRegisters(host, port, slave) {
    const results = {};

    const registers = [
        { start: 621, name: "GridTotalApparentPower", scale: 1 },      // 621
        { start: 622, name: "GridPowerFactor", scale: 0.001 },         // 622 (value * 1000)
        { start: 623, name: "GridPowerA", scale: 1 },                  // 623
        { start: 624, name: "GridPowerB", scale: 1 },                  // 624
        { start: 625, name: "GridPowerC", scale: 1 },                  // 625

        // Output voltages
        { start: 627, name: "InverterVoltageA", scale: 0.1 },          // R41
        { start: 628, name: "InverterVoltageB", scale: 0.1 },          // R42
        { start: 629, name: "InverterVoltageC", scale: 0.1 },          // R43

        // Output currents
        { start: 630, name: "InverterCurrentA", scale: 0.01 },         // 44 S16
        { start: 631, name: "InverterCurrentB", scale: 0.01 },         // 45 S16
        { start: 632, name: "InverterCurrentC", scale: 0.01 },         // 46 S16

        // Output powers
        { start: 633, name: "InverterPowerA", scale: 1 },              // R47
        { start: 634, name: "InverterPowerB", scale: 1 },              // R48
        { start: 635, name: "InverterPowerC", scale: 1 },              // 49

        // Totals
        { start: 636, name: "InverterTotalPower", scale: 1 },          // R50
        { start: 637, name: "InverterTotalApparentPower", scale: 1 },  // 51

        // Frequency
        { start: 638, name: "InverterFrequency", scale: 0.01 },        // 52 (correct!)
    ];

    const startRegister = registers[0].start;
    const count = registers.length;

    try {
        const resp = await fetch(
            `/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=${startRegister}&count=${count}&func=3`,
            { headers: { 'accept': 'application/json' } }
        );

        const data = await resp.json();
        console.log("Raw inverter grid data:", data);

       if (data.ok && data.data && data.data.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });
        }
    } catch (err) {
        console.error("Error reading inverter registers:", err);
    }

    console.log("Processed inverter grid data:", results);
    return results;
}



async function readBatteryRegisters(host, port, slave) {
    const results = {};

    const registers = [
        { start: 586, name: "battery1Temperature", scale: 0.1 },        // °C
        { start: 587, name: "battery1Voltage", scale: 0.1 },           // V
        { start: 588, name: "battery1SOC", scale: 1 },                  // %
        { start: 589, name: "battery2SOC", scale: 1 },                  // %
        { start: 590, name: "battery1Power", scale: 10, signed: true }, // W (S16)
        { start: 591, name: "battery1Current", scale: 0.01, signed: true }, // A (S16)
        { start: 592, name: "batteryCorrectedAh", scale: 1 },           // Ah
        { start: 593, name: "battery2Voltage", scale: 0.1 },           // V
        { start: 594, name: "battery2Current", scale: 0.01, signed: true }, // A (S16)
        { start: 595, name: "battery2Power", scale: 10, signed: true },      // W
        { start: 596, name: "battery2Temperature", scale: 0.1 }         // °C
    ];

    const startRegister = registers[0].start;
    const count = registers.length;

    try {
        const resp = await fetch(
            `/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}` +
            `&start=${startRegister}&count=${count}&func=3`,
            { headers: { "accept": "application/json" } }
        );

        const data = await resp.json();
        console.log("Raw battery data:", data);

        if (data.ok && data.data && data.data.length === count) {

            registers.forEach((reg, idx) => {
                let val = data.data[idx];

                // Обработка signed (S16)
                if (reg.signed && val > 0x7FFF) val = val - 0x10000;

                results[reg.name] = val * reg.scale;
            });
        }

    } catch (err) {
        console.error("Ошибка чтения регистров батареи:", err);
    }

    console.log("Battery parsed results:", results);
    return results;
}

// Пример вызова:
//readDeyeRegisters("195.8.40.53", 502, 1).then(console.log);
//readSunPanelRegisters("195.8.40.53", 502, 1).then(console.log);
//readGeneratorRegisters("195.8.40.53", 502, 1).then(console.log);
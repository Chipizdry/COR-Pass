
async function startMonitoringDeye(objectData) {
    const INTERVAL = 2000; // интервал между циклами
   
    while (true) {
        console.log("---- Цикл обновления Deye ----");

        try {
            let gridData, solarData, genData, battData , InvGridOut ;
          
            const host = objectData.ip_address;
            const port = objectData.port;
            const slave = objectData.slave_id || objectData.slave || 1;
            const object_id = objectData.id;
            const protocol = objectData.protocol;

            switch (protocol) {
                case "modbus_over_tcp":
                    gridData  = await readOutGridRegisters( host,  port, slave,object_id,protocol  );
                    solarData = await readSunPanelRegisters(host,  port, slave,object_id,protocol );
                    genData   = await readGeneratorRegisters(host,  port, slave,object_id,protocol );
                    battData  = await readBatteryRegisters(host,  port, slave,object_id,protocol );
                    InvGridOut = await readInverterGridRegisters(host, port, slave, object_id, protocol);
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







async function readOutGridRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    // Универсальная функция чтения Modbus
    const readBlock = async (start, count) => {
        const url =
            `/api/modbus_tcp/v1/read` +
            `?protocol=${protocol}` +
            `&host=${host}` +
            `&port=${port}` +
            `&slave_id=${slave_id}` +
            `&object_id=${object_id}` +
            `&start=${start}` +
            `&count=${count}` +
            `&func_code=3`;

        const resp = await fetch(url, {
            headers: { 'accept': 'application/json' }
        });

        return resp.json();
    };

    // --- Первый блок: 598–609 ---
    try {
        const data1 = await readBlock(598, 12);
        console.log("Данные первого блока:", data1);

        if (data1.ok && data1.data?.length === 12) {

            results.phaseVoltageA = data1.data[0] * 0.1;
            results.phaseVoltageB = data1.data[1] * 0.1;
            results.phaseVoltageC = data1.data[2] * 0.1;

            results.lineVoltageAB = data1.data[3] * 0.1;
            results.lineVoltageBC = data1.data[4] * 0.1;
            results.lineVoltageCA = data1.data[5] * 0.1;

            results.powerA = data1.data[6];
            results.powerB = data1.data[7];
            results.powerC = data1.data[8];

            results.totalPower         = data1.data[9];
            results.totalApparentPower = data1.data[10];
            results.gridFrequency      = data1.data[11];
        }

    } catch (err) {
        console.error("Ошибка чтения первого блока регистров:", err);
    }

    // --- Второй блок: 610–620 ---
    try {
        const data2 = await readBlock(610, 11);
        console.log("Данные второго блока:", data2);

        if (data2.ok && data2.data?.length === 11) {
            results.currentA = data2.data[0] * 0.01;
            results.currentB = data2.data[1] * 0.01;
            results.currentC = data2.data[2] * 0.01;

            results.outCurrentA = data2.data[3] * 0.01;
            results.outCurrentB = data2.data[4] * 0.01;
            results.outCurrentC = data2.data[5] * 0.01;

            results.outPowerA = data2.data[6];
            results.outPowerB = data2.data[7];
            results.outPowerC = data2.data[8];

            results.outTotalPower         = data2.data[9];
            results.outTotalApparentPower = data2.data[10];
        }

    } catch (err) {
        console.error("Ошибка чтения второго блока регистров:", err);
    }

    console.log("Обработанные результаты:", results);
    return results;
}


async function readSunPanelRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const readBlock = async (start, count) => {
        const url =
            `/api/modbus_tcp/v1/read` +
            `?protocol=${protocol}` +
            `&host=${host}` +
            `&port=${port}` +
            `&slave_id=${slave_id}` +
            `&object_id=${object_id}` +
            `&start=${start}` +
            `&count=${count}` +
            `&func_code=3`;

        const resp = await fetch(url, { headers: { accept: "application/json" } });
        return resp.json();
    };

    const registers = [
        { name: "PV1InputPower", start: 672, scale: 1 },
        { name: "PV2InputPower", start: 673, scale: 1 },
        { name: "PV3InputPower", start: 674, scale: 1 },
        { name: "PV4InputPower", start: 675, scale: 1 },
        { name: "DCVoltage1",    start: 676, scale: 0.1 },
        { name: "DCCurrent1",    start: 677, scale: 0.1 },
        { name: "DCVoltage2",    start: 678, scale: 0.1 },
        { name: "DCCurrent2",    start: 679, scale: 0.1 },
        { name: "DCVoltage3",    start: 680, scale: 0.1 },
        { name: "DCCurrent3",    start: 681, scale: 0.1 },
        { name: "DCVoltage4",    start: 682, scale: 0.1 },
        { name: "DCCurrent4",    start: 683, scale: 0.1 },
    ];

    const startReg = registers[0].start;
    const count = registers.length;

    try {
        const data = await readBlock(startReg, count);
        console.log("Сырые данные SUN Panel:", data);

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });
        }
    } catch (err) {
        console.error("Ошибка чтения SunPanel регистров:", err);
    }

    console.log("Обработанные результаты SUN Panel:", results);
    return results;
}

async function readGeneratorRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    // Перечень регистров генератора
    const registers = [
        { start: 661, name: "GenPhaseVoltageA", scale: 0.1 },
        { start: 662, name: "GenPhaseVoltageB", scale: 0.1 },
        { start: 663, name: "GenPhaseVoltageC", scale: 0.1 },
        { start: 664, name: "GenPhasePowerA", scale: 1 },
        { start: 665, name: "GenPhasePowerB", scale: 1 },
        { start: 666, name: "GenPhasePowerC", scale: 1 },
        { start: 667, name: "GenTotalPower", scale: 1 }
    ];

    const startReg = registers[0].start;
    const count = registers.length;

    const url =
        `/api/modbus_tcp/v1/read` +
        `?protocol=${protocol}` +
        `&host=${host}` +
        `&port=${port}` +
        `&slave_id=${slave_id}` +
        `&object_id=${object_id}` +
        `&start=${startReg}` +
        `&count=${count}` +
        `&func_code=3`;

    try {
        const resp = await fetch(url, {
            headers: { accept: "application/json" }
        });

        const data = await resp.json();
        console.log("Сырые данные Generator:", data);

        if (data.ok && data.data?.length === count) {
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



async function readInverterGridRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const registers = [
            { start: 621, name: "GridPowerFactor", scale: 0.001 },        // PF
            { start: 622, name: "GridPowerA", scale: 1 },                 // Low_Word
            { start: 623, name: "GridPowerB", scale: 1 },
            { start: 624, name: "GridPowerC", scale: 1 },
            { start: 625, name: "GridTotalPower", scale: 1 },

            // 626 пропускаем
            { start: 626, name: "InverterVoltageA???", scale: 0.1 },
            { start: 627, name: "InverterVoltageA", scale: 0.1 },
            { start: 628, name: "InverterVoltageB", scale: 0.1 },
            { start: 629, name: "InverterVoltageC", scale: 0.1 },

            { start: 630, name: "InverterCurrentA", scale: 1, signed: true },
            { start: 631, name: "InverterCurrentB", scale: 1, signed: true },
            { start: 632, name: "InverterCurrentC", scale: 1, signed: true },

            { start: 633, name: "InverterPowerA", scale: 1, signed: true },
            { start: 634, name: "InverterPowerB", scale: 1, signed: true },
            { start: 635, name: "InverterPowerC", scale: 1, signed: true },

            { start: 636, name: "InverterTotalPower", scale: 1, signed: true },
            { start: 637, name: "InverterTotalApparentPower", scale: 1, signed: true },
            { start: 638, name: "InverterFrequency", scale: 0.01 },
        ];
    const startReg = registers[0].start;
    const count = registers.length;

    const url =
        `/api/modbus_tcp/v1/read` +
        `?protocol=${protocol}` +
        `&host=${host}` +
        `&port=${port}` +
        `&slave_id=${slave_id}` +
        `&object_id=${object_id}` +
        `&start=${startReg}` +
        `&count=${count}` +
        `&func_code=3`;

    try {
        const resp = await fetch(url, { headers: { accept: "application/json" } });
        const data = await resp.json();
        console.log("Raw inverter grid data:", data);

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                let val = data.data[idx];
                if (reg.signed && val > 0x7FFF) val -= 0x10000;
                results[reg.name] = val * reg.scale;
            });
        }

    } catch (err) {
        console.error("Error reading inverter registers:", err);
    }

    console.log("Processed inverter grid data:", results);
    return results;
}




async function readBatteryRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    // Перечень регистров батареи
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

    const startReg = registers[0].start;
    const count = registers.length;

    const url =
        `/api/modbus_tcp/v1/read` +
        `?protocol=${protocol}` +
        `&host=${host}` +
        `&port=${port}` +
        `&slave_id=${slave_id}` +
        `&object_id=${object_id}` +
        `&start=${startReg}` +
        `&count=${count}` +
        `&func_code=3`;

    try {
        const resp = await fetch(url, {
            headers: { accept: "application/json" }
        });

        const data = await resp.json();
        console.log("Raw battery data:", data);

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                let val = data.data[idx];
                if (reg.signed && val > 0x7FFF) val -= 0x10000; // обработка signed S16
                results[reg.name] = val * reg.scale;
            });
        }

    } catch (err) {
        console.error("Ошибка чтения регистров батареи:", err);
    }

    console.log("Battery parsed results:", results);
    return results;
}



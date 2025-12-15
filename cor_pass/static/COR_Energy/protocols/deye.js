
async function startMonitoringDeye(objectData) {
    const INTERVAL = 2000; // интервал между циклами
    const INVERTER_MAX_POWER = 80000; // 80 кВт
    while (true) {
        console.log("---- Цикл обновления Deye ----");

        try {
           
          
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
                    gridDataPower = await readPower32_V104(host, port, slave, object_id, protocol);
                    LoadData = await readLoadRegisters(host, port, slave, object_id, protocol);
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

        } catch (err) {
            console.error("Ошибка мониторинга Deye:", err);
        }

        await new Promise(resolve => setTimeout(resolve, INTERVAL));
    }
}

/*  Регистры 622-625 соответствуют регистрам 687-690 , Сеть
    Регистры 633-637 соответствуют регистрам 691-695 , Выход инвертора
    Регистры 640-643 соответствуют регистрам 696-699 , Нагрузка ИБП
    Регистры 616-620 соответствуют регистрам 705-709 , Внешние трансформаторы тока 
    Регистры 604-608 соответствуют регистрам 700-704 , Внутренние трансформаторы тока


Измерение       	Регистры	                    Что измеряет
Inverter Output	    633-637 + 691-695	            Мощность на выходе DC-AC преобразователя
Grid Side	        622-625 + 687-690	            Мощность на стороне сети (после реле)
Load Side	        650-654 + 700-704	            Мощность на стороне нагрузки
UPS Load	        646-649 + 696-699	            Мощность на критической нагрузке
External CT	        655-659 + 705-709	            Мощность через внешние датчики

*/



async function readGeneratorRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const startReg = 661;
    const count = 11; // 661–671

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

       // console.log("Raw Generator data:", data);

        if (data.ok && data.data?.length === count) {

            // --- Phase voltages ---
            results.GenPhaseVoltageA = data.data[0] * 0.1;
            results.GenPhaseVoltageB = data.data[1] * 0.1;
            results.GenPhaseVoltageC = data.data[2] * 0.1;

            // --- LOW words ---
            const pA_low = data.data[3];
            const pB_low = data.data[4];
            const pC_low = data.data[5];
            const pT_low = data.data[6];

            // --- HIGH words ---
            const pA_high = data.data[7];
            const pB_high = data.data[8];
            const pC_high = data.data[9];
            const pT_high = data.data[10];

            // --- 32-bit power calculation ---
            results.GenPhasePowerA = (pA_high << 16) | pA_low;
            results.GenPhasePowerB = (pB_high << 16) | pB_low;
            results.GenPhasePowerC = (pC_high << 16) | pC_low;
            results.GenTotalPower  = (pT_high << 16) | pT_low;
        }

    } catch (err) {
        console.error("Ошибка чтения регистров генератора:", err);
    }

    console.log("Parsed generator results:", results);
    return results;
}





async function readBatteryRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const registers = [
        { start: 586, name: "battery1Temperature", scale: 0.1 },        // °C
        { start: 587, name: "battery1Voltage", scale: 0.1 },            // V
        { start: 588, name: "battery1SOC", scale: 1 },                   // %
        { start: 589, name: "battery2SOC", scale: 1 },                   // %
        { start: 590, name: "battery1Power", scale: 10, signed: true },  // W
        { start: 591, name: "battery1Current", scale: 0.01, signed: true }, // A
        { start: 592, name: "batteryCorrectedAh", scale: 1 },            // Ah
        { start: 593, name: "battery2Voltage", scale: 0.1 },            // V
        { start: 594, name: "battery2Current", scale: 0.01, signed: true }, // A
        { start: 595, name: "battery2Power", scale: 10, signed: true },  // W
        { start: 596, name: "battery2Temperature", scale: 0.1 }          // °C
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

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                let val = data.data[idx];
                if (reg.signed && val > 0x7FFF) val -= 0x10000;
                results[reg.name] = val * reg.scale;
            });

            // 🔹 ОБЩАЯ МОЩНОСТЬ БАТАРЕЙ
            const p1 = results.battery1Power ?? 0;
            const p2 = results.battery2Power ?? 0;
            results.batteryTotalPower = p1 + p2;
        }

    } catch (err) {
        console.error("Ошибка чтения регистров батареи:", err);
    }

    console.log("Battery parsed results:", results);
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
        { name: "PV1InputPower", start: 672, scale: 10 },
        { name: "PV2InputPower", start: 673, scale: 10 },
        { name: "PV3InputPower", start: 674, scale: 10 },
        { name: "PV4InputPower", start: 675, scale: 10 },

        { name: "DCVoltage1", start: 676, scale: 0.1 },
        { name: "DCCurrent1", start: 677, scale: 0.1 },
        { name: "DCVoltage2", start: 678, scale: 0.1 },
        { name: "DCCurrent2", start: 679, scale: 0.1 },
        { name: "DCVoltage3", start: 680, scale: 0.1 },
        { name: "DCCurrent3", start: 681, scale: 0.1 },
        { name: "DCVoltage4", start: 682, scale: 0.1 },
        { name: "DCCurrent4", start: 683, scale: 0.1 },
    ];

    const startReg = registers[0].start;
    const count = registers.length;

    try {
        const data = await readBlock(startReg, count);

        if (data.ok && data.data?.length === count) {

            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });

            /* ===== PV TOTAL POWER ===== */
            results.PVTotalPower =
                (results.PV1InputPower || 0) +
                (results.PV2InputPower || 0) +
                (results.PV3InputPower || 0) +
                (results.PV4InputPower || 0);
        }

    } catch (err) {
        console.error("Ошибка чтения SunPanel регистров:", err);
    }

    console.log("Обработанные результаты SUN Panel:", results);
    return results;
}





async function readLoadRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const startReg = 644;
    const count = 17; // 644–660

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

      //  console.log("Raw LOAD data:", data);

        if (data.ok && data.data?.length === count) {

            /* ---------- Voltages ---------- */
            results.LoadPhaseVoltageA = data.data[0] * 0.1; // 644
            results.LoadPhaseVoltageB = data.data[1] * 0.1; // 645
            results.LoadPhaseVoltageC = data.data[2] * 0.1; // 646

            /* ---------- Frequency ---------- */
            results.LoadFrequency = data.data[11] * 0.01;  // 655

            /* ---------- LOW words ---------- */
            const pA_low = data.data[6];  // 650
            const pB_low = data.data[7];  // 651
            const pC_low = data.data[8];  // 652
            const pT_low = data.data[9];  // 653

            /* ---------- HIGH words ---------- */
            const pA_high = data.data[12]; // 656
            const pB_high = data.data[13]; // 657
            const pC_high = data.data[14]; // 658
            const pT_high = data.data[15]; // 659

            /* ---------- S32 power calculation ---------- */
            results.LoadPhasePowerA =
                ((pA_high << 16) | pA_low) << 0;
            results.LoadPhasePowerB =
                ((pB_high << 16) | pB_low) << 0;
            results.LoadPhasePowerC =
                ((pC_high << 16) | pC_low) << 0;
            results.LoadTotalPower =
                ((pT_high << 16) | pT_low) << 0;
        }

    } catch (err) {
        console.error("Ошибка чтения регистров нагрузки:", err);
    }

    console.log("Parsed LOAD results:", results);
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

            { start: 636, name: "InverterTotalPower", scale: 0.1, signed: true },
            { start: 637, name: "InverterTotalApparentPower", scale: 0.1, signed: true },
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
       // console.log("Raw inverter grid data:", data);

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
       // console.log("Данные первого блока:", data1);

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
       // console.log("Данные второго блока:", data2);

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





async function readPower32_V104(host, port, slave_id, object_id, protocol) {
    const results = {};

    const registers = [
        // --- Grid side ---
        { start: 687, name: "GridPowerA_high", scale: 1 },
        { start: 688, name: "GridPowerB_high", scale: 1 },
        { start: 689, name: "GridPowerC_high", scale: 1 },
        { start: 690, name: "GridTotalPower_high", scale: 1 },

        // --- Inverter output ---
        { start: 691, name: "InverterPowerA_high", scale: 1, signed: true },
        { start: 692, name: "InverterPowerB_high", scale: 1, signed: true },
        { start: 693, name: "InverterPowerC_high", scale: 1, signed: true },
        { start: 694, name: "InverterTotalPower_high", scale: 1, signed: true },
        { start: 695, name: "InverterTotalApparentPower_high", scale: 1, signed: true },

        // --- UPS load ---
        { start: 696, name: "UpsPowerA_high", scale: 1 },
        { start: 697, name: "UpsPowerB_high", scale: 1 },
        { start: 698, name: "UpsPowerC_high", scale: 1 },
        { start: 699, name: "UpsTotalPower_high", scale: 1 },

        // --- Inner grid ---
        { start: 700, name: "InnerGridPowerA_high", scale: 1, signed: true },
        { start: 701, name: "InnerGridPowerB_high", scale: 1, signed: true },
        { start: 702, name: "InnerGridPowerC_high", scale: 1, signed: true },
        { start: 703, name: "InnerGridTotalPower_high", scale: 1, signed: true },
        { start: 704, name: "InnerGridTotalApparentPower_high", scale: 1 }, // reserved

        // --- Out grid ---
        { start: 705, name: "OutGridPowerA_high", scale: 1, signed: true },
        { start: 706, name: "OutGridPowerB_high", scale: 1, signed: true },
        { start: 707, name: "OutGridPowerC_high", scale: 1, signed: true },
        { start: 708, name: "OutGridTotalPower_high", scale: 1, signed: true },
        { start: 709, name: "OutGridTotalApparentPower_high", scale: 1, signed: true },
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

      //  console.log("Raw HIGH power data:", data);

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                let val = data.data[idx];
                if (reg.signed && val > 0x7FFF) val -= 0x10000; // S16
                results[reg.name] = val * reg.scale;
            });
        }

    } catch (err) {
        console.error("Ошибка чтения HIGH power регистров:", err);
    }

    console.log("Parsed HIGH power results:", results);
    return results;
}


async function startMonitoringDeye(objectData) {

    if (deyeMonitorRunning) {
        console.warn("Deye monitoring already running");
        return;
    }

    deyeMonitorRunning = true;

    const INTERVAL = 2000;
    const INVERTER_MAX_POWER = 80000;

    const {
        ip_address: host,
        port,
        slave_id,
        id: object_id,
        protocol
    } = objectData;

    const slave = slave_id || 1;

    while (deyeMonitorRunning) {
        try {

            let gridData, solarData, genData, battData, loadData;

            if (protocol === "modbus_over_tcp") {
                gridData  = await readOutGridRegisters(host, port, slave, object_id, protocol);
                solarData = await readSunPanelRegisters(host, port, slave, object_id, protocol);
                genData   = await readGeneratorRegisters(host, port, slave, object_id, protocol);
                battData  = await readBatteryRegisters(host, port, slave, object_id, protocol);
                loadData  = await readLoadRegisters(host, port, slave, object_id, protocol);
            } else {
                console.warn("Unsupported Deye protocol:", protocol);
                break;
            }

            /* ===== UI ===== */

            if (solarData?.PV1InputPower !== undefined) {
                updatePowerByName(
                    "Solar",
                    PowerToIndicator(solarData.PVTotalPower, INVERTER_MAX_POWER)
                );
            }

            if (genData?.GenTotalPower !== undefined) {
                updatePowerByName(
                    "Generator",
                    PowerToIndicator(genData.GenTotalPower, INVERTER_MAX_POWER)
                );
            }

            if (loadData?.LoadTotalPower !== undefined) {
                updatePowerByName(
                    "Load",
                    PowerToIndicator(loadData.LoadTotalPower, INVERTER_MAX_POWER)
                );
            }

            if (battData?.batteryTotalPower !== undefined) {
                updatePowerByName("Battery", PowerToIndicator(battData.batteryTotalPower, INVERTER_MAX_POWER));
                updateBatteryFill(battData.battery1SOC);
            }

            if (gridData?.totalPower !== undefined) {
                updatePowerByName(
                    "Grid",
                    PowerToIndicator(gridData.totalPower, INVERTER_MAX_POWER)
                );
            }


            loadIndicatorLabel.textContent =
                formatPowerLabel(loadData.LoadTotalPower, "load");

            networkFlowLabel.textContent =
                formatPowerLabel(gridData.totalPower, "grid");

            batteryFlowLabel.textContent =
                formatPowerLabel(battData.batteryTotalPower, "battery");

            solarPowerLabel.textContent =
                formatPowerLabel(solarData.PVTotalPower, "solar");

            generatorFlowLabel.textContent =
                formatPowerLabel(genData.GenTotalPower, "generator");


        } catch (err) {
            console.error("Ошибка мониторинга Deye:", err);
        }

        await new Promise(r => setTimeout(r, INTERVAL));
    }

    deyeMonitorRunning = false;
}



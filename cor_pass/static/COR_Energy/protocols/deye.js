

async function readDeyeRegisters(host, port, slave) {
const results = {};

// Первый блок: напряжения и мощности фаз (598-609)
try {
    const resp1 = await fetch(`/api/modbus_tcp/read?host=${host}&port=${port}&slave=${slave}&start=598&count=12&func=3`, {
        headers: { 'accept': 'application/json' }
    });
    const data1 = await resp1.json();
    console.log("Данные первого блока:", data1); 
    if (data1.result && data1.result.length === 12) {
        results.phaseVoltageA = data1.result[0] * 0.1;
        results.phaseVoltageB = data1.result[1] * 0.1;
        results.phaseVoltageC = data1.result[2] * 0.1;
        results.lineVoltageAB = data1.result[3] * 0.1;
        results.lineVoltageBC = data1.result[4] * 0.1;
        results.lineVoltageCA = data1.result[5] * 0.1;
        results.powerA = data1.result[6] * 1;
        results.powerB = data1.result[7] * 1;
        results.powerC = data1.result[8] * 1;
        results.totalPower = data1.result[9] * 1;
        results.totalApparentPower = data1.result[10] * 1;
        results.gridFrequency = data1.result[11] * 1;
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
    if (data2.result && data2.result.length === 11) {
        results.currentA = data2.result[0] * 0.01;
        results.currentB = data2.result[1] * 0.01;
        results.currentC = data2.result[2] * 0.01;
        results.outCurrentA = data2.result[3] * 0.01;
        results.outCurrentB = data2.result[4] * 0.01;
        results.outCurrentC = data2.result[5] * 0.01;
        results.outPowerA = data2.result[6] * 1;
        results.outPowerB = data2.result[7] * 1;
        results.outPowerC = data2.result[8] * 1;
        results.outTotalPower = data2.result[9] * 1;
        results.outTotalApparentPower = data2.result[10] * 1;
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

        if (data.result && data.result.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.result[idx] * reg.scale;
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
        console.log("Сырые данные генератора:", data);

        if (data.result && data.result.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.result[idx] * reg.scale;
            });
        }
    } catch (err) {
        console.error("Ошибка чтения регистров генератора:", err);
    }

    console.log("Обработанные результаты генератора:", results);
    return results;
}

// Пример вызова:
//readDeyeRegisters("195.8.40.53", 502, 1).then(console.log);
//readSunPanelRegisters("195.8.40.53", 502, 1).then(console.log);
//readGeneratorRegisters("195.8.40.53", 502, 1).then(console.log);
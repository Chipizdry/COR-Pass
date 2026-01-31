
// ============================
// Цикл мониторинга Deye
// ============================

// Объект с полной информацией о предупреждениях (аналогично DEYE_FAULT_INFO)
const DEYE_WARNING_INFO = {
    // W01-W10 из первой таблицы
    1: {  name:"W01", description: "Reserved", solution: "1. Check the operating status of the fan. 2. If the fan is running abnormally, open the cover of the inverter to check the connection of the fan."  },
    2: {  name:"W02", description: "FAN_IN_Warn", solution: "1. Check the operating status of the fan. 2. If the fan is running abnormally, open the cover of the inverter to check the connection of the fan." },    
    3: {  name:"W03", description: "Grid_phase_warn",  solution: "1. Check the phase sequence connection of the power grid. 2. Try to change the grid type, 0, 240/120. 3. If there is still no solution to check the wiring at the grid end." },
    4: {  name:"W04", description: "Meter_offline_warn", solution: "Meter communication failure. Check whether the meter has successful communication and whether the wiring is normal." },
    5: {  name:"W05", description: "CT_WRONG_direction_warn", solution: "Check whether the arrow on CT's case point to the inverter or not, and check if the installation location of CTs are correct."  },
    6: {  name:"W06", description: "CT_Notconnect_warn", solution: "Check whether the wires of CTs are connected correctly or not." },
    7: {  name:"W07", description: "FAN_OUT1_Warn",  solution: "Check whether the FAN are connected correctly and operating normally."  },
    8: {  name:"W08", description: "FAN_OUT2_Warn",  solution: "Check whether the FAN are connected correctly and operating normally." },
    9: {  name:"W09", description: "FAN_OUT3_Warn", solution: "1. Measure whether the grid port voltage is too high. 2. Check whether the AC cable is too thin to carry current." },
    10:{  name:"W10", description: "VW_activate", solution: "Check whether the FAN are connected correctly and operating normally." },
    11:{  name:"W11", description: "DC_Bus_Leakage_Warn",  solution: " This is a critical warning that requires checking the solar panel or battery connections. Main causes and actions: Check panel/battery voltage: Make sure that the PV (solar panel) or battery voltage is within the inverter's operating range. Reboot: Try to completely turn off the inverter (AC and DC), wait 10-15 minutes until the screen turns off, and then turn it on again. Check cables: Inspect the terminals for looseness or oxidation. Service center: If the W11/F11 error persists after reboot, contact the installer or service center."   },
    31:{  name:"W31", description: "Battery_comm_warn",  solution: "Abnormal battery communication. 1. Check whether the BMS connection is stable. 2. Check whether the BMS data is abnormal." },
    32:{  name:"W32", description: "Parallel_comm_warn", solution: "Unstable parallel communication. 1. Check the connection of the parallel communication line. Please do not wind the parallel communication line with other cables. 2. Check whether the parallel dip switch is on." }
};


 const DEYE_FAULT_INFO = {
  // F01–F19 из таблиц на страницах 51–52
  1:  { name: "F01", description: "DC_Inversed_Failure", solution: "Check the PV input polarity." },
  2:  { name: "F02", description: "DC_Insulation_Failure", solution: "Check whether the PV is grounded, secondly, check whether the impedance of the PV to the ground is normal." },
  3:  { name: "F03", description: "GFDI_Failure", solution: "1. Check whether the PV modules are grounded. 2. Check whether the impedance of the PV to the ground is normal, whether there is leakage current." },
  4:  { name: "F04", description: "GFDI_Ground_Failure", solution: "Check whether the PV is grounded." },
  5:  { name: "F05", description: "EEPROM_Read_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  6:  { name: "F06", description: "EEPROM_Write_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  7:  { name: "F07", description: "DCDC1_START_Failure", solution: "The BUS voltage can't be reached by PV or battery. 1. Switch off the DC switches and restart the inverter." },
  8:  { name: "F08", description: "DCDC2_START_Failure", solution: "The BUS voltage can't be reached by PV or battery. 1. Switch off the DC switches and restart the inverter." },
  9:  { name: "F09", description: "IGBT_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  10: { name: "F10", description: "AuxPowerBoard_Failure", solution: "1. First check whether the inverter switch is open. 2. Restart the inverter 3 times and restore the factory settings." },
  11: { name: "F11", description: "AC_MainContactor_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  12: { name: "F12", description: "AC_SlaveContactor_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  13: { name: "F13", description: "Working_Mode_Change", solution: "1. When the grid type and frequency have changed it will report F13. 2. When the battery mode has been changed to 'No battery' mode, it will report F13. 3. For some old FW version, it will report F13 when the system's work mode has been changed. 4. Generally, this error will disappear automatically. 5. If it remains the same, turn off DC and AC switches for one minute, then turn on the DC and AC switches." },
  14: { name: "F14", description: "DC_OverCurr_Failure", solution: "Restart the inverter 3 times and restore the factory settings." },
  15: { name: "F15", description: "AC_OverCurr_SW_Failure", solution: "AC side over current fault. 1. Please check whether the backup load power and common load power are within the range. 2. Restart and check whether it is normal." },
  16: { name: "F16", description: "GFCI_Failure", solution: "Leakage current fault. 1. Check the PV side cable ground connection. 2. Restart the system 2-3 times." },
  17: { name: "F17", description: "Tz_PV_OverCurr_Fault", solution: "1. Check the PV connection and whether the PV is unstable. 2. Restart the inverter 3 times." },
  18: { name: "F18", description: "Tz_AC_OverCurr_Fault", solution: "AC side over current fault. 1. Please check whether the backup load power and common load power are within the range. 2. Restart and check whether it is normal." },
  19: { name: "F19", description: "Tz_Integ_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  20: { name: "F20", description: "Tz_Dc_OverCurr_Fault", solution: "DC side over current fault 1. Check PV module connection and battery connection; 2. When in the off-grid mode, starting the inverter under a high power load may report F20. Please reduce the load power connected. 3. If it remains the same, turn off DC and AC switches for one minute, then turn on the DC and AC switches." },
  21: { name: "F21", description: "Tz_HV_Overcurr_Fault", solution: "BUS over current 1. Check the PV input current and battery current setting. 2. Restart the system 2~3 times." },
  22: { name: "F22", description: "Tz_EmergStop_Fault", solution: "Remotely shutdown It means the inverter is remotely controlled." },
  23: { name: "F23", description: "Tz_GFCI_OC_Fault", solution: "Leakage current fault 1. Check PV side cable ground connection. 2. Restart the system 2~3 times." },
  24: { name: "F24", description: "DC_Insulation_Fault", solution: "PV isolation resistance is too low 1. Check the connection of PV panels and inverter is firm and correct. 2. Check whether the PE cable of inverter is connected to ground." },
  25: { name: "F25", description: "DC_Feedback_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  26: { name: "F26", description: "BusUnbalance_Fault", solution: "1. Please wait for a while and check whether it is normal. 2. When the load power of 3 phases has a big different, it will report the F26. 3. When there's DC leakage current, it will report F26. 4. Restart the system 2~3 times." },
  27: { name: "F27", description: "DC_Insulation_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  28: { name: "F28", description: "DCIOver_M1_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  29: { name: "F29", description: "Parallel_Comm_Fault", solution: "1. When inverters are connected in parallel, check the parallel communication cable connection and hybrid inverter communication address setting. 2. During the parallel system startup period, inverters will report F29. But when all inverters are in ON status, it will disappear automatically." },
  30: { name: "F30", description: "AC_MainContactor_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  31: { name: "F31", description: "AC_SlaveContactor_Fault", solution: "1. Check whether the grid orientation is correct, 2. Restart the inverter 3 times and restore the factory settings" },
  32: { name: "F32", description: "DCIOver_M2_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  33: { name: "F33", description: "AC_OverCurr_Fault", solution: "1. Check whether the grid current is too large. 2. Restart the inverter 3 times and restore the factory settings." },
  34: { name: "F34", description: "AC_Overload_Fault", solution: "Check the backup load connection, make sure it is within the allowed power range." },
  35: { name: "F35", description: "AC_NotUtility_Fault", solution: "Check the grid voltage and frequency, whether the connection of the power grid is normal." },
  36: { name: "F36", description: "Reserved", solution: "N/A" },
  37: { name: "F37", description: "Reserved", solution: "N/A" },
  38: { name: "F38", description: "Reserved", solution: "N/A" },
  39: { name: "F39", description: "INT_AC_OverCurr_Fault", solution: "Inverter AC overcurrent, restart the inverter." },
  40: { name: "F40", description: "INT_DC_OverCurr_Fault", solution: "Inverter DC overcurrent, restart the inverter." },
  41: { name: "F41", description: "Parallel_system_Stop", solution: "Check the hybrid inverter work status. If there is at least one hybrid inverter shutdown, all hybrid inverters will report F41 fault." },
  42: { name: "F42", description: "Parallel_Version_Fault", solution: "1. Check whether the inverter version is consistent. 2. Please contact us to upgrade the software version." },
  43: { name: "F43", description: "Reserved", solution: "N/A" },
  44: { name: "F44", description: "Reserved", solution: "N/A" },
  45: { name: "F45", description: "AC_UV_OverVolt_Fault", solution: "Grid voltage out of range. 1. Check the voltage is in the range of specification or not. 2. Check whether AC cables are firmly and correctly connected." },
  46: { name: "F46", description: "AC_UV_UnderVolt_Fault", solution: "Grid voltage out of range. 1. Check the voltage is in the range of specification or not. 2. Check whether AC cables are firmly and correctly connected." },
  47: { name: "F47", description: "AC_OverFreq_Fault", solution: "Grid frequency out of range. 1. Check whether the frequency is in the range of the specification or not. 2. Check whether AC cables are firmly and correctly connected." },
  48: { name: "F48", description: "AC_UnderFreq_Fault", solution: "Grid frequency out of range. 1. Check whether the frequency is in the range of the specification or not. 2. Check whether AC cables are firmly and correctly connected." },
  49: { name: "F49", description: "AC_U_GridCurr_DcHigh_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  50: { name: "F50", description: "AC_V_GridCurr_DcHigh_Fault", solution: "Restart the inverter 3 times and restore the factory settings." },
  51: { name: "F51", description: "Battery_Temp_High_Fault", solution: "Check whether the temperature data of BMS is too high." },
  52: { name: "F52", description: "DC_VoltHigh_Fault", solution: "BUS voltage is too high. 1. Check whether battery voltage is too high. 2. Check the PV input voltage, make sure if it is within the allowed range." },
  53: { name: "F53", description: "DC_VoltLow_Fault", solution: "BUS voltage is too low. 1. Check whether battery voltage is too low. 2. If the battery voltage is too low, use PV or grid to charge the battery." },
  54: { name: "F54", description: "BAT2_VoltHigh_Fault", solution: "1. Check the battery 2 terminal voltage is high. 2. Restart the inverter 2 times and restore the factory settings." },
  55: { name: "F55", description: "BAT1_VoltHigh_Fault", solution: "1. Check the battery 1 terminal voltage is high. 2. Restart the inverter 2 times and restore the factory settings." },
  56: { name: "F56", description: "BAT1_VoltLow_Fault", solution: "1. Check the battery 1 terminal voltage is low. 2. Restart the inverter 2 times and restore the factory settings." },
  57: { name: "F57", description: "BAT2_VoltLow_Fault", solution: "1. Check the battery 2 terminal voltage is low. 2. Restart the inverter 2 times and restore the factory settings." },
  58: { name: "F58", description: "Battery_Comm_Lose", solution: "1. It means that the communication between the hybrid inverter and the battery BMS is disconnected when ‘BMS_Err-Stop’ is active. 2. To avoid this error, disable ‘BMS_Err-Stop’ item on the LCD." },
  59: { name: "F59", description: "Reserved", solution: "N/A" },
  60: { name: "F60", description: "GEN_FAULT", solution: "Check whether the voltage and frequency of the generator are normal, and then restart." },
  61: { name: "F61", description: "INVERTER_Manual_OFF", solution: "Check whether the switch of the inverter is turned on, restart the inverter, and restore the factory settings." },
  62: { name: "F62", description: "DRMs_Stop", solution: "Check the DRM function is active or not." },
  63: { name: "F63", description: "ARC_Fault", solution: "1. ARC fault detection is only for US market. 2. Check PV module cable connection and clear the fault." },
  64: { name: "F64", description: "Heatsink_HighTemp_Fault", solution: "Heat sink temperature is too high. 1. Check whether the working environment temperature is too high. 2. Turn off the inverter for 10 minutes and restart." }
};

async function startMonitoringDeye(objectData) {

    if (deyeMonitorRunning) {
        console.warn("Deye monitoring already running");
        return;
    }

    deyeMonitorRunning = true;

    const INTERVAL = 1000;
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


            if (protocol === "modbus_over_tcp") {
                
            gridData  = await readOutGridRegisters(host, port, slave, object_id, protocol);
            solarData = await readSunPanelRegisters(host, port, slave, object_id, protocol);
            solarExtData = await readSunPanelExtRegisters(host, port, slave, object_id, protocol);
            genData   = await readGeneratorRegisters(host, port, slave, object_id, protocol);
            battData  = await readBatteryRegisters(host, port, slave, object_id, protocol);
            loadData  = await readLoadRegisters(host, port, slave, object_id, protocol);
            InvGridOut = await readInverterGridRegisters(host, port, slave, object_id, protocol);
            gridDataPower = await readPower32_V104(host, port, slave, object_id, protocol);
            serviceData = await readServiceRegisters(host, port, slave, object_id, protocol);

            energyServiceData = await readEnergyServiceRegisters(host, port, slave, object_id, protocol);
            deyeFaults = await readDeyeFaults(host, port, slave, object_id, protocol);


            const calculatedSOC = calculateBatterySOCVoltage(battData, energyServiceData);

           if (calculatedSOC !== null) {
                battData.calculatedSOC = calculatedSOC;
                battData.battery1SOC = calculatedSOC;
                battData.battery2SOC = calculatedSOC;
            }

            } else {
                console.warn("Unsupported Deye protocol:", protocol);
                break;
            }

            /* ===== UI ===== */

                if (solarExtData?.PVTotalPowerRaw != null) {
                    updatePowerByName( "Solar", PowerToIndicator(solarExtData.PVTotalPowerRaw, INVERTER_MAX_POWER) );
                    solarPowerLabel.textContent = formatPowerLabel(solarExtData.PVTotalPowerRaw, "solar");
                     setIconStatus("Solar", "normal");
                }

                if (genData?.GenTotalPower != null) {
                    updatePowerByName("Generator", PowerToIndicator(genData.GenTotalPower, INVERTER_MAX_POWER));
                    generatorFlowLabel.textContent = formatPowerLabel(genData.GenTotalPower, "generator");
                   if (typeof serviceData?.genRelay === "boolean") {
                    setDeviceVisibility( "Generator", serviceData.genRelay ? "visible" : "hidden");
                    }
                    setIconStatus("Generator", "normal");
                }

                if (loadData?.LoadTotalPower != null) {
                    updatePowerByName(
                        "Load",
                        PowerToIndicator(loadData.LoadTotalPower, INVERTER_MAX_POWER)
                    );
                    loadIndicatorLabel.textContent = formatPowerLabel(loadData.LoadTotalPower, "load");
                    setIconStatus("Load", "normal");
                }

                if (battData?.batteryTotalPower != null) {
                    updatePowerByName(
                        "Battery",
                        PowerToIndicator(battData.batteryTotalPower, INVERTER_MAX_POWER)
                    );
                     updateBatteryFill(battData.battery1SOC);
                    batteryFlowLabel.textContent = formatPowerLabel(battData.batteryTotalPower, "battery");
                    setIconStatus("Battery", "normal");
                }

                if (gridData?.inputPowerTotal != null) {
                    updatePowerByName("Grid", PowerToIndicator(gridData.inputPowerTotal, INVERTER_MAX_POWER));
                    networkFlowLabel.textContent = formatPowerLabel(gridData.inputPowerTotal, "grid");
                    setIconStatus("Grid", "normal");
                }


                // 🔹 обновляем lastData
                    window.lastData = {
                        ...window.lastData,
                        ...window.gridData,
                        ...window.solarData,
                        ...window.solarExtData,
                        ...window.genData,
                        ...window.battData,
                        ...window.loadData,
                        ...window.InvGridOut,
                        ...window.gridDataPower
                    };

                    // 🔹 обновляем UI (включая все открытые модалки)
                    window.updateUIByData(window.lastData);

        } catch (err) {
            console.error("Ошибка мониторинга Deye:", err);
        }

          

        await new Promise(r => setTimeout(r, INTERVAL));
    }

    deyeMonitorRunning = false;
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
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

            // --- calculate currents ---
            results.GenPhaseCurrentA = results.GenPhasePowerA / (results.GenPhaseVoltageA || 1);
            results.GenPhaseCurrentB = results.GenPhasePowerB / (results.GenPhaseVoltageB || 1);
            results.GenPhaseCurrentC = results.GenPhasePowerC / (results.GenPhaseVoltageC || 1);

        }

    } catch (err) {
        console.error("Ошибка чтения регистров генератора:", err);
    }

    console.log("Parsed generator results:", results);
    return results;
}


async function readSunPanelExtRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const readBlock = async (start, count) => {
        const url =
            `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

    // 718–730
    const registers = [
        { name: "PVTotalPowerRaw", start: 718, scale: 10 }, // ⚠️ опционально

        { name: "PV5Voltage", start: 719, scale: 0.1 },
        { name: "PV6Voltage", start: 720, scale: 0.1 },
        { name: "PV7Voltage", start: 721, scale: 0.1 },
        { name: "PV8Voltage", start: 722, scale: 0.1 },

        { name: "PV5Current", start: 723, scale: 0.1 },
        { name: "PV6Current", start: 724, scale: 0.1 },
        { name: "PV7Current", start: 725, scale: 0.1 },
        { name: "PV8Current", start: 726, scale: 0.1 },

        { name: "PV5Power", start: 727, scale: 10 },
        { name: "PV6Power", start: 728, scale: 10 },
        { name: "PV7Power", start: 729, scale: 10 },
        { name: "PV8Power", start: 730, scale: 10 },
    ];

    const startReg = registers[0].start;
    const count = registers.length;

    try {
        const data = await readBlock(startReg, count);

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                results[reg.name] = data.data[idx] * reg.scale;
            });

            // ✅ суммарная мощность PV5–PV8
            results.PVExtTotalPower =
                (results.PV5Power || 0) +
                (results.PV6Power || 0) +
                (results.PV7Power || 0) +
                (results.PV8Power || 0);
        }

    } catch (err) {
        console.error("Ошибка чтения расширенных PV регистров:", err);
    }

    console.log("☀️ PV5–PV8 results:", results);
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
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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
            `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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


            results.LoadPhaseCurrentA = results.LoadPhasePowerA / (results.LoadPhaseVoltageA || 1); // 647
            results.LoadPhaseCurrentB = results.LoadPhasePowerB / (results.LoadPhaseVoltageB || 1); // 648
            results.LoadPhaseCurrentC = results.LoadPhasePowerC / (results.LoadPhaseVoltageC || 1); // 649 

        }

    } catch (err) {
        console.error("Ошибка чтения регистров нагрузки:", err);
    }

    console.log("Parsed LOAD results:", results);
    return results;
}




async function readServiceRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    // Универсальная функция чтения блоков регистров
    const readBlock = async (start, count) => {
        const url =
            `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

    const startReg = 551;
    const count = 8; // 551–558

    try {
        const data = await readBlock(startReg, count);

        if (data.ok && data.data?.length === count) {
            const regs = data.data;

            // === Turn on/off status ===
            results.powerOn = (regs[0] & 0x1) === 1; // 551, Bit0: 1 = on, 0 = off

            // === AC relay status ===
            results.invRelay = (regs[1] & 0x1) !== 0;      // 552, Bit0
            results.loadRelay = (regs[1] & 0x2) !== 0;     // 552, Bit1
            results.gridRelay = (regs[1] & 0x4) !== 0;     // 552, Bit2
            results.genRelay = (regs[1] & 0x8) !== 0;      // 552, Bit3
            results.gridGivePowerRelay = (regs[1] & 0x10) !== 0; // 552, Bit4
            results.dryContact1 = (regs[1] & 0x80) !== 0;  // 552, Bit7
            results.dryContact2 = (regs[1] & 0x100) !== 0; // 552, Bit8

            // === Warning messages ===
            results.fanWarning = (regs[2] & 0x2) !== 0;          // 553, Bit1
            results.gridPhaseWrong = (regs[2] & 0x4) !== 0;      // 553, Bit2
            results.batteryLostWarning = (regs[3] & 0x4000) !== 0; // 554, Bit14
            results.parallelCommWarning = (regs[3] & 0x8000) !== 0; // 554, Bit15

            // === Fault information ===
            results.fault1 = regs[4]; // 555
            results.fault2 = regs[5]; // 556
            results.fault3 = regs[6]; // 557
            results.fault4 = regs[7]; // 558
        }

    } catch (err) {
        console.error("Ошибка чтения сервисных регистров:", err);
    }

    console.log("Обработанные сервисные результаты:", results);
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
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

    const readBlock = async (start, count) => {
        const url =
            `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

    const startReg = 598;
    const totalCount = 23; // с 598 по 620 включительно

    try {
        const data = await readBlock(startReg, totalCount);

        if (data.ok && data.data?.length === totalCount) {

            // === Первый блок ===
            results.inputVoltageL1 = data.data[0] * 0.1;
            results.inputVoltageL2 = data.data[1] * 0.1;
            results.inputVoltageL3 = data.data[2] * 0.1;

            results.lineVoltageAB = data.data[3] * 0.1;
            results.lineVoltageBC = data.data[4] * 0.1;
            results.lineVoltageCA = data.data[5] * 0.1;

            results.inputPowerL1 = data.data[6];
            results.inputPowerL2 = data.data[7];
            results.inputPowerL3 = data.data[8];
            results.totalApparentPower = data.data[10];
            results.inputPowerTotal = data.data[9];
            results.inputFrequency  = data.data[11] * 0.01;

            // === Второй блок ===
            results.inputCurrentL1 = data.data[12] * 0.01;
            results.inputCurrentL2 = data.data[13] * 0.01;
            results.inputCurrentL3 = data.data[14] * 0.01;

            results.outCurrentA = data.data[15] * 0.01;
            results.outCurrentB = data.data[16] * 0.01;
            results.outCurrentC = data.data[17] * 0.01;

            results.outPowerA = data.data[18];
            results.outPowerB = data.data[19];
            results.outPowerC = data.data[20];

            results.outTotalPower         = data.data[21];
            results.outTotalApparentPower = data.data[22];
        }

    } catch (err) {
        console.error("Ошибка чтения блока регистров:", err);
    }

    console.log("Обработанные GRID результаты:", results);
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
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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



async function readEnergyServiceRegisters(host, port, slave_id, object_id, protocol) {
    const results = {};

    const registers = [
        { start: 101, name: "batteryFloatVoltage", scale: 0.1 },        // V
        { start: 102, name: "batteryCapacityAh", scale: 1 },             // Ah
        { start: 103, name: "batteryEmptyVoltage", scale: 0.1 },        // V
        { start: 104, name: "zeroExportPower", scale: 1 },
        { start: 105, name: "equalizationDayCycle", scale: 1 },          // days
        { start: 106, name: "equalizationTime", scale: 0.1 },            // hours (MCU 0–100)
        { start: 107, name: "tempCompensation", scale: 1, signed: true },// mV/℃
        { start: 108, name: "batteryMaxChargeCurrent", scale: 1 },       // A
        { start: 109, name: "batteryMaxDischargeCurrent", scale: 1 },    // A
        { start: 110, name: "parallelBatteryEnable", bool: true },
        { start: 111, name: "batteryWorkMode", enum: { 0: "voltage", 1: "capacity", 2: "no_battery" }},
        { start: 112, name: "liBatteryWakeup", bits: { batt1: 0, batt2: 8 } }, // Bit0: battery1, Bit8: battery2
        { start: 113, name: "batteryResistance", scale: 1 },             // mΩ
        { start: 114, name: "batteryChargeEfficiency", scale: 0.1 },     // %
        { start: 115, name: "batteryCapacityShutdown", scale: 1 },       // %
        { start: 116, name: "batteryCapacityRestart", scale: 1 },
        { start: 117, name: "batteryCapacityLowBatt", scale: 1 },
        { start: 118, name: "batteryVoltageShutdown", scale: 0.1 },     // V
        { start: 119, name: "batteryVoltageRestart", scale: 0.1 },
        { start: 120, name: "batteryVoltageLowBatt", scale: 0.1 },
        { start: 121, name: "generatorMaxRunTime", scale: 0.1 },          // hours
        { start: 122, name: "generatorCoolingTime", scale: 0.1 },
        { start: 123, name: "generatorChargeStartVoltage", scale: 0.1 },
        { start: 124, name: "generatorChargeStartCapacity", scale: 1 },  // %
        { start: 125, name: "generatorChargeCurrent", scale: 1 },         // A
        { start: 126, name: "gridChargeStartVoltage", scale: 0.1 },
        { start: 127, name: "gridChargeStartCapacity", scale: 1 },
        { start: 128, name: "gridChargeCurrent", scale: 1 },
        { start: 129, name: "generatorChargeEnable", bool: true },
        { start: 130, name: "gridChargeEnable", bool: true },
    ];

    const startReg = registers[0].start;
    const count = registers.length;

    const url =
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

        if (data.ok && data.data?.length === count) {
            registers.forEach((reg, idx) => {
                let val = data.data[idx];

                if (reg.signed && val > 0x7FFF) {
                    val -= 0x10000;
                }

                if (reg.bool) {
                    results[reg.name] = val !== 0;
                } 
                else if (reg.enum) {
                    results[reg.name] = reg.enum[val] ?? val;
                }
                else if (reg.bits) {
                    results[reg.name] = {};
                    for (const [key, bit] of Object.entries(reg.bits)) {
                        results[reg.name][key] = ((val >> bit) & 1) === 0;
                    }
                }
                else {
                    results[reg.name] = val * reg.scale;
                }
            });
        }
    } catch (err) {
        console.error("Ошибка чтения регистров энергии (101–130):", err);
    }

    console.log("⚙️ Energy service registers:", results);
    return results;
}



// Обновленная функция readDeyeFaults
async function readDeyeFaults(host, port, slave_id, object_id, protocol) {
    const startReg = 553;
    const count = 6;

    const url =
        `${API_BASE_URL}/api/modbus_tcp/v1/read` +
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

        if (!data.ok || !Array.isArray(data.data)) {
            console.warn("⚠️ Deye faults read failed:", data);
            return null;
        }

        const [w1, w2, f1, f2, f3, f4] = data.data;

        console.debug("🚨 Deye fault raw registers:", {
            553: `0x${w1.toString(16)}`,
            554: `0x${w2.toString(16)}`,
            555: `0x${f1.toString(16)}`,
            556: `0x${f2.toString(16)}`,
            557: `0x${f3.toString(16)}`,
            558: `0x${f4.toString(16)}`
        });

        return {
            warnings: decodeDeyeWarnings([w1, w2]),
            faults: decodeDeyeFaults([f1, f2, f3, f4])
        };

    } catch (err) {
        console.error("❌ Error reading Deye faults:", err);
        return null;
    }
}


function decodeDeyeFaults(words) {
    const faults = [];

    words.forEach((word, wordIndex) => {
        for (let bit = 0; bit < 16; bit++) {
            if (!(word & (1 << bit))) continue;

            const faultNumber = wordIndex * 16 + bit + 1; // F01–F64
            const info = DEYE_FAULT_INFO[faultNumber];

            if (!info || info.description === "Reserved") continue;

            faults.push({
                code: info.name,              // Fxx
                name: info.description,
                solution: info.solution
            });
        }
    });

    return faults;
}



// Обновленная функция декодирования предупреждений
function decodeDeyeWarnings(words) {
    const warnings = [];

    words.forEach((word, wordIndex) => {
        for (let bit = 0; bit < 16; bit++) {
            if (!(word & (1 << bit))) continue;

            const warningNumber = wordIndex * 16 + bit + 1; // W01–W32
            const info = DEYE_WARNING_INFO[warningNumber];

            if (!info || info.description === "Reserved") continue;

            warnings.push({
                code: info.name,              // Wxx
                name: info.description,
                solution: info.solution
            });
        }
    });

    return warnings;
}







function calculateBatterySOCVoltage(battData, energyServiceData) {
    if (!battData || !energyServiceData) return null;

    if (energyServiceData.batteryWorkMode !== "voltage") {
        return null; // не voltage-режим
    }

    const v1 = battData.battery1Voltage;
    const v2 = battData.battery2Voltage;

    if (typeof v1 !== "number" || typeof v2 !== "number") {
        return null;
    }

    const vAvg = (v1 + v2) / 2;

    const vMax = energyServiceData.batteryFloatVoltage;      // 100%
    const vMin = energyServiceData.batteryVoltageShutdown;  // 0%

    if (vMax <= vMin) return null;

    let soc = ((vAvg - vMin) / (vMax - vMin)) * 100;

    // 🔒 защита от выхода за пределы
    soc = Math.max(0, Math.min(100, soc));

    return Math.round(soc * 10) / 10; // 1 знак после запятой
}


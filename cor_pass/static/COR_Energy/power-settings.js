


 function updateBatteryModal(data) {
    document.getElementById('batt_voltage').textContent = data.voltage.toFixed(2);
    document.getElementById('batt_curr').textContent = data.current.toFixed(2);
    document.getElementById('chargeLevel').textContent = data.soc.toFixed(2);
    document.getElementById('Bat_Temp').textContent = data.temperature.toFixed(2);
    document.getElementById('PowerLevel').textContent = (data.voltage*data.current).toFixed(2);
}

async function fetchStatus() {
    try {
      const res = await fetch('/api/modbus/battery_status');
      const data = await res.json();
                batteryData = {
                    soc: data.soc,
                    voltage: data.voltage,
                    current: data.current,
                    soh: data.soh,
                    temperature:data.temperature
                };
                updateBatteryFill(batteryData.soc);
                updateBatteryFlow((data.voltage*data.current));
                updateBatteryModal(batteryData);
    } catch (err) {
      console.error("Ошибка при получении данных батареи:", err);
    }
  }

  async function fetchInverterPowerStatus() {
    try {
        const response = await fetch('/api/modbus/inverter_power_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка при запросе данных мощности');
        }

        const data = await response.json();
        updateLoadModal(data);
        return {
            success: true,
            data: {
                dc_power: data.dc_power,
                ac_output: {
                    l1: data.ac_output.l1,
                    l2: data.ac_output.l2,
                    l3: data.ac_output.l3,
                    total: data.ac_output.total
                }
            }
        };
    } catch (error) {
        console.error('❗ Ошибка получения данных мощности инвертора:', error);
        return {
            success: false,
            error: error.message || 'Modbus ошибка'
        };
    }
}


async function fetchEssAcStatus() {
    try {
        const response = await fetch('/api/modbus/ess_ac_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка при запросе AC параметров ESS');
        }

        const data = await response.json();
        updateEssAcDisplay(data);
        updateNetworkFlow((data.input.powers.total / 10));

        return {
            success: true,
            data: data
        };
    } catch (error) {
        console.error('❗ Ошибка получения AC параметров ESS:', error);
        return {
            success: false,
            error: error.message || 'Modbus ошибка'
        };
    }
}



async function fetchVebusStatus() {
    try {
        const res = await fetch('/api/modbus/vebus_status');
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Ошибка запроса VE.Bus");
        }

        const data = await res.json();
        updateVebusDisplay(data);
       
        return {
            success: true,
            data: data
        };
    } catch (error) {
        console.error("❗ Ошибка получения VE.Bus данных:", error);
        return {
            success: false,
            error: error.message || "Modbus ошибка"
        };
    }
}

function updateLoadModal(data) {
    // Обновляем данные по фазам (мощность в ваттах, преобразуем в кВт)
    document.getElementById('powerPhaseA').textContent = (data.ac_output.l1 / 1000).toFixed(2);
    document.getElementById('powerPhaseB').textContent = (data.ac_output.l2 / 1000).toFixed(2);
    document.getElementById('powerPhaseC').textContent = (data.ac_output.l3 / 1000).toFixed(2);
    document.getElementById('total_load').textContent = (data.ac_output.total / 1000).toFixed(2);
    updateLoadIndicator(data.ac_output.total / 1000); 
}

function updateEssAcDisplay(data) {
    
    document.getElementById('inputVoltageL1').textContent = data.input.voltages.l1.toFixed(1);
    document.getElementById('inputVoltageL2').textContent = data.input.voltages.l2.toFixed(1);
    document.getElementById('inputVoltageL3').textContent = data.input.voltages.l3.toFixed(1);
    
    document.getElementById('inputCurrentL1').textContent = data.input.currents.l1.toFixed(1);
    document.getElementById('inputCurrentL2').textContent = data.input.currents.l2.toFixed(1);
    document.getElementById('inputCurrentL3').textContent = data.input.currents.l3.toFixed(1); 
    
    document.getElementById('inputFrequencyL1').textContent = data.input.frequencies.l1.toFixed(2);
    document.getElementById('inputFrequencyL2').textContent = data.input.frequencies.l2.toFixed(2);
    document.getElementById('inputFrequencyL3').textContent = data.input.frequencies.l3.toFixed(2);
   
    document.getElementById('inputPowerL1').textContent = (data.input.powers.l1 / 1000).toFixed(2);
    document.getElementById('inputPowerL2').textContent = (data.input.powers.l2 / 1000).toFixed(2);
    document.getElementById('inputPowerL3').textContent = (data.input.powers.l3 / 1000).toFixed(2);
    document.getElementById('inputPowerTotal').textContent = (data.input.powers.total / 1000).toFixed(2); 

    document.getElementById('outputVoltageL1').textContent = data.output.voltages.l1.toFixed(1);
    document.getElementById('outputVoltageL2').textContent = data.output.voltages.l2.toFixed(1);
    document.getElementById('outputVoltageL3').textContent = data.output.voltages.l3.toFixed(1);
    
    document.getElementById('outputCurrentL1').textContent = data.output.currents.l1.toFixed(1);
    document.getElementById('outputCurrentL2').textContent = data.output.currents.l2.toFixed(1);
    document.getElementById('outputCurrentL3').textContent = data.output.currents.l3.toFixed(1);
}




function updateVebusDisplay(data) {
/*    document.getElementById('vebusFreq').textContent = data.output_frequency_hz.toFixed(2);
    document.getElementById('vebusCurrentLimit').textContent = data.input_current_limit_a.toFixed(1);
    
    document.getElementById('vebusPowerL1').textContent = (data.output_power.l1 / 1000).toFixed(2);
    document.getElementById('vebusPowerL2').textContent = (data.output_power.l2 / 1000).toFixed(2);
    document.getElementById('vebusPowerL3').textContent = (data.output_power.l3 / 1000).toFixed(2);

    document.getElementById('vebusBatteryVolt').textContent = data.battery_voltage_v.toFixed(2);
    document.getElementById('vebusBatteryCurr').textContent = data.battery_current_a.toFixed(2);

    document.getElementById('vebusPhases').textContent = data.phase_count;
    document.getElementById('vebusActiveInput').textContent = data.active_input; */
  //  document.getElementById('vebusSOC').textContent = data.soc_percent.toFixed(1);
  /*  document.getElementById('vebusState').textContent = data.vebus_state;
    document.getElementById('vebusError').textContent = data.vebus_error;
    document.getElementById('vebusSwitchPos').textContent = data.switch_position;

    document.getElementById('vebusTempAlarm').textContent = data.alarms.temperature;
    document.getElementById('vebusLowBattAlarm').textContent = data.alarms.low_battery;
    document.getElementById('vebusOverloadAlarm').textContent = data.alarms.overload;

    document.getElementById('vebusSetpointL1').textContent = data.ess.power_setpoint_l1;
    document.getElementById('vebusDisableCharge').textContent = data.ess.disable_charge;
    document.getElementById('vebusDisableFeed').textContent = data.ess.disable_feed;
    document.getElementById('vebusSetpointL2').textContent = data.ess.power_setpoint_l2;
    document.getElementById('vebusSetpointL3').textContent = data.ess.power_setpoint_l3; */
}



async function saveBatterySettings() {
    const sliderValue = parseInt(document.getElementById("State_Of_Сharge").value, 10);

    try {
        const res = await fetch('/api/modbus/vebus/soc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ soc_threshold: sliderValue })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Ошибка записи SOC");
        }

        document.getElementById('confirmationMessage').textContent = "✅ Настройки сохранены";
        document.getElementById('confirmationMessage').style.display = "block";
    } catch (err) {
        console.error("❗ Ошибка установки порога SOC:", err);
        document.getElementById('confirmationMessage').textContent = "❌ Ошибка сохранения";
        document.getElementById('confirmationMessage').style.color = "red";
        document.getElementById('confirmationMessage').style.display = "block";
    }
}


async function fetchEss() {
    try {
      const response = await fetch('/api/modbus/ess_settings', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        }
      });
  
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка чтения ESS настроек');
      }
  
      const data = await response.json();
      const essMode = data.ess_mode;
        document.getElementById('mode_display').innerText = modeNames[essMode] || "Неизвестно";

        const radios = document.getElementsByName('mode');
        for (const radio of radios) {
        radio.checked = parseInt(radio.value) === essMode;
        }
     // updateEssSettingsDisplay(data);
        const socValue = data.minimum_soc_limit || 40;
     //   document.getElementById('State_Of_Сharge').value = socValue;
        document.getElementById('vebusSOC').textContent = socValue;
      return {
        success: true,
        data: data
      };
    } catch (err) {
      console.error("❗ Ошибка получения ESS настроек:", err);
      return {
        success: false,
        error: err.message || 'Modbus ошибка'
      };
    }
  }







async function fetchEssAdvancedSettings() {
    try {
        const res = await fetch('/api/modbus/ess_advanced_settings');
        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || 'Ошибка запроса ESS настроек');
        }

        const data = await res.json();
        updateEssAdvancedDisplay(data);
    } catch (err) {
        console.error("❗ Ошибка получения ESS расширенных настроек:", err);
    }
}

function updateEssAdvancedDisplay(data) {
    document.getElementById("ac_setpoint").textContent = data.ac_power_setpoint + " W";
    document.getElementById("charge_limit").textContent = data.max_charge_percent + " %";
    document.getElementById("discharge_limit").textContent = data.max_discharge_percent + " %";
    document.getElementById("fine_setpoint").textContent = data.ac_power_setpoint_fine + " W";
    document.getElementById("discharge_power").textContent = data.max_discharge_power + " W";
    document.getElementById("dvcc_current").textContent = data.dvcc_max_charge_current + " A";
    document.getElementById("feedin_power").textContent = data.max_feed_in_power + " W";
    document.getElementById("feedin_dc").textContent = data.overvoltage_feed_in ? "Вкл" : "Выкл";
    document.getElementById("feedin_ac").textContent = data.prevent_feedback ? "Отключено" : "Разрешено";
    document.getElementById("grid_limit").textContent = data.grid_limiting_status ? "Активно" : "Нет";
    document.getElementById("charge_voltage").textContent = data.max_charge_voltage + " В";
    document.getElementById("input1_src").textContent = formatInputSource(data.ac_input_1_source);
    document.getElementById("input2_src").textContent = formatInputSource(data.ac_input_2_source);
}

function formatInputSource(code) {
    const sources = {
        0: "Не используется",
        1: "Сеть",
        2: "Генератор",
        3: "Берег"
    };
    return sources[code] || `Код ${code}`;
}



// Функция сохранения значения
async function saveAcSetpointFine() {
    const sliderValue = parseInt(document.getElementById("ac_setpoint_fine_slider").value, 10);
    
    try {
        const res = await fetch('/api/modbus/ess_advanced_settings/setpoint_fine', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                ac_power_setpoint_fine: sliderValue 
            })
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Ошибка записи Setpoint Fine");
        }

        const confirmation = document.getElementById('setpoint_confirmation');
        confirmation.textContent = "✅ Настройки сохранены";
        confirmation.style.color = "green";
        confirmation.style.display = "block";
        
        // Обновляем данные на странице
        fetchEssAdvancedSettings();
        
    } catch (err) {
        console.error("❗ Ошибка установки Setpoint Fine:", err);
        const confirmation = document.getElementById('setpoint_confirmation');
        confirmation.textContent = "❌ Ошибка сохранения: " + err.message;
        confirmation.style.color = "red";
        confirmation.style.display = "block";
    }
}



async function toggleGridLimitingStatus(enabled) {
    try {
        const res = await fetch('/api/ess/grid_limiting_status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Ошибка запроса");
        }

        console.log("✅ Успешно обновлено:", data);
    } catch (err) {
        console.error("❌ Ошибка при обновлении grid_limiting_status:", err);
    }
}


async function fetchGridLimitingStatus() {
    try {
        const res = await fetch('/api/ess_advanced_settings');
        const data = await res.json();

        const switchElement = document.getElementById('gridLimitingSwitch');
        switchElement.checked = (data.grid_limiting_status === 1);
    } catch (e) {
        console.error("Ошибка загрузки состояния ограничения отдачи:", e);
    }
}

async function handleGridLimitingToggle(enabled) {
    await toggleGridLimitingStatus(enabled);
}


async function fetchSolarChargerStatus() {
    try {
        const response = await fetch('/api/modbus/solarchargers_status');
        if (!response.ok) {
            throw new Error('Ошибка запроса данных солнечных контроллеров');
        }

        const data = await response.json();
        console.log('✅ Принятые данные (сырье):', data);

        let totalAllPower = 0;
        const chargersSummary = {};

        for (const [chargerId, values] of Object.entries(data)) {
            if (chargerId === "total_power_all_devices") continue;

            let chargerTotalPower = 0;
            const panels = [];

            for (let i = 0; i < 4; i++) {
                const voltage = values[`pv_voltage_${i}`];
                const power = values[`pv_power_${i}`];

                let current = null;
                if (voltage !== null && voltage > 0 && power !== null) {
                    current = parseFloat((power / voltage).toFixed(2));
                }

                if (power !== null) {
                    chargerTotalPower += power;
                }

                panels.push({
                    panel: i + 1,
                    voltage,
                    power,
                    current
                });
            }

            totalAllPower += chargerTotalPower;

            chargersSummary[chargerId] = {
                panels,
                totalPower: parseFloat(chargerTotalPower.toFixed(2))
            };
        }

        console.log('📊 Расчёт по каждому MPPT:', chargersSummary);
        console.log('🔆 Общая мощность всех MPPT:', totalAllPower.toFixed(2), 'Вт');

        // Таблица в модальном окне
        const container = document.getElementById('solarTableContainer');
        container.innerHTML = '';

        for (const [chargerId, charger] of Object.entries(chargersSummary)) {
            const table = document.createElement('table');
            table.className = 'phase-table'; // можешь переименовать под стиль

            const header = `
                <thead>
                    <tr>
                        <th colspan="4">${chargerId.toUpperCase()}</th>
                    </tr>
                    <tr>
                        <th>Панель</th>
                        <th>Напряжение (В)</th>        
                        <th>Ток (А)</th>
                        <th>Мощность (Вт)</th>
                    </tr>
                </thead>
            `;

            const rows = charger.panels.map(p => `
                <tr>
                    <td>Панель ${p.panel}</td>
                    <td>${p.voltage ?? '—'}</td>
                    <td>${p.current ?? '—'}</td>
                    <td>${p.power ?? '—'}</td>
                </tr>
            `).join('');

            const footer = `
                <tfoot>
                    <tr>
                        <td colspan="3"><strong>Итого по устройству</strong></td>
                        <td><strong>${charger.totalPower}</strong> Вт</td>
                    </tr>
                </tfoot>
            `;

            table.innerHTML = header + `<tbody>${rows}</tbody>` + footer;
            container.appendChild(table);
        }

        // Общая мощность всех MPPT
        const totalText = document.createElement('p');
        totalText.style = "margin-top:10px; font-weight: bold;";
        totalText.innerText = `🔆 Общая мощность всех MPPT: ${totalAllPower.toFixed(2)} Вт`;
        container.appendChild(totalText);

        // Открыть модальное окно
       // document.getElementById('SolarModal').style.display = 'block';

    } catch (error) {
        console.error('❗ Ошибка при получении данных:', error);
    }
}
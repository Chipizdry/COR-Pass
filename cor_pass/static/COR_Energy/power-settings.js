


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
   // const totalPower = (data.ac_output.total / 1000).toFixed(2);
   // if (typeof updatePowerChart === 'function') {
  //      updatePowerChart(parseFloat(totalPower));
  //  }
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

    const totalPower = (data.input.powers.total / 1000).toFixed(2);
    if (typeof updatePowerChart === 'function') {
        updatePowerChart(parseFloat(totalPower));
    }
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


// Модифицированная функция сохранения
async function saveBatterySettings() {
    const slider = document.getElementById('State_Of_Сharge');
    const sliderValue = parseInt(slider.value, 10);

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

        // Обновляем исходное значение после успешного сохранения
        initialSocValue = sliderValue;
        document.getElementById('vebusSOC').textContent = sliderValue;
        isSliderChanged = false;

        // Очищаем таймер
        if (socChangeTimeout) {
            clearTimeout(socChangeTimeout);
            socChangeTimeout = null;
        }

        showConfirmationMessage("✅ Настройки сохранены", true);
        return true;
    } catch (err) {
        console.error("❗ Ошибка установки порога SOC:", err);
        showConfirmationMessage("❌ Ошибка сохранения", false);
        resetSocSlider();
        return false;
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
        const socValue = data.minimum_soc_limit || 40;
        updateBatteryLimitLine(socValue);
        // Обновляем исходное значение только если ползунок не был изменен пользователем
        if (!isSliderChanged) {
            initialSocValue = socValue;
            document.getElementById('State_Of_Сharge').value = socValue;
            document.getElementById('socSliderValue').textContent = socValue;
        }
        
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


            // Устанавливаем начальное значение для ползунка отдачи в сеть
            const feedInValue = data.ac_power_setpoint_fine || 0;
            const InverterPowerValue = data.max_discharge_power || 0;
            // Обновляем исходное значение только если ползунок не был изменен пользователем
            if (!isFeedInSliderChanged) {
                initialFeedInValue = feedInValue;
                document.getElementById('feedInPowerSlider').value = feedInValue;
                document.getElementById('feedInSliderValue').textContent = feedInValue;
            }
            if (!inverterPowerChanged) {
                initialInverterPowerValue = InverterPowerValue;
                document.getElementById('InverterPowerSlider').value = InverterPowerValue;
                document.getElementById('InverterSliderValue').textContent = InverterPowerValue;
            }


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
   // console.log("Ограничение выдачи:",data.grid_limiting_status);
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



// Функция сохранения значения отдачи в сеть
async function saveAcSetpoint() {
    const sliderValue = parseInt(document.getElementById('feedInPowerSlider').value, 10);
    
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

        // Обновляем исходное значение после успешного сохранения
        initialFeedInValue = sliderValue;
        isFeedInSliderChanged = false;

        // Очищаем таймер
        if (feedInChangeTimeout) {
            clearTimeout(feedInChangeTimeout);
            feedInChangeTimeout = null;
        }

        showFeedInConfirmationMessage("✅ Настройки сохранены", true);
        
        // Обновляем данные на странице
        fetchEssAdvancedSettings();
        
    } catch (err) {
        console.error("❗ Ошибка установки Setpoint Fine:", err);
        showFeedInConfirmationMessage("❌ Ошибка сохранения: " + err.message, false);
        resetFeedInSlider();
    }
}


async function saveInverterPower() {
    const value = parseInt(document.getElementById('InverterPowerSlider').value, 10);

    try {
        const res = await fetch('/api/modbus/ess_advanced_settings/inverter_power', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ inverter_power: value })
        });

        if (!res.ok) throw new Error((await res.json()).detail || "Ошибка записи регистра 2704");

        initialInverterPowerValue = value;
        isInverterSliderChanged = false;
        document.getElementById('saveInverterPower').disabled = true;

        if (inverterChangeTimeout) {
            clearTimeout(inverterChangeTimeout);
            inverterChangeTimeout = null;
        }

        showInverterConfirmationMessage("✅ Успешно сохранено", true);
    } catch (err) {
        showInverterConfirmationMessage("❌ Ошибка: " + err.message, false);
    }
}

async function toggleGridLimitingStatus(enabled) {
    try {
        const res = await fetch('/api/modbus/ess/grid_limiting_status', {
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
        const res = await fetch('/api/modbus/ess_advanced_settings');
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
        // console.log('✅ Принятые данные (сырье):', data);

        const container = document.getElementById('solarTableContainer');
        container.innerHTML = ''; // Очистка

        const template = document.getElementById('solarTableTemplate');

        // Обрабатываем каждый контроллер
        for (const [chargerId, values] of Object.entries(data)) {
            // Пропускаем поле с общей суммой (оно будет обработано отдельно)
            if (chargerId === "total_pv_power") continue;

            let chargerTotalPower = 0;
            const clone = template.content.cloneNode(true);

            // Заголовок устройства
            clone.querySelector('.charger-title').innerText = chargerId.toUpperCase();

            const tbody = clone.querySelector('.table-body');

            // Обрабатываем каждый PV вход (0-3)
            for (let i = 0; i < 4; i++) {
                const voltage = values[`pv_voltage_${i}`];
                const power = values[`pv_power_${i}`];

                // Рассчитываем ток, если есть напряжение и мощность
                let current = null;
                if (voltage !== null && voltage > 0 && power !== null) {
                    current = parseFloat((power / voltage).toFixed(2));
                }

                // Суммируем мощность по устройству
                if (power !== null) {
                    chargerTotalPower += power;
                }

                // Создаем строку таблицы
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>PV ${i + 1}</td>
                    <td>${voltage ?? '—'}</td>
                    <td>${current ?? '—'}</td>
                    <td>${power ?? '—'}</td>
                `;
                tbody.appendChild(row);
            }

            // Установка итогов по устройству
            clone.querySelector('.device-total').innerText = chargerTotalPower.toFixed(2);
            container.appendChild(clone);
        }

        // Установка общей суммы из данных API (вместо самостоятельного расчета)
        const totalPowerFromAPI = data.total_pv_power || 0;
        document.getElementById('totalAllPower').innerText = totalPowerFromAPI.toFixed(2);
        updateSolarPowerIndicator(totalPowerFromAPI);

    } catch (error) {
        console.error('❗ Ошибка при получении данных:', error);
        // Можно добавить отображение ошибки в интерфейсе
        document.getElementById('solarTableContainer').innerHTML = 
            '<div class="error-message">Ошибка загрузки данных</div>';
    }
}


async function fetchDynamicEssSettings() {
    try {
      const response = await fetch('/api/modbus/dynamic_ess_settings');
      if (!response.ok) throw new Error("Ошибка запроса: " + response.status);
      const data = await response.json();

      for (const [key, value] of Object.entries(data)) {
        const cell = document.getElementById(key);
        if (cell) cell.textContent = value;
      }
    } catch (err) {
      document.getElementById("error").textContent = "❗ Ошибка загрузки данных: " + err.message;
    }
  }
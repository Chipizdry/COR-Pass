


export const MODAL_SCHEMAS = {
    Deye: {
        "SUN-80K-SG04LP3": {
            battery: {
                title: "Батарея",
                fields: [
                    { id: "soc", label: "SOC", unit: "%", source: "battery1SOC" },
                    { id: "voltage", label: "Напряжение", unit: "V", source: "battery1Voltage" },
                    { id: "power", label: "Мощность", unit: "kW", source: "batteryTotalPower" },
                    { id: "temp", label: "Температура", unit: "°C", source: "battery1Temperature" }
                ]
            },
            generator: {
                title: "Генератор",
                fields: [
                    { id: "power", label: "Мощность", unit: "kW", source: "GenTotalPower" },
                    { id: "va", label: "Фаза A", unit: "V", source: "GenPhaseVoltageA" }
                ]
            }
        },

        default: {
            battery: {
                title: "Батарея",
                fields: [
                    { id: "soc", label: "SOC", unit: "%", source: "battery1SOC" },
                    { id: "power", label: "Мощность", unit: "kW", source: "batteryTotalPower" }
                ]
            }
        }
    },

    Victrone: {
        default: {
            battery: {  },
            generator: {  } ,
            grid: {  },
            load: {  },
            solar: {  }
        }
    },
       
};

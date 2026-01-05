


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
                enabled: true,
                modalId: "batteryModal",
                title: "Батарея",

                blocks: [
                    {
                        type: "fieldList",
                        title: "Батарея 1",
                        fields: [
                            { label: "SOC", unit: "%", source: "battery1SOC" },
                            { label: "Напряжение", unit: "V", source: "battery1Voltage" },
                            { label: "Ток", unit: "A", source: "battery1Current" },
                            { label: "Мощность", unit: "W", source: "battery1Power" }                   
                        ]
                    },

                    {
                        type: "fieldList",
                        title: "Батарея 2",
                        fields: [
                            { label: "SOC", unit: "%", source: "battery2SOC" },
                            { label: "Напряжение", unit: "V", source: "battery2Voltage" },
                            { label: "Ток", unit: "A", source: "battery2Current" },
                            { label: "Мощность", unit: "W", source: "battery2Power" }                  
                        ]
                    },
                    {
                        type: "slider",
                        label: "Минимальный SOC",
                        min: 0,
                        max: 99,
                        step: 1,
                        source: "batteryMinSoc",
                        saveAction: "saveBatterySettings"
                    }
                ]
            },

            grid: {
                enabled: true,
                modalId: "GridSettingsModal",
                title: "Сеть",

                blocks: [
                    {
                        type: "phaseTable",
                        phases: 3,

                        rows: [
                            {
                                label: "Напряжение",
                                unit: "V",
                                source: ["inputVoltageL1", "inputVoltageL2", "inputVoltageL3"]
                            },
                            {
                                label: "Ток",
                                unit: "A",
                                source: ["inputCurrentL1", "inputCurrentL2", "inputCurrentL3"]
                            },
                            {
                                label: "Мощность",
                                unit: "kW",
                                source: ["inputPowerL1", "inputPowerL2", "inputPowerL3"]
                            }
                        ]
                    },

                    {
                        type: "fieldList",
                        fields: [
                            {
                                label: "Общая мощность",
                                unit: "kW",
                                source: "inputPowerTotal"
                            },
                            {
                                label: "Частота",
                                unit: "Hz",
                                source: "inputFrequency"
                            }

                        ]
                    },

                    {
                        type: "slider",
                        label: "Ограничение отдачи в сеть",
                        min: -100000,
                        max: 100000,
                        step: 100,
                        source: "gridFeedLimit",
                        saveAction: "saveAcSetpoint"
                    }
                ]
            },   

            load: {
                enabled: true,
                modalId: "loadSettingsModal",
                title: "Нагрузка",
                phases: true,

                phaseFields: [
                    { label: "Напряжение", unit: "V", source: ["outputVoltageL1","outputVoltageL2","outputVoltageL3"] },
                    { label: "Ток", unit: "A", source: ["outputCurrentL1","outputCurrentL2","outputCurrentL3"] },
                    { label: "Мощность", unit: "kW", source: ["powerPhaseA","powerPhaseB","powerPhaseC"] }
                ],

                totals: [
                    { label: "Общая нагрузка", unit: "kW", source: "total_load" }
                ]
            },

            solar: {
                enabled: true,
                modalId: "SolarModal",
                title: "Солнечные панели",
                mppt: true
            },

            inverter: {
                enabled: true,
                modalId: "inverterModal",
                title: "Инвертор",
             
            },

            generator: {
                enabled: true
            }
        }
    },



   Axioma: {
        "ISGRID10000": {
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
                enabled: true,
                modalId: "batteryModal",
                title: "Батарея",

                fields: [
                    { id: "soc", label: "SOC", unit: "%", source: "batterySOC" },
                    { id: "voltage", label: "Напряжение", unit: "V", source: "batteryVoltage" },
                    { id: "current", label: "Ток", unit: "A", source: "batteryCurrent" },
                    { id: "power", label: "Мощность", unit: "W", source: "batteryTotalPower" },
                    { id: "temp", label: "Температура", unit: "°C", source: "batteryTemperature" }
                ],

                controls: [
                    {
                        type: "slider",
                        id: "State_Of_Charge",
                        label: "Минимальный SOC",
                        min: 0,
                        max: 99,
                        step: 1,
                        source: "batteryMinSoc",
                        saveAction: "saveBatterySettings"
                    }
                ]
            },

          grid: {
                enabled: true,
                modalId: "GridSettingsModal",
                title: "Сеть",

                blocks: [
                    {
                        type: "singlePhase",
                        fields: [
                            { label: "Напряжение:", unit: "V", source: "inputVoltage" },
                            { label: "Ток:", unit: "A", source: "inputCurrent" },
                            { label: "Мощность:", unit: "kW", source: "inputPower" },
                            { label: "Частота:", unit: "Hz", source: "inputFrequency" }
                        ]
                    }
                ]
            },

            load: {
                enabled: true,
                modalId: "loadSettingsModal",
                title: "Нагрузка",
                phases: true,
                blocks: [
                {
                    type: "singlePhase",
                    fields: [
                        { label: "Напряжение:", unit: "V", source: "outputVoltage" },
                        { label: "Ток:", unit: "A", source: "outputCurrent" },
                        { label: "Мощность:", unit: "W", source: "outputActivePower" },
                        { label: "Частота:", unit: "Hz", source: "outputFrequency" }
                    ]
                }
              ]
            },

            solar: {
                enabled: true,
                modalId: "SolarModal",
                title: "Солнечные панели",
                mppt: true
            },

            inverter: {
                enabled: true,
                modalId: "inverterModal",
                title: "Инвертор",
             
            },

            generator: {
                enabled: false
            }
        }
    },




    Victrone: {
        default: {
            battery: {
                enabled: true,
                modalId: "batteryModal",
                title: "Батарея",

                blocks: [
                    {
                        type: "fieldList",
                        fields: [
                            { label: "SOC", unit: "%", source: "battery1SOC" },
                            { label: "Напряжение", unit: "V", source: "battery1Voltage" },
                            { label: "Ток", unit: "A", source: "battery1Current" },
                            { label: "Мощность", unit: "W", source: "batteryTotalPower" }
                        ]
                    },
                    {
                        type: "slider",
                        label: "Минимальный SOC",
                        min: 0,
                        max: 99,
                        source: "batteryMinSoc",
                        saveAction: "saveBatterySettings"
                    }
                ]
            },
            generator: {  } ,
            grid: {  },
            load: {  },
            solar: {  }
        }
    },
       
};

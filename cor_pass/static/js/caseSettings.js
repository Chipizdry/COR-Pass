document.addEventListener("DOMContentLoaded", (event) => {
    const currentCaseData = {
        macroarchive: 1,
        decalcification: 1,
        caseType: 1,
        materialType: 1,
        urgency: 1,
        containerNumber: 1,
        fixation: 1,
    }


    const selectItemHandler = () => {
        document.querySelectorAll('.caseSettingsItem').forEach(elem => {
            elem.addEventListener('click', (e) => {
                const currentElem = e.target;
                const parent = currentElem.closest(".caseSettingsItemContent")

                parent.querySelectorAll('.caseSettingsItem').forEach( elem => {
                    elem.classList.remove('active')
                })

                currentElem.classList.add('active')


                currentCaseData[parent.dataset.key] = currentElem.dataset.id
            })
        })
    }
    const inputItemHandler = () => {
        document.querySelectorAll('.caseSettingsItemContent input').forEach(elem => {
            elem.addEventListener('change', (e) => {
                const currentElem = e.target;
                const parent = currentElem.closest(".caseSettingsItemContent")

                currentCaseData[parent.dataset.key] = +currentElem.value
            })
        })
    }
    const drawSelectHTML = (title, data, key) => {
        const caseSettingsContent = document.querySelector('#cassetteSettings');

        const cassetteSettingsDataHTML = data.map( (item, index) => {
            return (`<div class="caseSettingsItem ${!index && "active"}" data-id="${item.id}"> ${item.name}</div>`);
        }).join("")

        caseSettingsContent.innerHTML += (`
             <div class="caseSettingsItemWrapper">
                <div class="caseSettingsItemHeader">
                    ${title}
                </div>
                <div class="caseSettingsItemContent df fdc" data-key="${key}">
                    ${cassetteSettingsDataHTML}
                </div>
            </div>
        `)
    }
    const drawInputHTML = (title, key) => {
        const caseSettingsContent = document.querySelector('#cassetteSettings');

        caseSettingsContent.innerHTML += (`
             <div class="caseSettingsItemWrapper">
                <div class="caseSettingsItemHeader">
                    ${title}
                </div>
                <div class="caseSettingsItemContent df fdc" data-key="${key}">
                    <input type="text" placeholder="Введіть число">
                </div>
            </div>
        `)
    }

    const getCaseSettings = () => {
        const caseSettingsData = {
            macroarchive: {
                title: "Макроархів",
                data: [
                    {
                        id: 1,
                        name: "ESS - без залишку"
                    },
                    {
                        id: 2,
                        name: "RSS - залишок"
                    },
                ]
            },
            decalcification: {
                title: "Декальцінація",
                data: [
                    {
                        id: 1,
                        name: "Відсутня"
                    },
                    {
                        id: 2,
                        name: "EDTA"
                    },
                    {
                        id: 3,
                        name: "Кислотна"
                    },
                ],
            },
            caseType: {
                title: "Тип зразків",
                data: [
                    {
                        id: 1,
                        name: "Нативний біоматеріал"
                    },
                    {
                        id: 2,
                        name: "EDTA"
                    },
                    {
                        id: 3,
                        name: "Блоки/скельця"
                    },
                ],
            },
            materialType:  {
                title: "Тип матеріалу",
                data: [
                    {
                        id: 1,
                        name: "R"
                    },
                    {
                        id: 2,
                        name: "B"
                    },
                    {
                        id: 3,
                        name: "C"
                    },
                    {
                        id: 4,
                        name: "CB"
                    },
                    {
                        id: 5,
                        name: "S"
                    },
                    {
                        id: 6,
                        name: "A"
                    },
                    {
                        id: 7,
                        name: "EM"
                    },
                ],
            },
            urgency: {
                title: "Терміновість",
                data: [
                    {
                        id: 1,
                        name: "S"
                    },
                    {
                        id: 2,
                        name: "U"
                    },
                    {
                        id: 3,
                        name: "F"
                    },
                ],
            },
            containerNumber: {
                title: "Фактична кількість контейнерів",
                data: "12"
            },
            fixation: {
                title: "Фіксація",
                data: [
                    {
                        id: 1,
                        name: "10% NBF"
                    },
                    {
                        id: 2,
                        name: "Alcohol"
                    },
                    {
                        id: 3,
                        name: "Osmioum tetroxide"
                    },
                    {
                        id: 4,
                        name: "2% Glutaraldehyde"
                    },
                    {
                        id: 5,
                        name: "Bouin"
                    },
                    {
                        id: 5,
                        name: "Інша"
                    },
                ],
            }
        }

        fetch(`${API_BASE_URL}/api/cases/1a106b65-11b6-429b-aae6-ec84d1804b1a/case_parameters`, )
            .then(res => res.json())
            .then(caseParametrs => {
                console.log(caseParametrs, "caseParametrs")
            })

        drawSelectHTML("Макроархів", caseSettingsData.macroarchive.data, "macroarchive")
        drawSelectHTML("Декальцінація", caseSettingsData.decalcification.data, "decalcification")
        drawSelectHTML("Тип зразків", caseSettingsData.caseType.data, "caseType")
        drawSelectHTML("Тип матеріалу", caseSettingsData.materialType.data, "materialType")
        drawSelectHTML("Терміновість", caseSettingsData.urgency.data, "urgency")
        drawInputHTML("Фактична кількість контейнерів", "containerNumber")
        drawSelectHTML("Фіксація", caseSettingsData.fixation.data, "fixation")
        selectItemHandler()
        inputItemHandler()
    }

    getCaseSettings();
});

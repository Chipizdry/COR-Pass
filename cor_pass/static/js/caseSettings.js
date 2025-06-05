document.addEventListener("DOMContentLoaded", (event) => {
    let currentCaseData = {}

    const caseSettingsData = {
        macro_archive: {
            title: "Макроархів",
            data: [
                {
                    id: "ESS - без остатка",
                    name: "ESS - без залишку"
                },
                {
                    id: "RSS - остаток",
                    name: "RSS - залишок"
                },
            ]
        },
        decalcification: {
            title: "Декальцінація",
            data: [
                {
                    id: "Отсутствует",
                    name: "Відсутня"
                },
                {
                    id: "EDTA",
                    name: "EDTA"
                },
                {
                    id: "Кислотная",
                    name: "Кислотна"
                },
            ],
        },
        sample_type: {
            title: "Тип зразків",
            data: [
                {
                    id: "Нативный биоматериал",
                    name: "Нативний біоматеріал"
                },
                {
                    id: "Блоки/Стекла",
                    name: "Блоки/скельця"
                },
            ],
        },
        material_type:  {
            title: "Тип матеріалу",
            data: [
                {
                    id: "Resectio",
                    name: "R"
                },
                {
                    id: "Biopsy",
                    name: "B"
                },
                {
                    id: "Excisio",
                    name: "E"
                },
                {
                    id: "Cytology",
                    name: "C"
                },
                {
                    id: "Cellblock",
                    name: "X"
                },
                {
                    id: "Second Opinion",
                    name: "S"
                },
                {
                    id: "Autopsy",
                    name: "A"
                },
                {
                    id: "Electron Microscopy",
                    name: "Y"
                },
            ],
        },
        urgency: {
            title: "Терміновість",
            data: [
                {
                    id: "Standard",
                    name: "S"
                },
                {
                    id: "Urgent",
                    name: "U"
                },
                {
                    id: "Frozen",
                    name: "F"
                },
            ],
        },
        container_count_actual: {
            title: "Фактична кількість контейнерів",
            data: "12"
        },
        fixation: {
            title: "Фіксація",
            data: [
                {
                    id: "10% NBF",
                    name: "10% NBF"
                },
                {
                    id: "Alcohol",
                    name: "Alcohol"
                },
                {
                    id: "Osmium",
                    name: "Osmioum tetroxide"
                },
                {
                    id: "2% Glutaraldehyde",
                    name: "2% Glutaraldehyde"
                },
                {
                    id: "Bouin",
                    name: "Bouin"
                },
                {
                    id: "Другое",
                    name: "Інша"
                },
            ],
        }
    }

    const selectItemHandler = () => {
        document.querySelectorAll('.caseSettingsItem').forEach(elem => {
            elem.addEventListener('click', (e) => {
                const currentElem = e.target;
                const parent = currentElem.closest(".caseSettingsItemContent")
                currentCaseData[parent.dataset.key] = currentElem.dataset.id

                parent.querySelectorAll('.caseSettingsItem').forEach( elem => {
                    elem.classList.remove('active')
                })

                currentElem.classList.add('active')
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
    const commentItemHandler = () => {
        document.querySelectorAll('#caseSettingsComments').forEach(elem => {
            elem.addEventListener('change', (e) => {
                const currentElem = e.target;
                currentCaseData["macro_description"] = currentElem.value.trim();
            })
        })
    }
    const drawSelectHTML = (title, data, value, key) => {
        const caseSettingsContent = document.querySelector('#caseSettingsModal .caseSettingsContent');

        const cassetteSettingsDataHTML = data.map( (item, index) => {
            return (`<div class="caseSettingsItem ${item.id === value && "active"}" data-id="${item.id}"> ${item.name}</div>`);
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
    const drawInputHTML = (title, value, key) => {
        const caseSettingsContent = document.querySelector('#caseSettingsModal .caseSettingsContent');

        caseSettingsContent.innerHTML += (`
             <div class="caseSettingsItemWrapper">
                <div class="caseSettingsItemHeader">
                    ${title}
                </div>
                <div class="caseSettingsItemContent df fdc" data-key="${key}">
                    <input type="text" value="${value}" placeholder="Введіть число">
                </div>
            </div>
        `)
    }




    const getCaseSettings = () => {
        drawSelectHTML(caseSettingsData.macro_archive.title, caseSettingsData.macro_archive.data, currentCaseData.macro_archive,"macro_archive")
        drawSelectHTML(caseSettingsData.decalcification.title, caseSettingsData.decalcification.data,  currentCaseData.decalcification,"decalcification")
        drawSelectHTML(caseSettingsData.sample_type.title, caseSettingsData.sample_type.data,  currentCaseData.sample_type,"sample_type")
        drawSelectHTML(caseSettingsData.material_type.title, caseSettingsData.material_type.data, currentCaseData.material_type, "material_type")
        drawSelectHTML(caseSettingsData.urgency.title, caseSettingsData.urgency.data, currentCaseData.urgency, "urgency")
        drawInputHTML("Фактична кількість контейнерів", +currentCaseData.container_count_actual, "container_count_actual")
        drawSelectHTML(caseSettingsData.fixation.title, caseSettingsData.fixation.data, currentCaseData.fixation, "fixation")
        selectItemHandler()
        inputItemHandler()

        document.querySelector('#caseSettingsComments').value = currentCaseData.macro_description || ""
    }
    const openCaseSettingsModal = () => {
        const caseSettingsModal = document.querySelector('#caseSettingsModal');
        const caseSettingsContent = caseSettingsModal.querySelector('.caseSettingsContent');
        caseSettingsContent.innerHTML = ""


        caseSettingsModal.classList.add('open')

        const currentCase = cases[lastActiveCaseIndex];

        fetch(`${API_BASE_URL}/api/cases/${currentCase.id}/case_parameters`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            },
        })
            .then(res => res.json())
            .then(caseParametrs => {
                currentCaseData = caseParametrs;
                getCaseSettings();
            })
    }
    const openCaseSettingsModalHandler = () => {
        document.querySelector('#caseSettingsModalBtn').addEventListener('click', () => {
            openCaseSettingsModal()
        })
    }
    const saveCaseSettings = () => {
        const caseSettingsModal = document.querySelector('#caseSettingsModal');
        const caseSettingsModalButton = caseSettingsModal.querySelector('.modalButton');

        caseSettingsModalButton.addEventListener('click', () => {
            fetch(`${API_BASE_URL}/api/cases/case_parameters`, {
                method: "PATCH",
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(currentCaseData),
            })
                .then(res => res.json())
                .then(() => {
                    caseSettingsModal.classList.remove('open')
                    alert('Параметри кейсу успішно оновлені')
                })
        })

    }


    openCaseSettingsModalHandler();
    saveCaseSettings();
    commentItemHandler();
});

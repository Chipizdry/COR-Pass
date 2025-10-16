document.addEventListener("DOMContentLoaded", (event) => {
    const drawForm = ( formData ) => {
        const formDrawData = [
            {
                label: "Прізвище",
                field: "last_name",
                required: true,
                elementType: "input",
                type: "text",
                placeholder: "",
                half: true
            },
            {
                label: "Ім’я",
                field: "first_name",
                elementType: "input",
                type: "text",
                placeholder: "",
                half: true
            },
            {
                label: "Дата народження",
                field: "date_of_birth",
                elementType: "input",
                type: "date",
            },
            {
                label: "Стать",
                field: "sex",
                elementType: "input",
                type: "radio",
                options: [
                    {
                        id: "M",
                        label: "Чоловіча",
                    },
                    {
                        id: "F",
                        label: "Жіноча",
                    },
                ]
            },
            {
                label: "Email",
                field: "email",
                elementType: "input",
                type: "text",
                placeholder: "",
            },
            {
                label: "Телефон",
                field: "phone",
                elementType: "input",
                type: "text",
                placeholder: "",
            },
            {
                label: "Тип дослідження",
                field: "research_type",
                elementType: "select",
                placeholder: "Оберіть тип дослідження",
                selectData: [
                    {
                        id: "Standard",
                        label: "S"
                    },
                    {
                        id: "Urgent",
                        label: "U"
                    },
                    {
                        id: "Frozen",
                        label: "F"
                    },
                ]
            },
            {
                label: "Тип препарату",
                field: "material_type",
                elementType: "select",
                placeholder: "Оберіть тип препарату",
                selectData: [
                    {
                        id: "Resectio",
                        label: "R"
                    },
                    {
                        id: "Biopsy",
                        label: "B"
                    },
                    {
                        id: "Excisio",
                        label: "E"
                    },
                    {
                        id: "Cytology",
                        label: "C"
                    },
                    {
                        id: "Cellblock",
                        label: "X"
                    },
                    {
                        id: "Second Opinion",
                        label: "S"
                    },
                    {
                        id: "Autopsy",
                        label: "A"
                    },
                    {
                        id: "Electron Microscopy",
                        label: "Y"
                    },
                ]
            },
            {
                label: "Кількість контейнерів",
                field: "container_count",
                elementType: "input",
                type: "number",
                placeholder: "0",
            },
            {
                label: "Опис",
                field: "description",
                elementType: "textarea",
                maxLength: 500
            },
        ]
        const formWrapper = document.querySelector("#caseDirection .directionFormContainer")
        formWrapper.innerHTML = ""

        const formNODE = document.createElement('form')
        formNODE.setAttribute("id", "directionForm")

        formDrawData.forEach( data => {
            const formDataField = formData[data.field]

            if(data.elementType === "select"){
                const selectData = data.selectData.reduce((selectDataString, data) => {
                    return selectDataString + (
                        `<li data-v="${data.id}" class="${data.id === formDataField ? "selected" : ""}">
                            ${data.label}
                        </li>`
                    )
                }, '');
                const defaultDataLabel = !formDataField ? "" : data.selectData.find(data => data.id === formDataField)?.label

                formNODE.innerHTML += `
                <div class="directorModalFormGroup ${data.required ? "required" : ""} ${data.half ? "half" : ""} ">
                    <label htmlFor="${data.field}">${data.label} ${data.required ? '<span class="req">*</span>' : ''}</label>
                    <div class="directorModalFormGroup-select">
                        <div class="directorModalFormGroup-input input-box">
                            <span class="label" style="color: ${ formDataField ? "#23155b" : "#a9a4c6"}">${defaultDataLabel || data.placeholder}</span>
                        </div>
                        <ul class="directorModalFormGroup-list">
                            <li class="disabled">${data.placeholder}</li>
                            ${selectData}
                        </ul>
                        <input type="hidden" id="${data.field}" value="${formDataField || ""}" name="${data.field}" ${data.required ? "required" : ""} ${data.half ? "half" : ""} >
                    </div>
                </div>
                `
                return;
            }
            if(data.elementType === "input"){
                if(data.type === "radio"){
                    const options = data.options.map((option) => {
                        return (
                            `
                            <label>
                                <input type="radio" name="${data.field}" value="${option.id}">
                                <span class="custom-radio"></span>
                                <span>${option.label}</span>
                            </label>
                            `
                        )
                    }).join('')

                    formNODE.innerHTML += `
                    <div class="directorModalFormGroup ${data.required ? "required" : ""} ${data.half ? "half" : ""} ">
                        <label>${data.label} ${data.required ? '<span class="req">*</span>' : ''}</label>
                        <div class="directorModalFormGroupRadio">
                         ${options}
                        </div>
                    </div>
                    `
                }else{
                    formNODE.innerHTML += `
                    <div class="directorModalFormGroup ${data.required ? "required" : ""} ${data.half ? "half" : ""} ">
                        <label htmlFor="container_count">${data.label} ${data.required ? '<span class="req">*</span>' : ''}</label>
                        <input id="${data.field}" value="${formDataField || data.defaultValue || ""}" type="${data.type}" name="${data.field}" class="input input-box ${data.required ? 'required' : ''}" placeholder="${data.placeholder || ""}"
                               min="1">
                    </div>
                    `
                }
            }
            if(data.elementType === "textarea"){
                formNODE.innerHTML += `
                <div class="directorModalFormGroup ${data.required ? "required" : ""} ${data.half ? "half" : ""} ">
                    <label htmlFor="clinical_data">${data.label}  ${data.required ? '<span class="req">*</span>' : ''}</label>
                    <textarea id="${data.field}" name="${data.field}" placeholder="${data.placeholder || ""}" class="input input-box">${(formDataField || data.defaultValue || "").trim()}</textarea>
                </div>
                `
            }
        })

        formWrapper.append(formNODE)
    }
    const selectPicker = () => {
        document.querySelectorAll('.directorModalFormGroup-select').forEach(select =>{
            const box = select.querySelector('.directorModalFormGroup-input');
            const label = select.querySelector('.label');
            const list = select.querySelector('.directorModalFormGroup-list');
            const input = select.querySelector('input');
            box.onclick=()=> select.classList.toggle('open');

            list.addEventListener('click', e=>{
                const li = e.target.closest('li');
                if(!li || li.classList.contains('disabled')){
                    return;
                }

                list.querySelectorAll('li').forEach( li => li.classList.remove('selected'));
                li.classList.add('selected');

                label.textContent= li.textContent;
                label.style.color='#23155b';

                input.value = li.dataset.v || '';
                select.classList.remove('open');
                box.classList.remove('error');
            });
        });
    }
    const closeSelectPickerByClickingOutside = () => {
        document.addEventListener('click',e=>{
            document.querySelectorAll('.directorModalFormGroup-select.open').forEach( select => {
                if(!select.contains(e.target)) {
                    select.classList.remove('open')
                }
            });
        });
    }
    const submitCaseDirection = (e) => {
        document.querySelector('#caseDirectionSubmit')?.addEventListener('click', (e) => {
            e.preventDefault(e);
            let ok= true;

            document.querySelectorAll('.directorModalFormGroup.required').forEach( box =>{
                if(!box.querySelector('input').value){
                    box.querySelector('.input-box').classList.add('error');
                    ok = false;
                }
            });

            if(ok) {
                const formNODE = document.querySelector('#directionForm');
                const formData = Object.fromEntries(new FormData(formNODE).entries());


                let formattedDate = ``;

                if(formData.date_of_birth){
                    const date = new Date(formData.date_of_birth);

                    const day = String(date.getDate()).padStart(2, "0");
                    const month = String(date.getMonth() + 1).padStart(2, "0");
                    const year = date.getFullYear();
                    formattedDate = `${day}${month}${year}`;
                }

                const QRData = [
                    formData.last_name,
                    formData.first_name,
                    formattedDate,
                    formData.sex,
                    formData.email,
                    formData.phone,
                    formData.research_type,
                    formData.material_type,
                    formData.container_count,
                    formData.description
                ].join('|')

                new QRCode(document.querySelector('#testQRdiv'), {
                    text: QRData,
                    width: 500,
                    height: 500,
                    colorDark: '#291161',   // QR modules (the “dark” squares)
                    colorLight: '#ffffff',  // background (use 'transparent' if supported)
                });
                console.log(QRData, "QRData")
                console.log(formData, "formData")
                alert('HERE NEED TO ADD SOME REQEUST TO DATA_BASE')
                // fetch(`${API_BASE_URL}/API_URL_HERE`, {
                //     method: "POST",
                //     headers: {
                //         'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                //         "Content-Type": "application/json"
                //     },
                //     body: JSON.stringify({
                //         ...formData,
                //     })
                // })
                //     .then(res => res.json())
                //     .then((response) => {
                //
                //         //DO SOMETHING WITH RESPONSE
                //
                //         showSuccessAlert('Форму збережено!')
                //     })
                //     .catch((e) => {
                //         showErrorAlert(e?.message || "Щось пішло не так")
                //     })
            }
            else {
                showErrorAlert('Заповніть обов"язкові поля!')
            }
        })
    }

    drawForm( {} )
    selectPicker();
    closeSelectPickerByClickingOutside();
    submitCaseDirection();
})

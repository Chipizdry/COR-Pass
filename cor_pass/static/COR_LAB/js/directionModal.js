document.addEventListener("DOMContentLoaded", (event) => {
    const pad=n=>n.toString().padStart(2,'0');

    if(document.getElementById('todayMeta')){
        document.getElementById('todayMeta').textContent=`${pad(new Date().getDate())}.${pad(new Date().getMonth()+1)}.${new Date().getFullYear()}`;
    }


    const uploadBox = document.getElementById('uploadBox');
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    let uploadedFiles = []
    let currentReferralId = null

    function getExtensionFromBlob(blob) {
        const mime = blob.type;

        // Simple mapping
        const mimeToExt = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "application/pdf": "pdf",
            "text/plain": "txt",
            "application/json": "json",
        };

        return mimeToExt[mime] || "";
    }

    const closeModal  = () => {
        uploadedFiles = []
        currentReferralId = null

        uploadArea.innerHTML = ""
        document.querySelector('#caseDirection').classList.remove('open')
    }
    const sendFileRequest = async (file) => {
        const formGroup = new FormData()
        formGroup.append('file', file)

        return fetch(`${API_BASE_URL}/api/cases/${currentReferralId}/attachments`, {
            method: "POST",
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            },
            body: formGroup
        })
            .then(res => res.json())
            .then(() => true)
            .catch(() => false)
    }
    const drawForm = ( formData ) => {
        const formDrawData = [
            {
                label: "Вид дослідження",
                field: "research_type",
                required: true,
                elementType: "select",
                placeholder: "Оберіть вид",
                defaultValue: "Патогістологія",
                selectData: [
                    {
                        id: "Патогістологія",
                        label: "Патгістологія"
                    },
                    {
                        id: "Імуногістохімія",
                        label: "Імуногістохімія"
                    },
                    {
                        id: "Цитологія",
                        label: "Цитологія"
                    },
                    {
                        id: "FISH/CISH",
                        label: "NGS"
                    },
                    {
                        id: "Інше",
                        label: "Інше"
                    },
                ]
            },
            {
                label: "Кількість контейнерів",
                field: "container_count",
                required: true,
                elementType: "input",
                type: "number",
                placeholder: "0",
            },
            {
                label: "Дата забору біоматеріалу",
                field: "biomaterial_date",
                elementType: "input",
                type: "date",
            },
            {
                label: "Медкарта №",
                field: "medical_card_number",
                elementType: "input",
                type: "text",
                placeholder: "",
            },
            {
                label: "Клінічні дані",
                field: "clinical_data",
                elementType: "textarea",
            },
            {
                label: "Клінічний діагноз",
                field: "clinical_diagnosis",
                elementType: "input",
                type: "text",
                placeholder: "",
            },
            {
                label: "Медичний заклад",
                field: "medical_institution",
                elementType: "select",
                placeholder: "Оберіть медичний заклад",
                selectData: [
                    {
                        id: "Феофанія",
                        label: "Феофанія"
                    },
                    {
                        id: "Інститут раку",
                        label: "Інститут раку"
                    },
                ]
            },
            {
                label: "Відділення",
                field: "department",
                elementType: "select",
                placeholder: "Оберіть відділення",
                selectData: [
                    {
                        id: "Хірургія",
                        label: "Хірургія"
                    },
                    {
                        id: "Терапія",
                        label: "Терапія"
                    },
                ]
            },
            {
                label: "Лікуючий лікар ПІБ",
                field: "attending_doctor",
                elementType: "input",
                type: "text",
                placeholder: "",
            },
            {
                label: "Контакти лікаря",
                field: "doctor_contacts",
                elementType: "input",
                type: "text",
                placeholder: "+380"
            },
            {
                label: "Медична процедура/операція",
                field: "medical_procedure",
                elementType: "input",
                type: "text",
                placeholder: ""
            },
        ]
        const formWrapper = document.querySelector("#caseDirection .directorModalLeft")
        formWrapper.innerHTML = ""

        const formNODE = document.createElement('form')
        formNODE.setAttribute("id", "directionForm")

        formDrawData.forEach( data => {
            const formDataField = formData[data.field]

            if(data.elementType === "select"){
                const selectData = data.selectData.reduce((selectDataString, selectData) => {
                    return selectDataString + (
                        `<li data-v="${selectData.id}" class="${[formDataField, data.defaultValue].includes(selectData.id) ? "selected" : ""}">
                            ${selectData.label}
                        </li>`
                    )
                }, '');
                const defaultDataLabel = !formDataField ? (data.defaultValue || "") : data.selectData.find(data => data.id === formDataField)?.label

                formNODE.innerHTML += `
                <div class="directorModalFormGroup ${data.required ? "required" : ""}">
                    <label htmlFor="${data.field}">${data.label} ${data.required ? '<span class="req">*</span>' : ''}</label>
                    <div class="directorModalFormGroup-select">
                        <div class="directorModalFormGroup-input input-box">
                            <span class="label" style="color: ${ (formDataField || data.defaultValue) ? "#23155b" : "#a9a4c6"}">${defaultDataLabel || data.placeholder}</span>
                            <svg class="selectArrow" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M12.7241 16.0865L12.7269 16.0834L18.7453 9.65889L18.7499 9.65396L18.7511 9.65252C19.1032 9.25733 19.0719 8.66929 18.7194 8.30513L18.7167 8.30066L18.7158 8.29968L18.7122 8.29599L18.7114 8.29678C18.3519 7.90305 17.7346 7.90088 17.3434 8.29665L17.3412 8.29895L17.3399 8.30027L17.3377 8.30263L12.0041 13.964L6.66231 8.29402L6.66086 8.2954C6.49594 8.09985 6.23847 8 5.97981 8C5.45224 8 5 8.43581 5 8.99434C5 9.25792 5.09722 9.48996 5.26063 9.65679L5.26438 9.66067L11.3137 16.0847L11.3169 16.0882L11.342 16.1139L11.3527 16.1241L11.3555 16.1268C11.7488 16.488 12.3668 16.4838 12.7241 16.0865Z" fill="#5B4296"/>
                            </svg>
                        </div>
                        <ul class="directorModalFormGroup-list">
                            <li class="disabled">${data.placeholder}</li>
                            ${selectData}
                        </ul>
                        <input type="hidden" id="${data.field}" value="${formDataField  || data.defaultValue || ""}" name="${data.field}" ${data.required ? "required" : ""}>
                    </div>
                </div>
                `
                return;
            }
            if(data.elementType === "input"){
                formNODE.innerHTML += `
                <div class="directorModalFormGroup ${data.required ? "required" : ""}">
                    <label htmlFor="container_count">${data.label} ${data.required ? '<span class="req">*</span>' : ''}</label>
                    <input id="${data.field}" value="${formDataField || data.defaultValue || ""}" type="${data.type}" name="${data.field}" class="input input-box ${data.required ? 'required' : ''}" placeholder="${data.placeholder || ""}"
                           min="1">
                </div>
                `
            }
            if(data.elementType === "textarea"){
                formNODE.innerHTML += `
                <div class="directorModalFormGroup ${data.required ? "required" : ""}">
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
    const showFiles = async files => {
        if(!files.length) {
            return;
        }

        const cutTo5Files = [...files].slice(0,5);

        for (let i = 0; i < cutTo5Files.length; i++){
            await new Promise((resolve) => {
                const file = cutTo5Files[i];
                const fileViewerWrapperNODE = document.createElement('div');
                fileViewerWrapperNODE.className='thumb';

                const isPDF = file?.content_type?.includes('pdf') || file?.type?.includes('pdf');
                const imgNODE = document.createElement('img');

                if(file.file_url){
                    fetch(`${API_BASE_URL}/api${file.file_url}`, {
                        method: "GET",
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        },
                    })
                        .then(response => response.blob())
                        .then(blob => {
                            if(isPDF){
                                fileViewerWrapperNODE.innerHTML += `
                            <div style="background: white; height: 100%; width: 100%">
                                <embed
                                    src="${URL.createObjectURL(blob)}#toolbar=0"
                                    type="application/pdf"
                                    style="border: none; background: white; margin: 0 auto; display: block; height: 100%; width: 100%;"
                                ></embed>
                            </div>
                            `
                                uploadArea.prepend(fileViewerWrapperNODE);
                                resolve(true)
                                return;
                            }

                            imgNODE.src = URL.createObjectURL(blob);
                            imgNODE.onload=()=> URL.revokeObjectURL(imgNODE.src);
                            fileViewerWrapperNODE.appendChild(imgNODE);
                            uploadArea.prepend(fileViewerWrapperNODE);

                            resolve(true)
                        })
                    return;
                }

                if(isPDF){
                    fileViewerWrapperNODE.innerHTML += `
                            <div style="background: white; height: 100%; width: 100%">
                                <embed
                                    src="${URL.createObjectURL(file)}#toolbar=0"
                                    type="application/pdf"
                                    style="border: none; background: white; margin: 0 auto; display: block; height: 100%; width: 100%;"
                                ></embed>
                            </div>
                            `
                    uploadArea.prepend(fileViewerWrapperNODE);
                    resolve(true)
                    return;
                }


                console.log('HERE')
                imgNODE.src=URL.createObjectURL(file);
                imgNODE.onload=()=> URL.revokeObjectURL(imgNODE.src);
                fileViewerWrapperNODE.appendChild(imgNODE);
                uploadArea.prepend(fileViewerWrapperNODE);
                resolve(true)
            })
        }
    }
    const submitCaseDirection = (e) => {
        document.querySelector('#caseDirectionSubmit')?.addEventListener('click', (e) => {
            e.preventDefault(e);
            let ok= true;

            document.querySelectorAll('.directorModalFormGroup.required').forEach( box =>{

                const formNODE = document.querySelector('#directionForm');
                const formData = Object.fromEntries(new FormData(formNODE).entries());

                console.log(formData, "formData")
                if(!box.querySelector('input').value){
                    box.querySelector('.input-box').classList.add('error');
                    ok = false;
                }
            });

            if(ok) {
                const formNODE = document.querySelector('#directionForm');
                const formData = Object.fromEntries(new FormData(formNODE).entries());

                fetch(`${API_BASE_URL}/api/cases/referrals/upsert`, {
                    method: "POST",
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        case_id: cases[lastActiveCaseIndex].id,
                        ...formData,
                        biomaterial_date: formData.biomaterial_date || null
                    })
                })
                    .then(res => res.json())
                    .then((referralData) => {
                        if(!referralData.id){
                            return showErrorAlert('Щось пішло не так');
                        }
                        currentReferralId = referralData.id;

                        if(uploadedFiles.length){
                            Promise.all([...uploadedFiles].map(sendFileRequest))
                                .then(res => {
                                    showSuccessAlert('Форму збережено!')


                                    closeModal()
                                })

                            return;
                        }

                        showSuccessAlert('Форму збережено!')
                        closeModal()
                    })
                    .catch((e) => {
                        showErrorAlert(e?.message || "Щось пішло не так")
                    })
            }
            else {
                showErrorAlert('Заповніть обов"язкові поля!')
            }
        })
    }
    const scanCaseDirection = (e) => {
        document.querySelector('#caseDirectionScan')?.addEventListener('click', (e) => {
            fetch(`${API_BASE_URL}/api/cases/scan-referral`, {
                method: "POST",
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                    "Content-Type": "application/json"
                },
            })
                .then(res => res.blob())
                .then((blob) => {
                    const imgNODE = document.createElement('img');

                    const fileViewerWrapperNODE = document.createElement('div');
                    fileViewerWrapperNODE.className ='thumb full';


                    imgNODE.src = URL.createObjectURL(blob);
                    imgNODE.onload=()=> URL.revokeObjectURL(imgNODE.src);
                    fileViewerWrapperNODE.appendChild(imgNODE);
                    uploadArea.prepend(fileViewerWrapperNODE);


                    const file = new File([blob], `scan-${new Date().getTime()}.${getExtensionFromBlob(blob)}`, {
                        type: blob.type || "application/octet-stream",
                        lastModified: Date.now(),
                    });

                    uploadedFiles = [file, ...uploadedFiles]
                })
        })
    }
    const dropBoxEventsHandler = () => {
        uploadBox?.addEventListener('click', () => {
            fileInput.click()
        });
        uploadBox?.addEventListener('dragover', e => {
            e.preventDefault();
            uploadBox.classList.add('hover');
        });
        uploadBox?.addEventListener('dragenter', e => {
            e.preventDefault();
            uploadBox.classList.add('hover');
        });
        uploadBox?.addEventListener('dragleave', e => {
            e.preventDefault();
            uploadBox.classList.remove('hover');
        });
        uploadBox?.addEventListener('drop', e => {
            e.preventDefault();
            uploadBox.classList.remove('hover');
            uploadedFiles = [...uploadedFiles, ...e.dataTransfer.files]
            showFiles(e.dataTransfer.files)
        });
        fileInput?.addEventListener('change',e => {
            uploadedFiles = [ ...uploadedFiles, ...e.target.files ]
            showFiles(e.target.files)
        });
    }
    const openDirectionModal = () => {
        document.querySelector('#directionModalBtn')?.addEventListener('click', e => {
            uploadedFiles = []
            currentReferralId = null
            document.querySelector('#caseDirection').classList.add('open')
            fetch(`${API_BASE_URL}/api/cases/referrals/${cases[lastActiveCaseIndex]?.id}`, {
                method: "GET",
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                    "Content-Type": "application/json"
                },
            })
                .then(res => {
                    if(res.status === 404){
                        return {}
                    }

                    return res.json()
                })
                .then(refferalData => {
                    uploadArea.innerHTML = ""

                    currentReferralId = refferalData.id
                    drawForm( refferalData )
                    selectPicker();
                    closeSelectPickerByClickingOutside();
                    showFiles(refferalData.attachments || [])
                })
        })
    }

    submitCaseDirection();
    scanCaseDirection();
    dropBoxEventsHandler();
    openDirectionModal();
})

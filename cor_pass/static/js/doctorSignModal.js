let activeSign = null;

const modalDoctorSignNODE = document.querySelector('#doctorSign');
const doctorSignImgListNODE = document.querySelector('.doctorSignImgList');
const doctorSignCreateNODE = document.querySelector('.doctorSignCreate');
const doctorSignButtonNODE = document.querySelector('.doctorSignButton');
const signsNODE = document.querySelector('.doctorSignImgWrapper')


const initModal = () => {
    drawDestroy();
    signsNODE.innerHTML = ""
    doctorSignCreateNODE.classList.remove('open')
    doctorSignImgListNODE.classList.add('open')

    getAllDoctorSign()
}
const checkIsActiveSignButton = () => {
    const method = activeSign ? "add" : "remove";
    doctorSignButtonNODE.classList[method]('active')
}

const sendUploadFile = async (file) => {
    const formData = new FormData()
    formData.append('signature_scan_file', file)
    formData.append('is_default', false);

    return fetch(`${API_BASE_URL}/api/doctor/signatures/create`, {
        method: "POST",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: formData
    })
        .then(res => res.json())
}
const signFileChange = () => {
    const signFileInputNODE = document.querySelector('#signFile');
    signFileInputNODE.addEventListener('change', (e) => {
        Promise.all([...e.target.files].map(sendUploadFile))
            .then(signs => {
                Promise.all(signs.reverse().map((sign) => getSignImages(sign.signature_scan_data)))
                    .then(filesBlob => {
                        filesBlob.forEach((blob, index) => {
                            signTemplate(signs[index], blob)
                        })

                        showSuccessAlert('Файли успішно завантажились!')
                    })
            })
    });
}

const sendSignFileDraw = () => {
    document.querySelector('#createDoctorSign').addEventListener('click', () => {
        document.getElementById('drawing-board').toBlob((blob) => {
            const formData = new FormData();
            formData.append('signature_scan_file', blob, 'signature.png');
            formData.append('is_default', false);

            fetch(`${API_BASE_URL}/api/doctor/signatures/create`, {
                method: "POST",
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                },
                body: formData
            })
                .then(res => res.json())
                .then((signFile) => {
                    getSignImages(signFile.signature_scan_data)
                        .then(fileBlob => {
                            signTemplate(signFile, fileBlob)
                        })


                    showSuccessAlert('Файли успішно завантажились!')



                    doctorSignCreateNODE.classList.remove('open')
                    doctorSignImgListNODE.classList.add('open')
                })
        });
    })
}
const getSignImages = async (fileUrl) => {
    return fetch(`${API_BASE_URL}/api${fileUrl}`, {
        method: "GET",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
    })
        .then(response => response.blob())
        .then(blob => {
            return blob
        })
}

const clearDoctorSignHandler = () => {
    document.querySelector('#clearDoctorSign').addEventListener('click', () => {
        drawClear()
    })
}
const closeDoctorSignHandler = () => {
    document.querySelector('#closeDoctorSignDraw').addEventListener('click', () => {
        doctorSignCreateNODE.classList.remove('open')
        doctorSignImgListNODE.classList.add('open')
    })
}

const openDirectionModal = () => {
    document.querySelector('#doctorSignModalBtn').addEventListener('click', e => {
        initModal()
        modalDoctorSignNODE.classList.add('open')
    })
}
const openCreateDoctorSignHandler = () => {
    document.querySelector('#openCreateDoctorSign').addEventListener('click', () => {
        doctorSignCreateNODE.classList.add('open')
        doctorSignImgListNODE.classList.remove('open')
        drawInit(document.getElementById('drawing-board'), {minHeight: 400});
    })
}

const signTemplate = (currentSign, currentSignBlob) => {
    const div = document.createElement('div');
    div.classList = `doctorSignImg ${currentSign.is_default ? "check" : ""}`;
    div.innerHTML = `
        <div class="doctorSignImgBtn delete">
            <svg xmlns="http://www.w3.org/2000/svg" width="800px" height="800px" viewBox="0 0 1024 1024">
                <path fill="red" d="M352 192V95.936a32 32 0 0 1 32-32h256a32 32 0 0 1 32 32V192h256a32 32 0 1 1 0 64H96a32 32 0 0 1 0-64h256zm64 0h192v-64H416v64zM192 960a32 32 0 0 1-32-32V256h704v672a32 32 0 0 1-32 32H192zm224-192a32 32 0 0 0 32-32V416a32 32 0 0 0-64 0v320a32 32 0 0 0 32 32zm192 0a32 32 0 0 0 32-32V416a32 32 0 0 0-64 0v320a32 32 0 0 0 32 32z" />
            </svg>
        </div>
        <div class="doctorSignImgBtn check">
            <svg xmlns="http://www.w3.org/2000/svg" width="800px" height="800px" viewBox="0 0 24 24" fill="none">
                <path d="M4 12.6111L8.92308 17.5L20 6.5" stroke="green" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div class="doctorSignImgBtn default" style="display: ${currentSign.is_default ? "flex" : "none"}">
           <svg xmlns="http://www.w3.org/2000/svg" width="800px" height="800px" viewBox="0 0 1024 1024" fill="#000000">
            <path d="M896 896c0-35.376-28.626-64-64-64V448c35.376 0 64-28.626 64-64h128L512 0 0 384h128c0 35.376 28.626 64 64 64v384c-35.376 0-64 28.626-64 64-70.688 0-128 57.312-128 128h1024c0-70.688-57.312-128-128-128zM512 128c53 0 96 43 96 96s-43 96-96 96-96-43-96-96 43-96 96-96z m-128 768c0-35.376-28.626-64-64-64V448c35.376 0 64-28.626 64-64h256c0 35.376 28.626 64 64 64v384c-35.376 0-64 28.626-64 64H384z"/>
           </svg>
        </div>
        <img src="${URL.createObjectURL(currentSignBlob)}">
        `
    signsNODE.prepend(div);

    if(currentSign.is_default){
        activeSign = currentSign;
    }

    checkIsActiveSignButton()

    const deleteBtnNODE = div.querySelector('.doctorSignImgBtn.delete');
    const defaultBtnNODE = div.querySelector('.doctorSignImgBtn.default');

    div.addEventListener('click', () => {
        document.querySelectorAll(".doctorSignImg").forEach(elem => elem.classList.remove('check'))
        div.classList.add('check')

        activeSign = currentSign;
        checkIsActiveSignButton()
    })
    deleteBtnNODE.addEventListener('click', (e) => {
        e.stopPropagation()
        fetch(`${API_BASE_URL}/api/doctor/signatures/${currentSign.id}/delete`, {
            method: "DELETE",
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            },
        })
            .then(res => res.json())
            .then(() => {
                const wrapperNODE = deleteBtnNODE.closest('.doctorSignImg');
                if(wrapperNODE.classList.contains('check')){
                    activeSign = null;
                }

                wrapperNODE.remove()
                checkIsActiveSignButton()
                showSuccessAlert('Підпіс успішно видаленна')
            })
    })

    defaultBtnNODE.addEventListener('click', (e) => {
        e.stopPropagation()
        fetch(`${API_BASE_URL}/api/doctor/signatures/${currentSign.id}/set-default`, {
            method: "PUT",
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'Content-Type': 'application/json',
            },
        })
            .then(res => res.json())
            .then(() => {
                document.querySelectorAll(".doctorSignImgBtn.default").forEach(elem => elem.style.display = "none")
                defaultBtnNODE.style.display = "flex"
                div.click()
                alert('Підпіс вибран по дефолту')
                checkIsActiveSignButton()
            })
            .catch(() => {
                // document.querySelectorAll(".doctorSignImgBtn.default").forEach(elem => elem.style.display = "none")
                // defaultBtnNODE.style.display = "flex"
                // div.click()
                // alert('Підпіс вибран по дефолту')
                // checkIsActiveSignButton()
            })
    })

}

const getAllDoctorSign = () => {
    fetch(`${API_BASE_URL}/api/doctor/signatures/all`, {
        method: "GET",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
    })
        .then(res => res.json())
        .then(signs => {
            Promise.all(signs.reverse().map((sign) => getSignImages(sign.signature_scan_data)))
                .then(filesBlob => {
                    filesBlob.forEach((blob, index) => {
                        signTemplate(signs[index], blob)
                    })
                })
        })
}
const signReport = async (currentDiagnosisId) => {
    if(!doctorSignButtonNODE.classList.contains('active') || !currentDiagnosisId){
        return;
    }

    return fetch(`${API_BASE_URL}/api/doctor/diagnosis/${currentDiagnosisId}/report/sign`, {
        method: "POST",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            doctor_signature_id: activeSign.id
        })
    })
        .then(res => res.json())
        .then((res) => {
            modalDoctorSignNODE.classList.remove('open')
            initModal()
            showSuccessAlert('Підписання пройшло успішно')
            return res
        })
}


document.addEventListener("DOMContentLoaded", (event) => {

    openCreateDoctorSignHandler();
    sendSignFileDraw();
    clearDoctorSignHandler();
    closeDoctorSignHandler();
    signFileChange();
    openDirectionModal();

})

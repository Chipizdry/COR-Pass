



async function saveDoctorData(corId) {
    try {
        console.log("📤 Сбор данных для создания врача...");

        const data = {
            first_name: document.getElementById("doctorFirstName").value.trim(),
            last_name: document.getElementById("doctorLastName").value.trim(),
            middle_name: document.getElementById("doctorMiddleName").value.trim(),
            work_email: document.getElementById("doctorWorkEmail").value.trim(),
            phone_number: document.getElementById("doctorPhone").value.trim(),
            scientific_degree: document.getElementById("doctorDegree").value.trim(),
            passport_code: document.getElementById("doctorPassportCode").value.trim(),
            place_of_registration: document.getElementById("doctorRegistration").value.trim(),
            taxpayer_identification_number: document.getElementById("doctorInn").value.trim(),
            date_of_last_attestation: document.getElementById("doctorAttestationDate").value || new Date().toISOString().split('T')[0],
            diplomas: [],
            certificates: [],
            clinic_affiliations: []
        };

        console.log("✅ Персональные данные:", data);

        // Дипломы
        document.querySelectorAll('#diplomas-tab div[data-id]').forEach((d, idx) => {
            const inputs = d.querySelectorAll('input');
            const diploma = {
                university: inputs[0]?.value.trim() || "",
                series: inputs[1]?.value.trim() || "",
                number: inputs[2]?.value.trim() || "",
                date: "2023-01-01"
            };
            console.log(`📘 Диплом #${idx + 1}:`, diploma);
            data.diplomas.push(diploma);
        });

        // Сертификаты
        document.querySelectorAll('#certificates-tab div[data-id]').forEach((c, idx) => {
            const inputs = c.querySelectorAll('input');
            const cert = {
                university: inputs[0]?.value.trim() || "",
                series: inputs[1]?.value.trim() || "",
                number: inputs[2]?.value.trim() || "",
                date: "2023-01-01"
            };
            console.log(`📄 Сертификат #${idx + 1}:`, cert);
            data.certificates.push(cert);
        });

        // Клиники
        document.querySelectorAll('#clinics-tab div[data-id]').forEach((cl, idx) => {
            const inputs = cl.querySelectorAll('input');
            const clinic = {
                clinic_name: inputs[0]?.value.trim() || "",
                department: inputs[1]?.value.trim() || "",
                position: inputs[2]?.value.trim() || "",
                specialty: "Терапевт"
            };
            console.log(`🏥 Клиника #${idx + 1}:`, clinic);
            data.clinic_affiliations.push(clinic);
        });

        console.log("📦 Полный payload для отправки:", data);

        const response = await fetch(`/api/admin/signup_as_doctor?user_cor_id=${encodeURIComponent(corId)}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${getToken()}`
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ Ошибка от сервера (${response.status}):`, errorText);
            throw new Error(`Ошибка: ${response.status} ${response.statusText}\n${errorText}`);
        }

        const result = await response.json();
        console.log("✅ Врач успешно создан:", result);
        alert("✅ Пользователь успешно наделён правами врача!");

    } catch (error) {
        console.error("❌ Ошибка при сохранении врача:", error);
        alert("Ошибка при сохранении данных: " + error.message);
    }
}



async function showDoctorInfo(corId) {
    const roleInfoContent = document.getElementById("roleInfoContent");
    
    try {
        console.log('[DoctorInfo] Начало загрузки данных врача для corId:', corId);
        
        if (typeof corId !== 'string') {
            const errorMsg = `Ожидался string corId, получено: ${typeof corId}`;
            console.error('[DoctorInfo] Ошибка:', errorMsg, corId);
            throw new Error(errorMsg);
        }

        roleInfoContent.innerHTML = '<p>Загрузка данных врача...</p>';
        
        const response = await fetch(`/api/admin/get_user_info/${corId}/doctors-data`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Authorization': 'Bearer ' + getToken()
            }
        });

        if (!response.ok) {
            throw new Error(`Ошибка HTTP: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        const doctorInfo = data.doctor_info || {};
        
        // Формируем HTML для отображения в roleInfoModal
        roleInfoContent.innerHTML = `
    <h3>Информация о враче</h3>
    <div class="doctor-tabs">
        <div class="tabs-header">
            <button class="tab-btn active" data-tab="personal">Личные данные</button>
            <button class="tab-btn" data-tab="documents">Документы</button>
            <button class="tab-btn" data-tab="diplomas">Дипломы</button>
            <button class="tab-btn" data-tab="certificates">Сертификаты</button>
            <button class="tab-btn" data-tab="clinics">Клиники</button>
        </div>     
            <div id="personal-tab" class="tab-pane">
                ${renderPersonalInfo(doctorInfo)}
            </div>
            <div id="documents-tab" class="tab-pane">
                ${renderDocuments(doctorInfo)}
            </div>
            <div id="diplomas-tab" class="tab-pane">
                ${renderDiplomas(doctorInfo.diplomas || [])}
            </div>
            <div id="certificates-tab" class="tab-pane">
                ${renderCertificates(doctorInfo.certificates || [])}
            </div>
            <div id="clinics-tab" class="tab-pane">
                ${renderClinics(doctorInfo.clinic_affiliations || [])}
            </div>       
    </div>
    <button id="saveDoctorButton" class="button" style=" bottom:10px; margin:-10px 120px; margin-top:20px;">Сохранить врача</button>
`;


initTabs();
 document.getElementById("saveDoctorButton")?.addEventListener("click", () => {saveDoctorData(corId); });

    } catch (error) {
        console.error('[DoctorInfo] Ошибка:', error);
        roleInfoContent.innerHTML = `<p class="error">Не удалось загрузить информацию о враче: ${error.message}</p>`;
    }
    
}
// Функции для рендеринга разных разделов
function renderPersonalInfo(doctor) {
    return `
        <h4>Личные данные</h4>
        <div class="form-group-width">
            <label>Имя:</label>
            <input type="text" id="doctorFirstName" value="${doctor.first_name || ''}">
        </div>
        <div class="form-group-width">
            <label>Фамилия:</label>
            <input type="text" id="doctorLastName" value="${doctor.last_name || ''}">
        </div>
        <div class="form-group-width">
            <label>Отчество:</label>
            <input type="text" id="doctorMiddleName" value="${doctor.middle_name || ''}">
        </div>
        <div class="form-group-width">
            <label>Рабочий email:</label>
            <input type="email" id="doctorWorkEmail" value="${doctor.work_email || ''}">
        </div>
        <div class="form-group-width">
            <label>Телефон:</label>
            <input type="tel" id="doctorPhone" value="${doctor.phone_number || ''}">
        </div>
      
    `;
}

function renderDocuments(doctor) {
    return `
        <h4>Документы</h4>
        <div class="form-group-width">
            <label>Паспорт:</label>
            <input type="text" id="doctorPassportCode" value="${doctor.passport_code || ''}">
        </div>
        <div class="form-group-width">
            <label>Место регистрации:</label>
            <input type="text" id="doctorRegistration" value="${doctor.place_of_registration || ''}">
        </div>
        <div class="form-group-width">
            <label>ИНН:</label>
            <input type="text" id="doctorInn" value="${doctor.taxpayer_identification_number || ''}">
        </div>
        <div class="form-group-width">
            <label>Дата последней аттестации:</label>
            <input type="date" id="doctorAttestationDate" value="${doctor.date_of_last_attestation || ''}">
        </div>
        <div class="form-group-width">
            <label>Научная степень:</label>
            <input type="text" id="doctorDegree" value="${doctor.scientific_degree || ''}">
        </div>
    `;
}

function renderDiplomas(diplomas) {
    const list = diplomas.length > 0 ? diplomas : [{}];  // хотя бы один пустой

    return `
        <div class="documents-list">
            ${list.map((diploma, index) => `
                <div data-id="${diploma.id || ''}">
                    <h4>Диплом</h4>
                    <div class="form-group-width">
                        <label>Университет:</label>
                        <input type="text" value="${diploma.university || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Серия:</label>
                        <input type="text" value="${diploma.series || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Номер:</label>
                        <input type="text" value="${diploma.number || ''}">
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}


function renderCertificates(certificates) {
    const list = certificates.length > 0 ? certificates : [{}];

    return `
        <div class="documents-list">
            ${list.map((cert, index) => `
                <div data-id="${cert.id || ''}">
                    <h4>Сертификат</h4>
                    <div class="form-group-width">
                        <label>Университет:</label>
                        <input type="text" value="${cert.university || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Серия:</label>
                        <input type="text" value="${cert.series || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Номер:</label>
                        <input type="text" value="${cert.number || ''}">
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderClinics(clinics) {
    const list = clinics.length > 0 ? clinics : [{}];

    return `
        <div class="clinics-list">
            ${list.map((clinic, index) => `
                <div data-id="${clinic.id || ''}">
                    <h4>Клиника</h4>
                    <div class="form-group-width">
                        <label>Название:</label>
                        <input type="text" value="${clinic.clinic_name || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Отделение:</label>
                        <input type="text" value="${clinic.department || ''}">
                    </div>
                    <div class="form-group-width">
                        <label>Должность:</label>
                        <input type="text" value="${clinic.position || ''}">
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}
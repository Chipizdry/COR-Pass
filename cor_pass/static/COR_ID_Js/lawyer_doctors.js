// Скрипт для страницы списка врачей юриста

let doctorList = [];
let filteredDoctorList = [];
let currentSort = { field: "name", dir: "asc" };

const STATUS_COLORS = {
    pending: "#0B90C9",
    approved: "#49AC26",
    agreed: "#30D5C8",
    rejected: "#DF1125",
    need_revision: "#F8A441"
};

const STATUS_TRANSLATIONS = {
    pending: { uk: "На розгляді", en: "Pending", ru: "На рассмотрении" },
    approved: { uk: "Підтверджено", en: "Approved", ru: "Подтверждён" },
    agreed: { uk: "Узгоджено", en: "Agreed", ru: "Согласовано" },
    rejected: { uk: "Відхилено", en: "Rejected", ru: "Отклонён" },
    need_revision: { uk: "Потребує доопрацювання", en: "Needs Revision", ru: "Требует доработки" }
};

const tbody = document.getElementById("tableBody");
const footerInfo = document.getElementById("footerInfo");
const searchInput = document.getElementById("searchInput");
const sortBtn = document.getElementById("sortBtn");
const sortDropdown = document.getElementById("sortDropdown");
const sortLabel = document.getElementById("sortLabel");

// Получение всех врачей
const fetchAllDoctors = async () => {
    if (!await checkToken()) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/lawyer/get_all_doctors?skip=0&limit=1000`, {
            method: "GET",
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                "Content-Type": "application/json"
            },
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Error fetching doctors:", error);
        return [];
    }
};

// Обновление статуса врача
const updateDoctorStatus = async (doctorId, newStatus) => {
    if (!await checkToken()) return null;
    try {
        const response = await fetch(`${API_BASE_URL}/api/lawyer/asign_status/${doctorId}?doctor_status=${newStatus}`, {
            method: "PATCH",
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                "Content-Type": "application/json"
            },
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error("Error updating doctor status:", error);
        return null;
    }
};

const getFullName = (lastName, firstName, middleName) => [lastName, firstName, middleName].filter(Boolean).join(' ');

const getStatusLabel = (statusKey) => {
    const lang = getSavedLang() || 'uk';
    const statusTranslation = STATUS_TRANSLATIONS[statusKey];
    return statusTranslation ? (statusTranslation[lang] || statusTranslation['uk']) : statusKey;
};

const getStatusColor = (statusKey) => STATUS_COLORS[statusKey] || "#888888";

const formatDoctorData = (doctor) => ({
    ...doctor,
    name: getFullName(doctor.last_name, doctor.first_name, doctor.middle_name),
    sex: doctor.sex || null,
    specialization: doctor.specialization || '',
    clinic: doctor.clinic || '',
});

const compare = (a, b, field) => {
    if (field === "age") return (a.age ?? 0) - (b.age ?? 0);
    if (field === "id") return (a.doctor_id || '').localeCompare(b.doctor_id || '', "uk", { sensitivity: "base" });
    const av = a[field] != null ? a[field].toString() : '';
    const bv = b[field] != null ? b[field].toString() : '';
    return av.localeCompare(bv, "uk", { sensitivity: "base" });
};

const renderDoctorsTable = (doctorsData) => {
    const roles = decodeToken(getToken())?.roles || [];
    tbody.innerHTML = "";

    doctorsData.forEach(doctor => {
        const statusKey = doctor.status || 'pending';
        const color = getStatusColor(statusKey);
        const statusLabel = getStatusLabel(statusKey);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>
                ${doctor.doctors_photo 
                    ? `<img class="avatar" src="${API_BASE_URL}/api/lawyer/doctors/${doctor.doctor_id}/photo" alt="">` 
                    : ''}${doctor.name || ''}
            </td>
            <td>${doctor.doctor_id || ''}</td>
            <td>${doctor.age ? `${doctor.age}&nbsp;<span data-translate="yearsSuffix">р.</span>` : ''}</td>
            <td>${doctor.sex === "F" ? '<span data-translate="f">Жін</span>' : doctor.sex === "M" ? '<span data-translate="m">Чол</span>' : ''}</td>
            <td>${doctor.specialization || ''}</td>
            <td>${doctor.clinic || ''}</td>
            <td>
                <span class="status">
                    <span class="status-container">
                        <span class="status-dot" style="background:${color}"></span>
                        <span class="status-label" data-status="${statusKey}">${statusLabel}</span>
                    </span>
                    <svg class="status-menu-trigger" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M10 18.375C10 17.3395 10.8395 16.5 11.875 16.5C12.9105 16.5 13.75 17.3395 13.75 18.375C13.75 19.4105 12.9105 20.25 11.875 20.25C10.8395 20.25 10 19.4105 10 18.375Z" fill="#B1A1DA" />
                        <path d="M10 12.125C10 11.0895 10.8395 10.25 11.875 10.25C12.9105 10.25 13.75 11.0895 13.75 12.125C13.75 13.1605 12.9105 14 11.875 14C10.8395 14 10 13.1605 10 12.125Z" fill="#B1A1DA" />
                        <path d="M10 5.875C10 4.83947 10.8395 4 11.875 4C12.9105 4 13.75 4.83947 13.75 5.875C13.75 6.91053 12.9105 7.75 11.875 7.75C10.8395 7.75 10 6.91053 10 5.875Z" fill="#B1A1DA" />
                    </svg>
                </span>
            </td>`;

        // Переход на страницу врача при клике
        tr.addEventListener('click', (e) => {
            if (e.target.closest('.status-menu-trigger')) return;
            window.location.href = `/static/COR_ID/lawyers_cabinet/lawyer_specific-doctor.html?doctorId=${doctor.doctor_id}`;
        });

        const statusTrigger = tr.querySelector('.status-menu-trigger');
        if (statusTrigger) {
            statusTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                showStatusMenu(e, doctor.doctor_id, statusKey);
            });
        }

        tbody.appendChild(tr);
    });

    updateFooterInfo(doctorsData.length);
};

const updateFooterInfo = (count) => {
    const lang = getSavedLang() || 'uk';
    const dict = translations?.[lang] || {};
    footerInfo.textContent = `${dict.totalDoctors || 'Всього'}: ${count} ${dict.doctors || 'лікарів'}`;
};

const sortAndRenderTable = (field, dir) => {
    filteredDoctorList.sort((a, b) => dir === "asc" ? compare(a, b, field) : -compare(a, b, field));
    renderDoctorsTable(filteredDoctorList);
};

let activeStatusMenu = null;

const showStatusMenu = (event, doctorId, currentStatus) => {
    if (activeStatusMenu) activeStatusMenu.remove();

    const menu = document.createElement('div');
    menu.className = 'status-dropdown';
    menu.innerHTML = Object.keys(STATUS_COLORS).map(status => `
        <button class="status-option ${status === currentStatus ? 'active' : ''}" data-status="${status}">
            <span class="status-dot" style="background:${STATUS_COLORS[status]}"></span>
            ${getStatusLabel(status)}
        </button>
    `).join('');

    const rect = event.target.getBoundingClientRect();
    menu.style.cssText = `
        position: fixed;
        top: ${rect.bottom + 5}px;
        left: ${rect.left - 150}px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        z-index: 1000;
        min-width: 200px;
        padding: 8px 0;
    `;

    document.body.appendChild(menu);
    activeStatusMenu = menu;

    menu.querySelectorAll('.status-option').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const newStatus = btn.dataset.status;
            
            if (newStatus !== currentStatus) {
                const result = await updateDoctorStatus(doctorId, newStatus);
                if (result) {
                    const doctorIndex = doctorList.findIndex(d => d.doctor_id === doctorId);
                    if (doctorIndex !== -1) doctorList[doctorIndex].status = newStatus;
                    const filteredIndex = filteredDoctorList.findIndex(d => d.doctor_id === doctorId);
                    if (filteredIndex !== -1) filteredDoctorList[filteredIndex].status = newStatus;
                    renderDoctorsTable(filteredDoctorList);
                }
            }
            
            menu.remove();
            activeStatusMenu = null;
        });
    });

    const closeMenu = (e) => {
        if (!menu.contains(e.target)) {
            menu.remove();
            activeStatusMenu = null;
            document.removeEventListener('click', closeMenu);
        }
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
};

const initSearch = () => {
    if (!searchInput) return;
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase();
        filteredDoctorList = doctorList.filter(doctor =>
            Object.values(doctor).some(val => val != null && val.toString().toLowerCase().includes(query))
        );
        sortAndRenderTable(currentSort.field, currentSort.dir);
    });
};

const initSortDropdown = () => {
    if (!sortBtn || !sortDropdown) return;
    sortBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        sortDropdown.classList.toggle("visible");
    });
    window.addEventListener("click", () => sortDropdown.classList.remove("visible"));
    sortDropdown.addEventListener("click", (e) => {
        if (e.target.matches("button")) {
            const { field, dir } = e.target.dataset;
            currentSort = { field, dir };
            if (sortLabel) {
                const labelSpan = sortLabel.querySelector('span');
                if (labelSpan) labelSpan.textContent = e.target.textContent;
            }
            sortDropdown.classList.remove("visible");
            sortAndRenderTable(field, dir);
        }
    });
};

const initTableHeaderSort = () => {
    document.querySelectorAll("thead th[data-field]").forEach(th => {
        th.addEventListener("click", () => {
            const field = th.dataset.field;
            if (field === "select") return;
            const dir = currentSort.field === field && currentSort.dir === "asc" ? "desc" : "asc";
            currentSort = { field, dir };
            if (sortLabel) sortLabel.textContent = `Сортування: ${th.textContent.trim()} ${dir === "asc" ? "↑" : "↓"}`;
            sortAndRenderTable(field, dir);
        });
    });
};

const loadDoctors = async () => {
    const doctors = await fetchAllDoctors();
    if (doctors && doctors.length > 0) {
        doctorList = doctors.map(formatDoctorData);
        filteredDoctorList = [...doctorList];
        sortAndRenderTable(currentSort.field, currentSort.dir);
    } else {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Лікарів не знайдено</td></tr>';
        updateFooterInfo(0);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const searchParams = new URLSearchParams(document.location.search);
    const accessToken = searchParams.get("access_token");
    if (accessToken) localStorage.setItem('access_token', accessToken);

    initSearch();
    initSortDropdown();
    initTableHeaderSort();
    loadDoctors();
});

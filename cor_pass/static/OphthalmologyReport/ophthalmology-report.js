const REPORT_DATA = {
    corId: "159RLHD9P-1978M",
    patientName: "Іванова Катерина Віталіївна",
    birthDate: "15.01.1990",
    gender: "Жіноча",
    od: {
        sph: -20,
        cyl: -6,
        ax: 0,
        prism: 0,
        base: "Up",
        add: 0.75,
    },
    os: {
        sph: -20,
        cyl: -6,
        ax: 0,
        prism: 0,
        base: "Up",
        add: 0.75,
    },
    purpose: "Для постійного носіння",
    glassesType: "Мультифокальні",
    issueDate: "21.07.2025",
    validity: "3 місяців",
    noteText: "This placeholder text is used for design purposes in interface layouts. It does not carry actual meaning but helps to test how fonts, spacing, and structure will look once real content is added. Later, the doctor or system user can replace this text with real prescription data and patient-specific notes as required.",
    doctorName: "Іванов Іван Іванович",
};

document.addEventListener("DOMContentLoaded", () => {
    renderReport(REPORT_DATA);
});

function renderReport(reportData) {
    fillBasicInfo(reportData);
    renderEyeValues("od", reportData.od);
    renderEyeValues("os", reportData.os);
    renderSummary(reportData);
}

function fillBasicInfo({ corId, patientName, birthDate, gender }) {
    setFieldValue("corId", corId);
    setFieldValue("patientName", patientName);
    setFieldValue("birthDate", birthDate);
    setFieldValue("gender", gender);
}

function renderEyeValues(side, eyeData = {}) {
    const eyeFields = [
        { key: "sph", formatter: (value) => formatSignedNumber(value, 2) },
        { key: "cyl", formatter: (value) => formatSignedNumber(value, 2) },
        { key: "ax", formatter: formatAxis },
        { key: "prism", formatter: (value) => formatNumber(value, 2) },
        { key: "base", formatter: formatTextValue },
        { key: "add", formatter: (value) => formatSignedNumber(value, 2) },
    ];

    eyeFields.forEach(({ key, formatter }) => {
        const target = document.querySelector(`.eye-value[data-eye="${side}"][data-eye-value="${key}"]`);
        if (!target) {
            return;
        }
        target.textContent = formatter(eyeData[key]);
    });
}

function renderSummary({ purpose, glassesType, issueDate, validity, noteText, doctorName }) {
    setFieldValue("purpose", purpose);
    setFieldValue("glassesType", glassesType);
    setFieldValue("issueDate", issueDate);
    setFieldValue("validity", validity);
    setFieldValue("noteText", noteText);
    setFieldValue("doctorName", doctorName);
}

function setFieldValue(fieldName, value) {
    const target = document.querySelector(`[data-field="${fieldName}"]`);
    if (!target) {
        return;
    }
    target.textContent = formatTextValue(value);
}

function formatSignedNumber(value, digits = 2) {
    const formatted = formatNumber(value, digits);
    if (formatted === "-") {
        return formatted;
    }
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return formatted;
    }
    if (numericValue > 0) {
        return `+${formatted}`;
    }
    return formatted;
}

function formatAxis(value) {
    const formatted = formatNumber(value, 0);
    return formatted === "-" ? formatted : `${formatted}\u00b0`;
}

function formatNumber(value, digits = 2) {
    if (value === undefined || value === null || value === "") {
        return "-";
    }
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return value;
    }
    return numericValue.toFixed(digits);
}

function formatTextValue(value) {
    if (value === undefined || value === null || value === "") {
        return "-";
    }
    return value;
}

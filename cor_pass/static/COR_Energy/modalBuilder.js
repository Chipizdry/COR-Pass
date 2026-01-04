

// ===============================
// Конструктор модалок по schema
// ===============================

export function buildModals(schema) {
    if (!schema) return;

    Object.values(schema).forEach(section => {
        if (!section?.enabled || !section.modalId) return;

        const modal = document.getElementById(section.modalId);
        if (!modal) return;

        // Заголовок
        const title = modal.querySelector("h3");
        if (title && section.title) {
            title.textContent = section.title;
        }

        // Тело модалки
        let body = modal.querySelector(".modal-body");

        // если старые модалки — создаём body автоматически
        if (!body) {
            body = document.createElement("div");
            body.className = "modal-body";
            modal.appendChild(body);
        }

        body.innerHTML = "";

        section.blocks?.forEach(block => {
            body.appendChild(renderBlock(block));
        });
    });
}

// ===============================
// Фабрика блоков
// ===============================
function renderBlock(block) {
    switch (block.type) {

        case "fieldList":
            return renderFieldList(block.fields);

        case "phaseTable":
            return renderPhaseTable(block.phases);

        case "singlePhase":
            return renderSinglePhase(block.fields);


        case "slider":
            return renderSlider(block);

        case "text":
            return renderText(block.text);

        default:
            console.warn("❓ Unknown block type:", block.type);
            return document.createElement("div");
    }
}

// ===============================
// Блок: список параметров
// ===============================
function renderFieldList(fields = []) {
    const wrap = document.createElement("div");
    wrap.className = "modal-section";

    fields.forEach(f => {
        const row = document.createElement("div");
        row.className = "modal-row";
        row.dataset.source = f.source;

        row.innerHTML = `
            <span class="data-label">${f.label}</span>
            <span class="data-value">—</span>
            <span class="data-value">${f.unit || ""}</span>
        `;
        wrap.appendChild(row);
    });

    return wrap;
}

// ===============================
// Блок: фазовая таблица (1 / 3)
// ===============================


function renderPhaseTable(phases = 3) {
    const table = document.createElement("table");
    table.className = "phase-table";

    table.innerHTML = `
        <thead>
            <tr>
                <th>Параметр</th>
                ${Array.from({ length: phases }, (_, i) => `<th>L${i + 1}</th>`).join("")}
            </tr>
        </thead>
        <tbody>
            ${renderPhaseRow("Напряжение", "V", "inputVoltage", phases)}
            ${renderPhaseRow("Ток", "A", "inputCurrent", phases)}
            ${renderPhaseRow("Мощность", "kW", "inputPower", phases)}
        </tbody>
    `;
    return table;
}






function renderPhaseRow(label, unit, base, phases) {
    return `
        <tr>
            <td>${label} (${unit})</td>
            ${Array.from({ length: phases }, (_, i) =>
                `<td data-source="${base}L${i + 1}">—</td>`
            ).join("")}
        </tr>
    `;
}

// ===============================
// Блок: слайдер
// ===============================
function renderSlider(cfg) {
    const wrap = document.createElement("div");
    wrap.className = "modal-control";

    wrap.innerHTML = `
        <label>${cfg.label}</label>
        <div style="display:flex; gap:10px; align-items:center;">
            <input type="range"
                min="${cfg.min}"
                max="${cfg.max}"
                step="${cfg.step || 1}"
                data-source="${cfg.source}">
            <span class="slider-value">—</span>
        </div>
        ${cfg.saveAction ? `<button onclick="${cfg.saveAction}()">Сохранить</button>` : ""}
    `;
    return wrap;
}

// ===============================
// Блок: текст
// ===============================
function renderText(text) {
    const p = document.createElement("p");
    p.textContent = text;
    return p;
}


function renderSinglePhase(fields = []) {
    const wrap = document.createElement("div");
    wrap.className = "single-phase-grid";

    fields.forEach(f => {
        const card = document.createElement("div");
        card.className = "info-card";
        card.dataset.source = f.source;

        card.innerHTML = `
            <div class="data-label">${f.label}</div>
            <div class="data-value">— <span>${f.unit}</span></div>
        `;
        wrap.appendChild(card);
    });

    return wrap;
}
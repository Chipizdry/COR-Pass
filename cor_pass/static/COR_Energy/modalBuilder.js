
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
        if (title && section.title) title.textContent = section.title;

        // Тело модалки
        let body = modal.querySelector(".modal-body");
        if (!body) {
            body = document.createElement("div");
            body.className = "modal-body";
            modal.appendChild(body);
        }
        body.innerHTML = "";

        // Рендерим blocks
        section.blocks?.forEach(block => body.appendChild(renderBlock(block)));

        // Рендерим fields (для Axioma и Victrone)
        if (section.fields) {
            body.appendChild(renderBlock({ type: "fieldList", fields: section.fields }));
        }

        // Рендерим controls (слайдеры и кнопки)
        section.controls?.forEach(ctrl => body.appendChild(renderBlock(ctrl)));
    });
}

// ===============================
// Фабрика блоков
// ===============================
function renderBlock(block) {
    const container = document.createElement("div");
    container.className = "modal-block";

    let content;

    switch (block.type) {
        case "fieldList":
            content = renderFieldList(block.fields, block.title);
            break;

        case "phaseTable":
            content = renderPhaseTable(block.phases);
            break;

        case "singlePhase":
            content = renderSinglePhase(block.fields);
            break;

        case "slider":
            content = renderSlider(block);
            break;

        case "text":
            content = renderText(block.text);
            break;
    }

    container.appendChild(content);
    return container;
}

// ===============================
// Блок: список параметров
// ===============================


function renderFieldList(fields = [], title = null) {
    const wrap = document.createElement("div");
    wrap.className = "single-phase-grid";

    if (title) {
        const t = document.createElement("div");
        t.className = "single-block-title";
        t.textContent = title;
        wrap.appendChild(t);
    }

    fields.forEach(f => {
        const row = document.createElement("div");
        row.className = "modal-row";

        row.innerHTML = `
            <span class="data-label">${f.label}</span>
            <span class="data-value" data-source="${f.source}">—</span>
            <span class="unit">${f.unit || ""}</span>
        `;

        console.log("🟢 Создано поле:", f.label, "data-source:", f.source, "unit:", f.unit);

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

        card.innerHTML = `
            <div class="data-label">${f.label}</div>
            <div class="data-value" data-source="${f.source}">
                — <span>${f.unit}</span>
            </div>
        `;

        wrap.appendChild(card);
    });

    return wrap;
}
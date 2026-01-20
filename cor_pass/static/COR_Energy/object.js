
import { MODAL_SCHEMAS } from "./modalSchemas.js";
import { buildModals } from "./modalBuilder.js";

export function resolveModalSchema(vendor, model) {
    const vendorSchemas = MODAL_SCHEMAS[vendor];
    if (!vendorSchemas) return null;
    return vendorSchemas[model] || vendorSchemas.default || null;
}

// ============================
// Закрытие модалки
// ============================

document.addEventListener("click", (e) => {
    const btn = e.target.closest('[data-action="close"]');
    if (!btn) return;

    const modal = btn.closest(".modal");
    if (!modal) return;
 window.activeModals[entity] = false;
onModalClosed(entity);
});

function onModalClosed(entity) {
    const hooks = window.currentModalSchema?.hooks;
    if (!hooks?.onClose) return;

    hooks.onClose(entity);
}



async function loadObjectSettings(objectId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/modbus/${objectId}`, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error("Ошибка загрузки объекта");
        }

        const data = await response.json();

        console.log("Объект:", data);
        // Установка заголовка
        document.getElementById("objectTitle").textContent = data.name || "    ";


           // 🔽 ВАЖНО: получаем схему
        const modalSchema = resolveModalSchema(data.vendor, data.model);
        console.log("Schema:", modalSchema);

        // 🔥 СТРОИМ МОДАЛКИ ПО СХЕМЕ
        buildModals(modalSchema);
        updateUIByData(window.lastData);
        initIconModalHandlers(modalSchema);
        // Запускаем обработчик в зависимости от протокола
        handleObjectByProtocol(data);
        window.currentModalSchema = modalSchema;
        window.currentObject = data;

    } catch (err) {
        console.error("Ошибка:", err);
    }
}

function handleObjectByProtocol(objectData) {

    switch (objectData.vendor) {

        case "Deye":
            startMonitoringDeye(objectData);
            break;

        case "Victron":
            startMonitoringVictron(objectData);
            break;

        case "Axioma":
            startMonitoringAxioma(objectData);
            break;

        case "Pow Mr":
            startMonitoringPowMr(objectData);
            break;

        case "Pylontech":
            startMonitoringPylontech(objectData);
            break;

        case "COR-ID":
            startMonitoringCorID(objectData);
            break;

        default:
            console.warn("Неизвестный производитель:", objectData.vendor);
            break;
    }
}

async function resolveCORBridgeDeviceId(corBridgeId) {

      const token = getToken();
    checkToken();
    if (!corBridgeId) return null;

    try {

          const response = await fetch(
            `${API_BASE_URL}/api/energetic_device_proxy/devices`,
            {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Authorization': `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            throw new Error("Не удалось загрузить COR-Bridge список");
        }

        const devices = await response.json();

        const bridge = devices.find(d => d.id === corBridgeId);

        if (!bridge) {
            console.warn("❌ COR-Bridge не найден:", corBridgeId);
            return null;
        }

        return bridge.device_id; // 🔥 COR-XXXX
    } catch (err) {
        console.error("❌ Ошибка resolveCORBridgeDeviceId:", err);
        return null;
    }
}


// ============================
// Открытие модалки
// ============================
function openEntityModal(entity, modalSchema) {
    console.group(`🪟 openEntityModal: ${entity}`);

    if (!modalSchema) {
        console.warn("❌ Нет схемы модалок");
        console.groupEnd();
        return;
    }

    const entitySchema = modalSchema[entity];
    if (!entitySchema || !entitySchema.modalId) {
        console.warn(`❌ Сущность '${entity}' отсутствует или modalId не задан`);
        console.groupEnd();
        return;
    }

    const modal = document.getElementById(entitySchema.modalId);
    if (!modal) {
        console.error(`❌ Модалка '${entitySchema.modalId}' не найдена`);
        console.groupEnd();
        return;
    }

    modal.style.display = "block";

      // 🔥 АКТИВИРУЕМ ФЛАГ
   window.activeModals[entity] = true;
   onModalOpened(entity);

    // 🔄 обновляем модалку сразу актуальными данными
    updateUIByData(window.lastData);

    console.groupEnd();
}



function onModalOpened(entity) {
    const hooks = window.currentModalSchema?.hooks;
    if (!hooks?.onOpen) return;

    hooks.onOpen(entity, {
        object: window.currentObject,
        lastData: window.lastData
    });
}



function initIconModalHandlers(modalSchema) {
    console.group("🧷 initIconModalHandlers");

    if (!modalSchema) {
        console.error("❌ modalSchema отсутствует");
        console.groupEnd();
        return;
    }

    const icons = document.querySelectorAll(".icon[data-entity]");
    console.log("Найдено иконок:", icons.length);

    icons.forEach(icon => {
        const entity = icon.dataset.entity;
        console.log("→ иконка entity:", entity);

        icon.addEventListener("click", () => {
            console.log(`🖱️ click по entity: ${entity}`);
            openEntityModal(entity, modalSchema);
        });
    });

    console.groupEnd();
}


function getGradientColor(value) {
const x = Math.max(0, Math.min(100, value));
let r, g;
if (x <= 50) {
const k = x / 50;
r = Math.round(255 * k);
g = 255;
} else {
const k = (x - 50) / 50;
r = 255;
g = Math.round(255 * (1 - k));
}
return `rgb(${r}, ${g}, 0)`;
}
function updatePowerElement(id, value) {
const el = document.getElementById(id);
if (!el) return;

const v = Math.max(0, Math.min(100, Math.abs(value))); // используем модуль для цвета

if (el.tagName.toLowerCase() === "path") {
    const animate = el.querySelector("animate");
    if (v === 0) {
        el.style.stroke = "rgba(120,120,120,0.3)";
        el.style.opacity = "0.3";
        if (animate) animate.setAttribute("from", "0"), animate.setAttribute("to", "0");
        return;
    }
    el.style.stroke = getGradientColor(v);
    el.style.opacity = "1";
    if (animate) animate.setAttribute("from", "0"), animate.setAttribute("to", value > 0 ? "-50" : "50");
} else if (el.tagName.toLowerCase() === "rect") {
    const svg = el.ownerSVGElement;
    if (!svg) return;
    const vb = svg.viewBox.baseVal;
    const fullWidth = vb.width || svg.getBoundingClientRect().width;

    const centerBars = ["BatteryBar", "gridBar"];
    const isCenter = centerBars.includes(id);
    el.setAttribute("fill", v === 0 ? "rgba(120,120,120,0.4)" : getGradientColor(v));

    if (isCenter) {
        const centerX = fullWidth / 2;
        const halfWidth = (fullWidth / 2) * (v / 100);
        if (value >= 0) {
            // вправо от центра
            el.setAttribute("x", centerX);
            el.setAttribute("width", halfWidth);
        } else {
            // влево от центра
            el.setAttribute("x", centerX - halfWidth);
            el.setAttribute("width", halfWidth);
        }
    } else {
        const padding = 2;
        const width = Math.round((fullWidth - padding * 2) * (v / 100));
        el.setAttribute("x", padding);
        el.setAttribute("width", width);
    }
}

}

// --- Обновление по логическому имени ---
function updatePowerByName(name, value) {
    const map = {
        Battery: { line: "batteryLine", bar: "BatteryBar" },
        Generator: { line: "generatorLine", bar: "GeneratorBar" },
        Load: { line: "loadLine", bar: "PowerBar" },
        Grid: { line: "gridLine", bar: "gridBar" },
        Solar: { line: "solarLine", bar: "SunPanelBar" }
    };
    const ids = map[name];
    if (!ids) return;
    updatePowerElement(ids.line, value);
    updatePowerElement(ids.bar, value);
}

function updateBatteryFill(value) {
    const fill = document.getElementById("batteryFill");
    if (!fill) return;

    const v = Math.max(0, Math.min(100, value)); // SOC 0..100

    const x_left  = 14.7964;
    const x_right = 73.0562;
    const maxWidth = x_right - x_left;

    const newWidth = maxWidth * (v / 100);
    const newX = x_right - newWidth;

    fill.setAttribute("x", newX.toFixed(2));
    fill.setAttribute("width", newWidth.toFixed(2));

    // 🔴⬅️🟢 ИНВЕРСИЯ ЦВЕТА
    fill.setAttribute("fill", getGradientColor(100 - v));
}

function PowerToIndicator(powerW, maxPowerW) {
    if (typeof powerW !== "number" || !isFinite(powerW)) return 0;

    const percent = (powerW / maxPowerW) * 100;

    // ограничиваем, но сохраняем знак
    return Math.max(-100, Math.min(100, percent));
}


function formatPowerLabel(powerW, type) {
    if (typeof powerW !== "number" || !isFinite(powerW)) {
        return undefined; // ← textContent НЕ меняется
    }

    const absW = Math.abs(powerW);

    //НЕТ ПОТОКА
    if (absW === 0) {
        return "Нет потока";
    }

    const formatValue = (w) => {
        if (w < 10100) {
            return `${Math.round(w)} Вт`;
        }
        return `${(w / 1000).toFixed(1)} КВт`;
    };

    switch (type) {
        case "battery":
            return powerW >= 0
                ? `Разряд: ${formatValue(absW)}`
                : `Заряд: ${formatValue(absW)}`;

        case "grid":
            return powerW >= 0
                ? `Потребление: ${formatValue(absW)}`
                : `Отдача: ${formatValue(absW)}`;

        case "load":
            return `Нагрузка: ${formatValue(absW)}`;

        case "solar":
        case "generator":
            return `Генерация: ${formatValue(absW)}`;

        default:
            return formatValue(absW);
    }
}


/**
 * Показывает или скрывает элементы устройства по имени
 * @param {string} name - имя сущности: "Grid", "Battery", "Generator", "Load", "Sun"
 * @param {string} state - "visible" или "hidden"
 */
function setDeviceVisibility(name, state) {
    if (!name || !state) return;

    const show = state === "visible";

    // Привязываем к реальным ID элементов
    const idMap = {
        Battery: ["batteryIcon", "batteryLine", "batteryFill"],
        Generator: ["GeneratorIcon", "generatorLine"],
        Load: ["loadIcon", "loadLine"],
        Grid: ["power-grid-icon", "gridLine"],
        Sun: ["SolarBatteryIcon", "solarLine"]
        // при необходимости новые сущности сюда
    };

    const elements = idMap[name];
    if (!elements) return;

    elements.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = show ? "block" : "none";
    });
}



export function updateUIByData(data = {}) {
    if (!data || typeof data !== "object") {
        console.warn("updateUIByData: пустые или некорректные данные", data);
        return;
    }

    Object.assign(window.lastData, data);

    console.group("🔄 updateUIByData");
    Object.entries(data).forEach(([key, value]) => {
        const nodes = document.querySelectorAll(`[data-source="${key}"]`);

        if (!nodes.length) {
          //  console.warn(`❌ Поле с data-source="${key}" не найдено в DOM`, value);
            return;
        }

        nodes.forEach(node => {
            let oldText = node.textContent;

            if (node.classList.contains("data-value")) {
                // сохраняем unit
                const unit = node.querySelector("span")?.textContent || "";
                node.textContent = formatValue(value) + (unit ? ` ${unit}` : "");
            } else if (node.tagName === "TD") {
                node.textContent = formatValue(value);
            } else if (node.tagName === "INPUT" || node.tagName === "SELECT") {
                node.value = value;
            }

           // console.log(`✅ Обновлено: ${key}`, "DOM:", node, "старое:", oldText, "новое:", node.textContent || node.value);
        });
    });
    console.groupEnd();
}


function formatValue(val) {
    if (val == null || Number.isNaN(val)) return "—";
    if (typeof val === "number") return Math.abs(val) >= 1000 ? val.toFixed(0) : val.toFixed(1);
    return val;
}

window.resolveModalSchema = resolveModalSchema;
window.loadObjectSettings = loadObjectSettings;
window.updatePowerByName = updatePowerByName;
window.updateBatteryFill = updateBatteryFill;
window.PowerToIndicator = PowerToIndicator;
window.formatPowerLabel = formatPowerLabel;
window.setDeviceVisibility = setDeviceVisibility;
window.updateUIByData = updateUIByData;
window.resolveCORBridgeDeviceId = resolveCORBridgeDeviceId;

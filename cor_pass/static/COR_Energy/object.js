


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

    const v = Math.max(0, Math.min(100, value)); // clamp 0..100

    const x_left  = 14.7964;
    const x_right = 73.0562;
    const maxWidth = x_right - x_left; // 58.2598

    const newWidth = maxWidth * (v / 100);

    // смещаем x так, чтобы заполнялось справа → налево
    const newX = x_right - newWidth;

    fill.setAttribute("x", newX.toFixed(2));
    fill.setAttribute("width", newWidth.toFixed(2));
    fill.setAttribute("fill", getGradientColor(v));
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
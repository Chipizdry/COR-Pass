


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


const v = Math.max(0, Math.min(100, value));

if (el.tagName.toLowerCase() === "path") {
    // Линия
    const animate = el.querySelector("animate");
    if (v === 0) {
        el.style.stroke = "rgba(120,120,120,0.3)";
        el.style.opacity = "0.3";
        if (animate) {
            animate.setAttribute("from", "0");
            animate.setAttribute("to", "0");
        }
        return;
    }
    el.style.stroke = getGradientColor(v);
    el.style.opacity = "1";
    if (animate) {
        animate.setAttribute("from", "0");
        animate.setAttribute("to", value > 0 ? "-50" : "50");
    }
} else if (el.tagName.toLowerCase() === "rect") {
    // Прогресс-бар
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
        el.setAttribute("x", centerX - halfWidth);
        el.setAttribute("width", halfWidth * 2);
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



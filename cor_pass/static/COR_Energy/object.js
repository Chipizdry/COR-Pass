


function getGradientColor(value) {
    const x = Math.max(0, Math.min(100, value)); // clamp 0..100
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



function updatePowerLine(pathId, powerValue) {
    const path = document.getElementById(pathId);
    if (!path) return;

    const animate = path.querySelector("animate");

    // === 1. Если НОЛЬ — линия серая и полупрозрачная ===
    if (powerValue === 0) {
        path.style.stroke = "rgba(120,120,120,0.3)";
        if (animate) {
            animate.setAttribute("from", "0");
            animate.setAttribute("to", "0"); // стоячая линия
        }
        return;
    }

    // === 2. Цвет по модулю ===
    const color = getGradientColor(Math.abs(powerValue));
    path.style.stroke = color;

    // === 3. Прозрачность нормальная ===
    path.style.opacity = "1";

    // === 4. Направление движения ===
    if (animate) {
        if (powerValue > 0) {
            animate.setAttribute("from", "0");
            animate.setAttribute("to", "-50");
        } else {
            animate.setAttribute("from", "0");
            animate.setAttribute("to", "50");
        }
    }
}







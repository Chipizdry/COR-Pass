



  

function setupSVSViewerControls() {
    const img = document.getElementById('svs-fullscreen-image');
    const container = document.querySelector('.svs-image-container');
    let scale = 1;
    let isPanning = false;
    let startX, startY, translateX = 0, translateY = 0;

    // Zoom In
    document.querySelector('.zoom-in').addEventListener('click', () => {
        scale *= 1.2;
        updateImageTransform();
    });

    // Zoom Out
    document.querySelector('.zoom-out').addEventListener('click', () => {
        scale /= 1.2;
        updateImageTransform();
    });

    // Pan mode toggle
    document.querySelector('.pan').addEventListener('click', () => {
        isPanning = !isPanning;
        document.querySelector('.pan').classList.toggle('active', isPanning);
    });

    // Mouse/touch events for panning
    container.addEventListener('mousedown', (e) => {
        if (!isPanning) return;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
        container.style.cursor = 'grabbing';
    });

    container.addEventListener('mousemove', (e) => {
        if (!isPanning || !startX) return;
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        updateImageTransform();
    });

    container.addEventListener('mouseup', () => {
        if (!isPanning) return;
        startX = startY = null;
        container.style.cursor = isPanning ? 'grab' : 'default';
    });

    container.addEventListener('mouseleave', () => {
        startX = startY = null;
    });

    function updateImageTransform() {
        img.style.transform = `scale(${scale}) translate(${translateX}px, ${translateY}px)`;
    }
}







function handleClickLeft() {
    if (!viewer) return;
    
    const viewport = viewer.viewport;
    const currentCenter = viewport.getCenter();
    const bounds = viewport.getBounds();
    const imageBounds = viewer.world.getItemAt(0).getBounds();
    
    const deltaX = -bounds.width * 0.125;
    let newX = currentCenter.x + deltaX;
    
    const minX = imageBounds.x + bounds.width/2;
    const maxX = imageBounds.x + imageBounds.width - bounds.width/2;
    newX = Math.max(minX, Math.min(newX, maxX));
    
    // Плавное перемещение
    viewport.panTo(
        new OpenSeadragon.Point(newX, currentCenter.y),
        {
            animationTime: NAV_ANIMATION_DURATION,
            easing: function(t) {
                // Простая квадратичная функция для плавности
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            }
        }
    );
    updateNavigator();
}

// Аналогично для остальных функций (right, up, down):
function handleClickRight() {
    if (!viewer) return;
    
    const viewport = viewer.viewport;
    const currentCenter = viewport.getCenter();
    const bounds = viewport.getBounds();
    const imageBounds = viewer.world.getItemAt(0).getBounds();
    
    const deltaX = bounds.width * 0.125;
    let newX = currentCenter.x + deltaX;
    
    const minX = imageBounds.x + bounds.width/2;
    const maxX = imageBounds.x + imageBounds.width - bounds.width/2;
    newX = Math.max(minX, Math.min(newX, maxX));
    
    viewport.panTo(
        new OpenSeadragon.Point(newX, currentCenter.y),
        {
            animationTime: NAV_ANIMATION_DURATION,
            easing: function(t) {
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            }
        }
    );
    updateNavigator();
}

function handleClickUp() {
    if (!viewer) return;
    
    const viewport = viewer.viewport;
    const currentCenter = viewport.getCenter();
    const bounds = viewport.getBounds();
    const imageBounds = viewer.world.getItemAt(0).getBounds();
    
    const deltaY = -bounds.height * 0.125;
    let newY = currentCenter.y + deltaY;
    
    const minY = imageBounds.y + bounds.height/2;
    const maxY = imageBounds.y + imageBounds.height - bounds.height/2;
    newY = Math.max(minY, Math.min(newY, maxY));
    
    viewport.panTo(
        new OpenSeadragon.Point(currentCenter.x, newY),
        {
            animationTime: NAV_ANIMATION_DURATION,
            easing: function(t) {
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            }
        }
    );
    updateNavigator();
}

function handleClickDown() {
    if (!viewer) return;
    
    const viewport = viewer.viewport;
    const currentCenter = viewport.getCenter();
    const bounds = viewport.getBounds();
    const imageBounds = viewer.world.getItemAt(0).getBounds();
    
    const deltaY = bounds.height * 0.125;
    let newY = currentCenter.y + deltaY;
    
    const minY = imageBounds.y + bounds.height/2;
    const maxY = imageBounds.y + imageBounds.height - bounds.height/2;
    newY = Math.max(minY, Math.min(newY, maxY));
    
    viewport.panTo(
        new OpenSeadragon.Point(currentCenter.x, newY),
        {
            animationTime: NAV_ANIMATION_DURATION,
            easing: function(t) {
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            }
        }
    );
    updateNavigator();
}





document.getElementById('panel-close-btn').addEventListener('click', () => {
    viewer.destroy();
 
    const svsViewerDiv = document.getElementById('svs-fullscreen-viewer');
    svsViewerDiv.classList.remove('visible');
    svsViewerDiv.classList.add('hidden');
   
});




function enableAreaSelection(viewer) {
    if (!viewer) {
        console.error("Viewer is not defined");
        return;
    }

    // Ждём пока появится canvas
    const renderedCanvas = () => viewer.drawer?.canvas || viewer.canvas;
    if (!renderedCanvas()) {
        viewer.addOnceHandler("tile-loaded", () => enableAreaSelection(viewer));
        return;
    }

    // Блокируем навигацию
    viewer.setMouseNavEnabled(false);

    const containerEl = viewer.container;
    const capture = document.createElement("div");
    const box = document.createElement("div");

    Object.assign(capture.style, {
        position: "fixed",
        background: "transparent",
        zIndex: "2147483646",
        pointerEvents: "auto",
        touchAction: "none",
        cursor: "crosshair"
    });

    Object.assign(box.style, {
        position: "fixed",
        border: "2px dashed red",
        background: "rgba(255,0,0,0.12)",
        pointerEvents: "none",
        zIndex: "2147483647",
        display: "none"
    });

    document.body.appendChild(capture);
    document.body.appendChild(box);

    function positionCapture() {
        const r = containerEl.getBoundingClientRect();
        capture.style.left = r.left + "px";
        capture.style.top = r.top + "px";
        capture.style.width = r.width + "px";
        capture.style.height = r.height + "px";
    }
    positionCapture();

    let selecting = false;
    let sX = 0, sY = 0;

    function onDown(e) {
        if (e.button !== 0) return;
        selecting = true;
        sX = e.clientX;
        sY = e.clientY;
        box.style.left = sX + "px";
        box.style.top = sY + "px";
        box.style.width = "0px";
        box.style.height = "0px";
        box.style.display = "block";
    }

    function onMove(e) {
        if (!selecting) return;
        const x = Math.min(sX, e.clientX);
        const y = Math.min(sY, e.clientY);
        const w = Math.abs(e.clientX - sX);
        const h = Math.abs(e.clientY - sY);
        box.style.left = x + "px";
        box.style.top = y + "px";
        box.style.width = w + "px";
        box.style.height = h + "px";
    }

    function onUp(e) {
        if (!selecting) return cleanup();
        selecting = false;
        box.style.display = "none";

        const canvas = renderedCanvas();
        const canvasRect = canvas.getBoundingClientRect();

        const viewerRect = containerEl.getBoundingClientRect();
        const x1 = Math.max(viewerRect.left, Math.min(sX, e.clientX));
        const y1 = Math.max(viewerRect.top, Math.min(sY, e.clientY));
        const x2 = Math.min(viewerRect.right, Math.max(sX, e.clientX));
        const y2 = Math.min(viewerRect.bottom, Math.max(sY, e.clientY));

        const w = Math.max(0, x2 - x1);
        const h = Math.max(0, y2 - y1);
        if (w < 5 || h < 5) return cleanup();

        const scaleX = canvas.width / canvasRect.width;
        const scaleY = canvas.height / canvasRect.height;

        const sx = Math.round((x1 - canvasRect.left) * scaleX);
        const sy = Math.round((y1 - canvasRect.top) * scaleY);
        const sw = Math.round(w * scaleX);
        const sh = Math.round(h * scaleY);

        try {
            const out = document.createElement("canvas");
            out.width = sw;
            out.height = sh;
            out.getContext("2d").drawImage(canvas, sx, sy, sw, sh, 0, 0, sw, sh);

            const a = document.createElement("a");
            a.href = out.toDataURL("image/png");
            a.download = "selected_area.png";
            a.click();
        } catch (err) {
            alert("Ошибка: canvas tainted (CORS).");
        }

        cleanup();
    }

    function cleanup() {
        viewer.setMouseNavEnabled(true);
        capture.remove();
        box.remove();
        window.removeEventListener("resize", positionCapture);
        window.removeEventListener("scroll", positionCapture, true);
    }

    capture.addEventListener("mousedown", onDown);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("resize", positionCapture);
    window.addEventListener("scroll", positionCapture, true);
}




  

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





document.querySelector('.close-btn').addEventListener('click', () => {
    viewer.destroy();
 
    const svsViewerDiv = document.getElementById('svs-fullscreen-viewer');
    svsViewerDiv.classList.remove('visible');
    svsViewerDiv.classList.add('hidden');
   
});
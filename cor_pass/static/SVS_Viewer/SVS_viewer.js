

async function handleSVS(token) {
    try {
        // Load preview image
        const previewResponse = await fetch('/api/svs/preview_svs', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!previewResponse.ok) throw new Error('Failed to load SVS preview');
        
        const blob = await previewResponse.blob();
        const thumbnail = document.getElementById('svs-thumbnail');
        thumbnail.src = URL.createObjectURL(blob);
        document.getElementById('svs-preview-container').style.display = 'block';
        document.getElementById('viewer-controls').style.display = 'none';
        
        // Add click handler to open fullscreen
        thumbnail.onclick = () => openFullscreenSVS(blob, token);
        
        // Load metadata
        await loadSvsMetadata(token);
    } catch (err) {
        console.error("Error handling SVS file:", err);
        document.getElementById('upload-status').textContent = `Error: ${err.message}`;
    }
}



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



async function loadSvsMetadata(token, isFullscreen = false) {
    try {
        const metadataRes = await fetch('/api/svs/svs_metadata', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!metadataRes.ok) return null;
        const svsMetadata = await metadataRes.json();
        
        const metadataHTML = generateSvsMetadataHTML(svsMetadata);
        
        if (isFullscreen) {
            document.getElementById('svs-metadata-content').innerHTML = metadataHTML;
        } else {
            document.getElementById('metadata-content').innerHTML = metadataHTML;
            document.getElementById('metadata-container').style.display = 'block';
        }
        
        return svsMetadata;
    } catch (err) {
        console.error("Error loading SVS metadata:", err);
        return null;
    }
}





function generateSvsMetadataHTML(svsMetadata) {
    return `
        <div class="metadata-section">
            <h4>Basic Information</h4>
            <div class="metadata-grid">
                <div class="metadata-item"><span class="metadata-label">Filename:</span> ${svsMetadata.filename}</div>
                <div class="metadata-item"><span class="metadata-label">Dimensions:</span> ${svsMetadata.dimensions.width.toLocaleString()} × ${svsMetadata.dimensions.height.toLocaleString()} px</div>
                <div class="metadata-item"><span class="metadata-label">Levels:</span> ${svsMetadata.dimensions.levels}</div>
                <div class="metadata-item"><span class="metadata-label">MPP:</span> ${svsMetadata.basic_info.mpp}</div>
                <div class="metadata-item"><span class="metadata-label">Magnification:</span> ${svsMetadata.basic_info.magnification}x</div>
                <div class="metadata-item"><span class="metadata-label">Scan Date:</span> ${svsMetadata.basic_info.scan_date}</div>
                <div class="metadata-item"><span class="metadata-label">Scanner:</span> ${svsMetadata.basic_info.scanner}</div>
            </div>
        </div>

        <div class="metadata-section">
            <h4>Level Details</h4>
            <table class="metadata-table">
                <thead><tr><th>Level</th><th>Downsample</th><th>Dimensions</th></tr></thead>
                <tbody>
                    ${svsMetadata.levels.map((lvl, i) => `
                        <tr><td>${i}</td><td>${lvl.downsample.toFixed(1)}</td><td>${lvl.width.toLocaleString()} × ${lvl.height.toLocaleString()}</td></tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="metadata-section">
            <details class="technical-metadata">
                <summary>Technical Metadata</summary>
                <pre>${svsMetadata.full_properties ? Object.entries(svsMetadata.full_properties).map(([k, v]) => `${k}: ${v}`).join('\n') : 'No technical metadata available.'}</pre>
            </details>
        </div>
    `;
}




function openFullscreenSVS() {
    const svsViewerDiv = document.getElementById('svs-fullscreen-viewer');
    svsViewerDiv.style.display = 'block';
  
    // Если viewer уже создан - уничтожаем, чтобы создать заново
    if (viewer) {
      viewer.destroy();
    }
  
    viewer = OpenSeadragon({
      id: "openseadragon1",
      prefixUrl: "/static/SVS_Viewer/images/",
      tileSources: {
        // Здесь укажите свой источник, например, путь к SVS или tiles (пример)
        type: 'image',
        url: document.getElementById('svs-thumbnail').src
      },
      showNavigator: false,
      gestureSettingsMouse: {
        scrollToZoom: true,
        clickToZoom: false,
        dblClickToZoom: true,
        dragToPan: true
      },
      minZoomLevel: 0.5,  // минимальный zoom
      maxZoomLevel: 10,
    });
  
    // Начальный zoom (например, очень маленький)
    viewer.addHandler('open', function() {
      viewer.viewport.zoomTo(0.1); // начальный маленький зум
      viewer.viewport.panTo(new OpenSeadragon.Point(0.5, 0.5)); // центрируем изображение
    });
  
    // Обработчики кнопок:
    document.querySelector('.zoom-in').onclick = () => viewer.viewport.zoomBy(1.5);
    document.querySelector('.zoom-out').onclick = () => viewer.viewport.zoomBy(0.5);
    document.querySelector('.home').onclick = () => viewer.viewport.goHome();
    document.querySelector('.close-btn').onclick = () => {
      viewer.destroy();
      svsViewerDiv.style.display = 'none';
    };
  }
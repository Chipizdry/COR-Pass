

async function handleSVS(token) {
    try {
        // Load preview image
        const previewResponse = await fetch('/api/dicom/preview_svs', {
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


async function openFullscreenSVS(blob = null, token = null) {
    if (checkToken()) {
        const fullscreenViewer = document.getElementById('svs-fullscreen-viewer');
        const dcmViewerFrame = document.getElementById('DcmViewerFrame');
        
        if (dcmViewerFrame) dcmViewerFrame.classList.add('hidden');
        fullscreenViewer.style.display = 'block';
        
        try {
            token = token || getToken();
            
            // First load the metadata before initializing OpenSeadragon
            const metadata = await loadSvsMetadata(token, true);
            if (!metadata) throw new Error('Failed to load SVS metadata');
            
            // Initialize OpenSeadragon after metadata is loaded
            if (viewer) {
                viewer.destroy();
            }
            
            // Современный формат конфигурации для OpenSeadragon
            viewer = OpenSeadragon({
                id: "svs-fullscreen-viewer",
                prefixUrl: "/static/SVS_Viewer/images/",
                tileSources: {
                    type: 'image',
                    url: '/api/dicom/svs_tiles',
                    ajaxWithCredentials: true,
                    ajaxHeaders: {
                        'Authorization': `Bearer ${token}`
                    },
                    // УДАЛИТЬ: tileSize: 256, // Этот параметр больше не нужен
                    width: metadata.dimensions.width,
                    height: metadata.dimensions.height,
                    tileWidth: 256,  // Явно указываем ширину тайла
                    tileHeight: 256,  // Явно указываем высоту тайла
                    minLevel: 0,
                    maxLevel: metadata.dimensions.levels - 1,
                    getTileUrl: function(level, x, y) {
                        // Убедитесь, что размер соответствует tileWidth/tileHeight
                        return `/api/dicom/svs_tiles?level=${level}&x=${x*256}&y=${y*256}&size=256`;
                    }
                },
                showNavigationControl: false,
                showZoomControl: false,
                showHomeControl: false,
                showFullPageControl: false,
                showRotationControl: false,
                showFlipControl: false,
                showNavigator: false,
                gestureSettingsMouse: {
                    scrollToZoom: false,
                    clickToZoom: false,
                    dblClickToZoom: false,
                    pinchToZoom: false
                },
                gestureSettingsTouch: {
                    scrollToZoom: false,
                    clickToZoom: false,
                    dblClickToZoom: false,
                    pinchToZoom: false
                },
                gestureSettingsPen: {
                    scrollToZoom: false,
                    clickToZoom: false,
                    dblClickToZoom: false,
                    pinchToZoom: false
                }
            });
            
        } catch (err) {
            console.error("Error in openFullscreenSVS:", err);
            if (err.message.includes('401')) {
                window.location.href = '/';
            }
        }
    }
}



async function openFullscreenSVSFromThumbnail() {
    const token = getToken();
    const fullscreenViewer = document.getElementById('svs-fullscreen-viewer');
    const fullscreenImg = document.getElementById('svs-fullscreen-image');
    
    // Показываем контейнер и индикатор загрузки
    fullscreenViewer.style.display = 'block';
    fullscreenImg.classList.add('loading');
    
    try {
        // Загружаем полное изображение первого уровня
        const response = await fetch('/api/dicom/preview_svs?full=true&level=0', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error(`Failed to load full SVS image: ${response.status}`);
        }
        
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        
        // Создаем временное изображение для проверки загрузки
        const tempImg = new Image();
        tempImg.onload = () => {
            fullscreenImg.src = objectUrl;
            fullscreenImg.classList.remove('loading');
            fullscreenImg.style.transform = 'none';
            URL.revokeObjectURL(objectUrl);
        };
        tempImg.onerror = () => {
            fullscreenImg.classList.remove('loading');
            URL.revokeObjectURL(objectUrl);
            throw new Error('Failed to load image');
        };
        tempImg.src = objectUrl;
        
        // Загружаем метаданные
        await loadSvsMetadata(token, true);
        
    } catch (err) {
        console.error("Error opening fullscreen SVS:", err);
        fullscreenImg.classList.remove('loading');
        alert("Failed to open fullscreen viewer: " + err.message);
        fullscreenViewer.style.display = 'none';
    }
}

async function loadSvsMetadata(token, isFullscreen = false) {
    try {
        const metadataRes = await fetch('/api/dicom/svs_metadata', {
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
        
        return svsMetadata; // <- Важно: возвращаем метаданные
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



//Функция получения токена 
function getToken() {
    return localStorage.getItem('authToken') || 
           new URLSearchParams(window.location.search).get('access_token');
}


function prepareUIBeforeUpload() {
    document.getElementById('upload-status').textContent = 'Preparing upload...';
    const progressBar = document.getElementById('progress-bar');
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    document.getElementById('metadata-container').style.display = 'none';
    document.getElementById('svs-preview-container').style.display = 'none';
  }


  function collectFiles(fileInput) {
    const formData = new FormData();
    let totalSize = 0;
    let fileCount = 0;
  
    for (const file of fileInput.files) {
      const fileExt = file.name.split('.').pop().toLowerCase();
      if (['', 'dcm', 'zip', 'svs'].includes(fileExt)) {
        formData.append('files', file);
        totalSize += file.size;
        fileCount++;
      }
    }
    return { formData, totalSize, fileCount };
  }

  
  async function uploadFiles(formData, token) {
    const response = await fetch('/api/dicom/upload', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
  
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return response.json();
  }


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

async function openFullscreenSVS(blob = null, token = null) {
    const fullscreenViewer = document.getElementById('svs-fullscreen-viewer');
    const fullscreenImg = document.getElementById('svs-fullscreen-image');
    const dcmViewerFrame = document.getElementById('DcmViewerFrame');
    
    // Скрываем DICOM viewer
    if (dcmViewerFrame) dcmViewerFrame.classList.add('hidden');
    
    // Показываем контейнер и индикатор загрузки
    fullscreenViewer.style.display = 'block';
    fullscreenImg.classList.add('loading');
    
    try {
        token = token || getToken();
        
        // Если blob не передан, загружаем изображение
        if (!blob) {
            const response = await fetch('/api/dicom/preview_svs?full=true&level=0', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) throw new Error('Failed to load SVS preview');
            blob = await response.blob();
        }
        
        const objectUrl = URL.createObjectURL(blob);
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
        console.error("Error in openFullscreenSVS:", err);
        fullscreenImg.classList.remove('loading');
        fullscreenViewer.style.display = 'none';
        if (err.message.includes('401')) {
            window.location.href = '/';
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
        
        if (!metadataRes.ok) return;
        const svsMetadata = await metadataRes.json();
        
        const metadataHTML = generateSvsMetadataHTML(svsMetadata);
        
        if (isFullscreen) {
            document.getElementById('svs-metadata-content').innerHTML = metadataHTML;
        } else {
            document.getElementById('metadata-content').innerHTML = metadataHTML;
            document.getElementById('metadata-container').style.display = 'block';
        }
    } catch (err) {
        console.error("Error loading SVS metadata:", err);
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

  
  async function handleDICOM(token) {
    const svsPreview = document.getElementById('svs-preview-container');
    svsPreview.style.display = 'none';
  
    const dcmViewerFrame = document.getElementById('DcmViewerFrame');
    dcmViewerFrame.classList.remove('hidden');
   // dcmViewerFrame.style.display = 'flex'; // или 'block' — в зависимости от твоего layout
  
    const volumeInfo = await fetch('/api/dicom/volume_info', {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(res => res.json());
  
    updateSliders(volumeInfo);
  
    const metadata = await fetch('/api/dicom/metadata', {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(res => res.json());
  
    document.getElementById('metadata-container').style.display = 'block';
    document.getElementById('metadata-content').innerHTML = `
      <p><strong>Dimensions:</strong> Axial: ${metadata.shape.depth}, Coronal: ${metadata.shape.height}, Sagittal: ${metadata.shape.width}</p>
      <p><strong>Spacing:</strong> X: ${metadata.spacing.x.toFixed(2)} mm, Y: ${metadata.spacing.y.toFixed(2)} mm, Z: ${metadata.spacing.z.toFixed(2)} mm</p>
      <p><strong>Study UID:</strong> ${metadata.study_info.StudyInstanceUID}</p>
      <p><strong>Series UID:</strong> ${metadata.study_info.SeriesInstanceUID}</p>
      <p><strong>Modality:</strong> ${metadata.study_info.Modality}</p>
      <p><strong>Date:</strong> ${metadata.study_info.StudyDate}</p>
      <p><strong>Patient:</strong> ${metadata.study_info.PatientName}</p>
      <p><strong>Birth Date:</strong> ${metadata.study_info.PatientBirthDate}</p>
      <p><strong>Manufacturer:</strong> ${metadata.study_info.Manufacturer}</p>
      <p><strong>Model:</strong> ${metadata.study_info.DeviceModel}</p>
      <p><strong>KVP:</strong> ${metadata.study_info.KVP}</p>
      <p><strong>Current (mA):</strong> ${metadata.study_info.XRayTubeCurrent}</p>
      <p><strong>Exposure (mAs):</strong> ${metadata.study_info.Exposure}</p>
    `;
  
    ['axial', 'sagittal', 'coronal'].forEach(update);
  }


  async function handleUpload() {
   
  
    const fileInput = document.getElementById('dicom-upload');
    if (!fileInput.files.length) {
      document.getElementById('upload-status').textContent = 'Please select files';
      return;
    }
  
    prepareUIBeforeUpload();
    const token = getToken();
    const { formData, totalSize, fileCount } = collectFiles(fileInput);
  
    if (fileCount === 0) {
      document.getElementById('upload-status').textContent = 'No valid files selected';
      return;
    }
  
    document.getElementById('file-info').textContent = `Selected ${fileCount} files (${formatFileSize(totalSize)})`;
    document.getElementById('upload-status').textContent = 'Uploading...';
  
    try {
      const result = await uploadFiles(formData, token);
      document.getElementById('upload-status').textContent = result.message;
      document.getElementById('progress-bar').style.width = '100%';
      document.getElementById('progress-bar').textContent = '100%';
  
      if (result.message.includes('SVS')) {
        await handleSVS(token);
      } else {
        await handleDICOM(token);
      }
    } catch (err) {
      document.getElementById('upload-status').textContent = `Error: ${err.message}`;
      document.getElementById('progress-bar').style.background = '#f44336';
      if (err.message.includes('401')) window.location.href = '/';
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

function uploadFilesWithProgress(formData, token) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/dicom/upload");

    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('upload-status');

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width = percent + "%";
        progressBar.textContent = percent + "%";
        statusText.textContent = `Uploading... (${percent}%)`;
      }
    });

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}




function prepareUIBeforeUpload() {
  const progressBar = document.getElementById('progress-bar');
  document.getElementById('upload-status').textContent = 'Preparing upload...';
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
      const fileParts = file.name.split('.');
      const fileExt = fileParts.length > 1 ? fileParts.pop().toLowerCase() : '';
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

  
  async function handleDICOM(token) {
    const svsPreview = document.getElementById('svs-preview-container');
    svsPreview.style.display = 'none';
  
    const dcmViewerFrame = document.getElementById('DcmViewerFrame');
    dcmViewerFrame.classList.remove('hidden');
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
    isDicomLoaded = true;
    ['axial', 'sagittal', 'coronal'].forEach(update);
  }

  async function handleUpload() {
    const fileInput = document.getElementById('dicom-upload');
    const statusText = document.getElementById('upload-status');
    const progressBar = document.getElementById('progress-bar');
  
    if (!fileInput.files.length) {
      statusText.textContent = 'Please select files';
      return;
    }
  
    prepareUIBeforeUpload();
    const token = getToken();
    const { formData, totalSize, fileCount } = collectFiles(fileInput);
  
    if (fileCount === 0) {
      statusText.textContent = 'No valid files selected';
      return;
    }
  
    document.getElementById('file-info').textContent =
      `Selected ${fileCount} files (${formatFileSize(totalSize)})`;
  
    statusText.textContent = 'Uploading...';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    document.getElementById('loading-spinner')?.style?.setProperty("display", "block");
  
    try {
      const result = await uploadFilesWithProgress(formData, token);
  
      progressBar.style.width = '100%';
      progressBar.textContent = '100%';
  
      if (result.steps) {
        statusText.innerHTML =
          result.steps.map(step => `<div>${step}</div>`).join('') +
          `<div style="margin-top: 8px;"><strong>${result.message}</strong></div>`;
      } else {
        statusText.textContent = result.message;
      }
  
      if (result.message.includes('SVS')) {
        await handleSVS(token);
      } else {
        await handleDICOM(token);
      }
    } catch (err) {
      console.error('Upload failed:', err);
      statusText.textContent = `Error: ${err.message}`;
      progressBar.style.background = '#f44336';
      if (err.message.includes('401')) {
        showTokenExpiredModal();
      }
    } finally {
      document.getElementById('loading-spinner')?.style?.setProperty("display", "none");
    }
  }


async function update(plane, callback) {
  if (!isDicomLoaded) { return;}
    const idx = parseInt(document.getElementById(plane).value);
    const canvas = document.getElementById('canvas-' + plane);
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    // Получаем токен из localStorage или URL
    const token =  getToken();

    img.onload = function() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        drawCrossOnPlane(ctx, plane);
        // Добавляем проверку, является ли callback функцией перед вызовом
        if (callback && typeof callback === 'function') {
            callback();
        }
    };

    // Создаем URL с параметрами
    const params = new URLSearchParams({
        index: idx,
        mode: currentMode,
        t: Date.now()
    });

    if (currentMode === 'window') {
        params.append('window_center', manualWindowCenter);
        params.append('window_width', manualWindowWidth);
    }

    try {
        const response = await fetch(`/api/dicom/reconstruct/${plane}?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const blob = await response.blob();
        img.src = URL.createObjectURL(blob);
    } catch (error) {
        console.error('Error loading DICOM image:', error);
        // Обработка ошибок (например, показать сообщение)
        if (error.message.includes('401')) {
          showTokenExpiredModal();
        }
    }
}


  // Добавление метки по клику
  function addMarker(event, plane) {
    const canvas = event.target;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(event.clientX - rect.left);
    const y = Math.round(event.clientY - rect.top);
  
    // Получаем фактические размеры изображения на canvas
    const imgWidth = canvas.width;
    const imgHeight = canvas.height;
    const scaleX = 512 / imgWidth;
    const scaleY = 512 / imgHeight;
  
    const indices = {
      axial: parseInt(document.getElementById('axial').value),
      sagittal: parseInt(document.getElementById('sagittal').value),
      coronal: parseInt(document.getElementById('coronal').value),
    };
  
    let point3D;
  
    if (plane === 'axial') {
      point3D = { 
        x: x * scaleX, 
        y: y * scaleY, 
        z: indices.axial 
      };
    } else if (plane === 'sagittal') {
      point3D = {
        x: indices.sagittal,
        y: 512 - (x * scaleX),  // учитываем переворот изображения
        z: 512 - (y * scaleY)    // x на изображении становится z в объеме
      };
    } else if (plane === 'coronal') {
      point3D = {
        x: x * scaleX,
        y: indices.coronal,
        z: 512 - (y * scaleY)    // учитываем переворот изображения
      };
    }
  
    markers3D = [point3D];
    drawCrossOnSlices(point3D);
  }


  
function updateSliders(volumeInfo) {
    // Используем slices вместо depth, если shape отсутствует
    const depth = volumeInfo.shape?.depth ?? volumeInfo.slices;
    const width = volumeInfo.shape?.width ?? volumeInfo.width;
    const height = volumeInfo.shape?.height ?? volumeInfo.height;
  
    // Устанавливаем максимальные значения для каждого ползунка
    document.getElementById('axial').max = Math.max(0, depth - 1);
    document.getElementById('sagittal').max = Math.max(0, width - 1);
    document.getElementById('coronal').max = Math.max(0, height - 1);
    
    // Устанавливаем средние значения
    document.getElementById('axial').value = Math.floor(depth / 2);
    document.getElementById('sagittal').value = Math.floor(width / 2);
    document.getElementById('coronal').value = Math.floor(height / 2);
    
    // Обновляем отображаемые значения
    updateSliderValue('axial');
    updateSliderValue('sagittal');
    updateSliderValue('coronal');
  }
  
  // Функция для обновления отображаемого значения ползунка
  function updateSliderValue(plane) {
    const slider = document.getElementById(plane);
    const valueDisplay = slider.nextElementSibling; 
    if (valueDisplay && valueDisplay.classList.contains('dcm-range-value')) {
      valueDisplay.textContent = slider.value;
    }
  }
  


 // Рисование перекрестия на конкретном срезе
 function drawCrossOnPlane(ctx, plane, point3D = markers3D[0]) {
    if (!point3D) return;
  
    // Получаем размеры изображения на canvas
    const canvas = ctx.canvas;
    const imgWidth = canvas.width;
    const imgHeight = canvas.height;
    
    // Рассчитываем масштабные коэффициенты
    const scaleX = imgWidth / 512;
    const scaleY = imgHeight / 512;
  
    ctx.strokeStyle = 'lime';
    ctx.lineWidth = 1;
    ctx.beginPath();
  
    if (plane === 'axial') {
      // Для аксиальной плоскости просто используем x и y
      const yPos = point3D.y * scaleY;
      ctx.moveTo(0, yPos);
      ctx.lineTo(imgWidth, yPos);
      
      const xPos = point3D.x * scaleX;
      ctx.moveTo(xPos, 0);
      ctx.lineTo(xPos, imgHeight);
    } else if (plane === 'sagittal') {
      // Для сагиттальной плоскости
      const imgZ = (512 - point3D.z) * scaleY;
      ctx.moveTo(0, imgZ);
      ctx.lineTo(imgWidth, imgZ);
  
      const yPos = (512 - point3D.y) * scaleX;
      ctx.moveTo(yPos, 0);
      ctx.lineTo(yPos, imgHeight);
    } else if (plane === 'coronal') {
      // Для корональной плоскости
      const imgZ = (512 - point3D.z) * scaleY;
      ctx.moveTo(0, imgZ);
      ctx.lineTo(imgWidth, imgZ);
      
      const xPos = point3D.x * scaleX;
      ctx.moveTo(xPos, 0);
      ctx.lineTo(xPos, imgHeight);
    }
  
    ctx.stroke();
  } 


  

    // Рисование перекрестия на всех срезах
    function drawCrossOnSlices(point3D) {
        ['axial', 'sagittal', 'coronal'].forEach(plane => {
          update(plane, () => {
            const canvas = document.getElementById('canvas-' + plane);
            const ctx = canvas.getContext('2d');
            drawCrossOnPlane(ctx, plane, point3D);
          });
        });
      }


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
            thumbnail.onclick = () => openFullscreenSVS();
            
            // Load metadata
            await loadSvsMetadata(token);
        } catch (err) {
            console.error("Error handling SVS file:", err);
            document.getElementById('upload-status').textContent = `Error: ${err.message}`;
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
            console.log("SVS Metadata levels info:");
            svsMetadata.levels.forEach((lvl, idx) => {
              console.log(`Level ${idx}: size ${lvl.width}x${lvl.height}, tiles_x=${lvl.tiles_x}, tiles_y=${lvl.tiles_y}, total=${lvl.total_tiles}`);
            });
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
  


  const navOverlay = document.createElement('canvas');
  navOverlay.id = 'tile-navigator';
  navOverlay.width = 150;  
  navOverlay.height = 150; 
  navOverlay.style.position = 'absolute';
  navOverlay.style.bottom = '10px';
  navOverlay.style.left = '10px';
  navOverlay.style.border = '1px solid white';
  navOverlay.style.background = 'rgba(0,0,0,0.6)';
  navOverlay.style.zIndex = '10001';

  
  document.getElementById('svs-fullscreen-viewer').appendChild(navOverlay);
  const navCtx = navOverlay.getContext('2d');

  function updateNavigator() {
    if (!viewer || !viewer.world.getItemAt(0)) return;
  
    const tiledImage = viewer.world.getItemAt(0);
    if (!tiledImage || !tiledImage.source) return;
  
    const levelsCount = tiledImage.source.levels.length;
    
    // Получаем текущий уровень через zoom
    const zoom = viewer.viewport.getZoom(true);
    const imageZoom = zoom * tiledImage.source.width / tiledImage.source.dimensions.x;
    const osdLevel = Math.min(
      Math.max(
        Math.floor(Math.log(imageZoom) / Math.log(2)),
        0
      ),
      levelsCount - 1
    );
  
    // Преобразуем OSD уровень в SVS уровень (инвертируем)
    const svsLevel = (levelsCount - 1) - osdLevel;
    const currentLevel = tiledImage.source.levels[osdLevel];
    const levelWidth = currentLevel.width;
    const levelHeight = currentLevel.height;
    const tileSize = tiledImage.source.tileSize;
  
    const canvasW = navOverlay.width;
    const canvasH = navOverlay.height;
    const scaleX = canvasW / levelWidth;
    const scaleY = canvasH / levelHeight;
  
    navCtx.clearRect(0, 0, canvasW, canvasH);
    navCtx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    navCtx.fillRect(0, 0, canvasW, canvasH);
  
    // Рисуем сетку тайлов
    navCtx.strokeStyle = 'white';
    navCtx.lineWidth = 0.5;
    
    const cols = Math.ceil(levelWidth / tileSize);
    const rows = Math.ceil(levelHeight / tileSize);
  
    for (let x = 0; x <= cols; x++) {
      navCtx.beginPath();
      navCtx.moveTo(x * tileSize * scaleX, 0);
      navCtx.lineTo(x * tileSize * scaleX, canvasH);
      navCtx.stroke();
    }
    for (let y = 0; y <= rows; y++) {
      navCtx.beginPath();
      navCtx.moveTo(0, y * tileSize * scaleY);
      navCtx.lineTo(canvasW, y * tileSize * scaleY);
      navCtx.stroke();
    }
  
    // Рисуем прямоугольник просмотра
    const bounds = viewer.viewport.getBoundsNoRotate();
    const x = bounds.x * levelWidth * scaleX;
    const y = bounds.y * levelHeight * scaleY;
    const w = bounds.width * levelWidth * scaleX;
    const h = bounds.height * levelHeight * scaleY;
  
    navCtx.strokeStyle = 'red';
    navCtx.lineWidth = 1.5;
    navCtx.strokeRect(x, y, w, h);
  
    // Отображаем уровень (показываем SVS уровень, а не OSD уровень)
    navCtx.fillStyle = 'yellow';
    navCtx.font = '14px sans-serif';
    navCtx.fillText(`Level: ${svsLevel}/${levelsCount - 1}`, 12, canvasH - 12);
  }


  async function openFullscreenSVS() {
    const token = getToken();
    const svsViewerDiv = document.getElementById('svs-fullscreen-viewer');
    svsViewerDiv.classList.remove('hidden');
    svsViewerDiv.classList.add('visible');
  
    const headers = {
      Authorization: `Bearer ${token}`
    };
  
    try {
      const svsMetadata = await loadSvsMetadata(token, true);
      if (!svsMetadata) {
        alert("❌ Не удалось загрузить метаданные SVS.");
        return;
      }
  
      const tileSize = 256;
      const levelsCount = svsMetadata.dimensions.levels;
  
      console.log('[openFullscreenSVS] Метаданные (все уровни):', svsMetadata);
  
      if (viewer) {
        console.log('[openFullscreenSVS] Уничтожение старого viewer');
        viewer.destroy();
      }
  
      // Инвертируем порядок уровней (чтобы уровень 0 был наименьшим разрешением)
      const invertedLevels = [...svsMetadata.levels].reverse();
  
      // Создаем tile source с инвертированными уровнями
      viewer = OpenSeadragon({
        id: "openseadragon1",
        prefixUrl: "/static/SVS_Viewer/images/",
        tileSources: {
          width: svsMetadata.dimensions.width,
          height: svsMetadata.dimensions.height,
          tileSize: tileSize,
          minLevel: 0,
          maxLevel: levelsCount - 1,
          getTileUrl: (level, x, y) => {
            // Преобразуем уровень OpenSeadragon в инвертированный уровень SVS
            const svsLevel = (levelsCount - 1) - level;
            return `/api/svs/tile?level=${svsLevel}&x=${x}&y=${y}&tile_size=${tileSize}`;
          },
          levels: invertedLevels.map((level, index) => ({
            width: level.width,
            height: level.height,
            url: `/api/svs/tile?level=${(levelsCount - 1) - index}&tile_size=${tileSize}`
          }))
        },
        showNavigator: false,
        showZoomControl: false,
        showFullPageControl: false,
        showHomeControl: false,
        showRotationControl: false,
        loadTilesWithAjax: true,
        ajaxHeaders: headers,
        visibilityRatio: 1,
        constrainDuringPan: true,
        homeFillsViewer: true,
        preserveImageSizeOnResize: true,
        maxZoomPixelRatio: 8,
        immediateRender: true,
        zoomPerScroll: 1.2,
        minZoomLevel: 0.1,
        animationTime: 0.5,
        springStiffness: 5.0,
        imageLoaderLimit: 5
      });
  
      viewer.addHandler('open', () => {
        console.log('[openFullscreenSVS] Viewer открыт');
        viewer.viewport.goHome();
        
        viewer.addHandler('zoom', updateNavigator);
        viewer.addHandler('pan', updateNavigator);
        viewer.addHandler('tile-loaded', updateNavigator);
      });
  
      viewer.addHandler('tile-loaded', (event) => {
        const actualSvsLevel = (levelsCount - 1) - event.tile.level;
        console.log('[tile-loaded] Загружен тайл:', {
          osdLevel: event.tile.level,
          svsLevel: actualSvsLevel,
          x: event.tile.x,
          y: event.tile.y
        });
      });
  
      const closeBtn = document.querySelector('.close-btn');
      if (closeBtn) {
        closeBtn.onclick = () => {
          viewer.destroy();
          viewer = null;
          svsViewerDiv.classList.remove('visible');
          svsViewerDiv.classList.add('hidden');
        };
      }
  
    } catch (error) {
      console.error('[openFullscreenSVS] Ошибка:', error);
      document.getElementById('upload-status').textContent = `Ошибка загрузки: ${error}`;
    }
  }



  function openDicomFullscreen(plane) {
    // Создаем контейнер для полноэкранного просмотра
    const fullscreenViewer = document.createElement('div');
    fullscreenViewer.id = 'dicom-fullscreen-viewer';
    fullscreenViewer.className = 'dicom-fullscreen-viewer';
    
    // Создаем хедер
    const header = document.createElement('div');
    header.className = 'dicom-fullscreen-header';
    
    const title = document.createElement('span');
    title.textContent = plane.charAt(0).toUpperCase() + plane.slice(1); // Capitalize first letter
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '🗗'; 
    closeBtn.className = 'dicom-buttons'; 
    closeBtn.onclick = function() {
      document.body.removeChild(fullscreenViewer);
    };
    
    header.appendChild(title);
    header.appendChild(closeBtn);
    
    // Создаем контейнер для контента
    const content = document.createElement('div');
    content.className = 'dicom-fullscreen-content';
    
    // Создаем canvas для полноэкранного отображения
    const fullscreenCanvas = document.createElement('canvas');
    fullscreenCanvas.className = 'dicom-fullscreen-canvas';
    fullscreenCanvas.id = `fullscreen-canvas-${plane}`;
    
    // Создаем контролы для слайдера
    const controlsDiv = document.createElement('div');
    controlsDiv.className = 'dicom-fullscreen-controls';
    
    const sliderContainer = document.createElement('div');
    sliderContainer.className = 'dcm-range-container';
    
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.id = `fullscreen-${plane}`;
    slider.min = document.getElementById(plane).min;
    slider.max = document.getElementById(plane).max;
    slider.value = document.getElementById(plane).value;
    
    const valueDisplay = document.createElement('span');
    valueDisplay.className = 'dcm-range-value';
    valueDisplay.textContent = slider.value;
    
    slider.oninput = function() {
      updateSliderValue(`fullscreen-${plane}`);
      updateFullscreenDicom(plane);
    };
    
    // Собираем все элементы
    sliderContainer.appendChild(slider);
    sliderContainer.appendChild(valueDisplay);
    controlsDiv.appendChild(sliderContainer);
    content.appendChild(fullscreenCanvas);
    content.appendChild(controlsDiv);
    
    fullscreenViewer.appendChild(header);
    fullscreenViewer.appendChild(content);
    
    // Добавляем на страницу
    document.body.appendChild(fullscreenViewer);
    
    // Загружаем изображение
    updateFullscreenDicom(plane);
  }



async function updateFullscreenDicom(plane) {
  const fullscreenViewer = document.getElementById('dicom-fullscreen-viewer');
  const fullscreenCanvas = document.getElementById(`fullscreen-canvas-${plane}`);
  const ctx = fullscreenCanvas.getContext('2d');
  const idx = parseInt(document.getElementById(`fullscreen-${plane}`).value);
  
  // Рассчитываем размер с учетом хедера и контролов
  const headerHeight = document.querySelector('.dicom-fullscreen-header').offsetHeight;
  const controlsHeight = document.querySelector('.dicom-fullscreen-controls').offsetHeight;
  const availableHeight = window.innerHeight - headerHeight - controlsHeight - 20; // 20px padding
  
  const maxSize = Math.min(window.innerWidth * 0.9, availableHeight);
  fullscreenCanvas.width = maxSize;
  fullscreenCanvas.height = maxSize;
  
  const img = new Image();
  img.onload = function() {
    ctx.clearRect(0, 0, fullscreenCanvas.width, fullscreenCanvas.height);
    
    // Рассчитываем размеры для сохранения пропорций
    const ratio = Math.min(
      fullscreenCanvas.width / img.width,
      fullscreenCanvas.height / img.height
    );
    const newWidth = img.width * ratio;
    const newHeight = img.height * ratio;
    const offsetX = (fullscreenCanvas.width - newWidth) / 2;
    const offsetY = (fullscreenCanvas.height - newHeight) / 2;
    
    ctx.drawImage(img, offsetX, offsetY, newWidth, newHeight);
  };
  
  const token = getToken();
  const params = new URLSearchParams({
    index: idx,
    mode: currentMode,
    t: Date.now()
  });

  if (currentMode === 'window') {
    params.append('window_center', manualWindowCenter);
    params.append('window_width', manualWindowWidth);
  }

  try {
    const response = await fetch(`/api/dicom/reconstruct/${plane}?${params.toString()}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    
    const blob = await response.blob();
    img.src = URL.createObjectURL(blob);
  } catch (error) {
    console.error('Error loading DICOM image:', error);
    if (error.message.includes('401')) {
      showTokenExpiredModal();
    }
  }
}

// Модифицируем обработчик кнопок полноэкранного режима
document.querySelectorAll('.dicom-buttons').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetPlane = btn.getAttribute('data-target');
    openDicomFullscreen(targetPlane.replace('canvas-', ''));
  });
});
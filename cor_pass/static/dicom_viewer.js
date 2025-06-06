

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
      if (err.message.includes('401'))  showTokenExpiredModal();
    }
}

async function update(plane, callback) {
    const idx = parseInt(document.getElementById(plane).value);
    const canvas = document.getElementById('canvas-' + plane);
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    // Получаем токен из localStorage или URL
    const token = localStorage.getItem('authToken') || 
                  new URLSearchParams(window.location.search).get('access_token');

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
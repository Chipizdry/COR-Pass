

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
    const previewResponse = await fetch('/api/dicom/preview_svs', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!previewResponse.ok) throw new Error('Failed to load SVS preview');
  
    const blob = await previewResponse.blob();
    document.getElementById('svs-thumbnail').src = URL.createObjectURL(blob);
    document.getElementById('svs-preview-container').style.display = 'block';
    document.getElementById('viewer-controls').style.display = 'none';
  
    try {
      const metadataRes = await fetch('/api/dicom/svs_metadata', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
  
      if (!metadataRes.ok) return;
      const svsMetadata = await metadataRes.json();
  
      let metadataHTML = `
        <h4>Basic Information</h4>
        <p><strong>Filename:</strong> ${svsMetadata.filename}</p>
        <p><strong>Dimensions:</strong> ${svsMetadata.dimensions.width.toLocaleString()} × ${svsMetadata.dimensions.height.toLocaleString()} px (Levels: ${svsMetadata.dimensions.levels})</p>
        <p><strong>Microns per pixel:</strong> ${svsMetadata.basic_info.mpp}</p>
        <p><strong>Magnification:</strong> ${svsMetadata.basic_info.magnification}x</p>
        <p><strong>Scan Date:</strong> ${svsMetadata.basic_info.scan_date}</p>
        <p><strong>Scanner:</strong> ${svsMetadata.basic_info.scanner}</p>
  
        <h4>Slide Properties</h4>
        <table class="metadata-table">
          <tr><td><strong>Vendor</strong></td><td>${svsMetadata.basic_info.vendor}</td></tr>
          <tr><td><strong>Format</strong></td><td>${svsMetadata.full_properties?.['tiff.ImageDescription']?.split('|')[0] || 'N/A'}</td></tr>
        </table>
  
        <h4>Level Details</h4>
        <table class="metadata-table">
          <thead><tr><th>Level</th><th>Downsample</th><th>Dimensions</th></tr></thead>
          <tbody>
            ${svsMetadata.levels.map((lvl, i) => `
              <tr><td>${i}</td><td>${lvl.downsample.toFixed(1)}</td><td>${lvl.width.toLocaleString()} × ${lvl.height.toLocaleString()}</td></tr>
            `).join('')}
          </tbody>
        </table>
  
        <h4>Technical Metadata</h4>
        <details><summary>Show full metadata</summary><pre>${svsMetadata.full_properties ? Object.entries(svsMetadata.full_properties).map(([k, v]) => `${k}: ${v}`).join('\n') : 'No technical metadata available.'}</pre></details>
      `;
  
      if (svsMetadata.properties && typeof svsMetadata.properties === 'object') {
        for (const [k, v] of Object.entries(svsMetadata.properties)) {
          metadataHTML += `<p><strong>${k}:</strong> ${v}</p>`;
        }
      }
  
      document.getElementById('metadata-container').style.display = 'block';
      document.getElementById('metadata-content').innerHTML = metadataHTML;
    } catch (err) {
      console.error("Error loading SVS metadata:", err);
    }
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
  
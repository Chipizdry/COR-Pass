


// filename: doctor_registration.js
// Final cleaned & fixed version for doctor registration
// - Single initialization of event listeners
// - Files stored in registrationFiles and restored between modal steps
// - Safe null checks (no Uncaught TypeError: Cannot set properties of null)
// - submitForm uses registrationFiles
// - exportFormToPDF uses addFileToVFS/addFont (no dependency on external JsPdf_Custom_Fonts)
// - initImageDragAndZoom uses explicit options for wheel listener

/* ========== Глобальное хранилище файлов ========== */
const registrationFiles = {
    photo: null,
    military_document: null,
    diplomaFile: null,
    certificateFile: null
  };
  
  /* ========== DOMContentLoaded: инициализация один раз ========== */
  document.addEventListener('DOMContentLoaded', () => {
    // Инициализация интерфейса
    navigateToStep(1);
    autoFillStep1Fields();
  
    // Навигация
    document.querySelectorAll('[data-translate="back-link-text"]').forEach(btn => {
      btn.addEventListener('click', goBack);
    });
    document.querySelectorAll('[data-translate="forward-link-text"]').forEach(btn => {
      btn.addEventListener('click', goForward);
    });
  
    // Drag modal initial
    makeModalDraggable('step1Modal');
  
    // Инициализация input[type=file] один раз
    initFileInput('fileInput', null, 'photo', true, 'previewImage', 'placeholder');
    initFileInput('military_document', 'militaryFileName', 'military_document');
    initFileInput('diplomaFile', 'fileName', 'diplomaFile');
    initFileInput('certificateFile', 'certificateFileName', 'certificateFile');
  
    // Лог прикрепления (дополнительно)
    ['fileInput', 'military_document', 'diplomaFile', 'certificateFile'].forEach(id => {
      const input = document.getElementById(id);
      if (input) {
        input.addEventListener('change', e => {
          const file = e.target.files ? e.target.files[0] : null;
          console.log(file ? `📎 Файл выбран [${id}]: ${file.name}` : `📎 Файл снят [${id}]`);
        });
      }
    });
  
    // Назначаем кнопку отправки (если есть)
    const submitButton = document.getElementById('submitButton');
    if (submitButton) submitButton.addEventListener('click', submitForm);
  
    // Кнопка Preview PDF
    const previewBtn = document.getElementById('exportPdfButton');
    if (previewBtn) previewBtn.addEventListener('click', exportFormToPDF);
  });
  
  /* ========== Универсальная инициализация file inputs ==========
     inputId    - id input[type=file]
     labelId    - id element для показа имени файла (может быть null)
     fileKey    - ключ в registrationFiles
     isImage    - если true — читаем previewId
     previewId  - id img для превью
     placeholderId - id placeholder svg
  =========================================================== */
  function initFileInput(inputId, labelId, fileKey, isImage = false, previewId = null, placeholderId = null) {
    const input = document.getElementById(inputId);
    const label = labelId ? document.getElementById(labelId) : null;
    const preview = previewId ? document.getElementById(previewId) : null;
    const placeholder = placeholderId ? document.getElementById(placeholderId) : null;
  
    if (!input) return;
  
    // Если файл уже в registrationFiles (например при перезагрузке скрипта),
    // покажем имя/превью:
    if (registrationFiles[fileKey]) {
      if (label) {
        label.textContent = registrationFiles[fileKey].name;
        label.style.color = '#7f69bd';
      }
      if (isImage && preview && placeholder) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          preview.src = ev.target.result;
          preview.style.display = 'block';
          placeholder.style.display = 'none';
          initImageDragAndZoom(preview);
        };
        reader.readAsDataURL(registrationFiles[fileKey]);
      }
    }
  
    input.addEventListener('change', (e) => {
      const file = e.target.files ? e.target.files[0] : null;
      registrationFiles[fileKey] = file || null;
  
      if (label) {
        if (file) {
          label.textContent = file.name;
          label.style.color = '#7f69bd';
        } else {
          label.textContent = 'Файл не выбран';
          label.style.color = '#888';
        }
      }
  
      if (isImage && preview && placeholder) {
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            preview.src = ev.target.result;
            preview.style.display = 'block';
            placeholder.style.display = 'none';
            initImageDragAndZoom(preview);
          };
          reader.readAsDataURL(file);
        } else {
          preview.style.display = 'none';
          if (placeholder) placeholder.style.display = 'block';
        }
      }
    });
  }
  
  /* ========== Навигация между шагами (модалками) ========== */
  function navigateToStep(targetStep) {
    if (!checkToken()) return;
  
    // Скрываем все модалки
    document.querySelectorAll('.modal').forEach(modal => modal.style.display = 'none');
  
    const targetModal = document.getElementById(`step${targetStep}Modal`);
    if (!targetModal) {
      console.error(`Модальное окно step${targetStep}Modal не найдено`);
      return;
    }
  
    targetModal.style.display = 'block';
    makeModalDraggable(`step${targetStep}Modal`);
    updateProgressBar(targetStep);
  
    // Восстанавливаем подписи/превью (с guard-ами)
    if (targetStep === 1 && registrationFiles.photo) {
      const img = document.getElementById('previewImage');
      const placeholder = document.getElementById('placeholder');
      if (img && placeholder) {
        const reader = new FileReader();
        reader.onload = e => {
          img.src = e.target.result;
          img.style.display = 'block';
          placeholder.style.display = 'none';
          initImageDragAndZoom(img);
        };
        reader.readAsDataURL(registrationFiles.photo);
      }
    }
  
    if (targetStep === 2 && registrationFiles.military_document) {
      const lbl = document.getElementById('militaryFileName');
      if (lbl) {
        lbl.textContent = registrationFiles.military_document.name;
        lbl.style.color = '#7f69bd';
      }
    }
  
    if (targetStep === 3) {
        console.log("🔁 Восстановление данных шага 3");
        const fields = ['Clinick_Name', 'Department', 'Job_title', 'specialization', 'degree', 'birthdate'];
        fields.forEach(id => {
          const el = document.getElementById(id);
          if (el && el.value) {
            el.style.borderColor = '#f0f0f0';
          }
        });
      }

    if (targetStep === 4 && registrationFiles.diplomaFile) {
      const lbl = document.getElementById('fileName');
      if (lbl) {
        lbl.textContent = registrationFiles.diplomaFile.name;
        lbl.style.color = '#7f69bd';
      }
    }
  
    if (targetStep === 5 && registrationFiles.certificateFile) {
      const lbl = document.getElementById('certificateFileName');
      if (lbl) {
        lbl.textContent = registrationFiles.certificateFile.name;
        lbl.style.color = '#7f69bd';
      }
    }
  }
  
  /* ========== Получение текущего шага ========= */
  function getCurrentStep() {
    const visibleModal = Array.from(document.querySelectorAll('.modal')).find(m => {
      // смотрим computed style на display block
      return window.getComputedStyle(m).display === 'block';
    });
    if (visibleModal) {
      const match = visibleModal.id.match(/step(\d)Modal/);
      return match ? parseInt(match[1], 10) : 1;
    }
    return 1;
  }
  
  /* ========== Навигация - кнопки ========= */
  function goBack() {
    const currentStep = getCurrentStep();
    if (currentStep > 1) {
      navigateToStep(currentStep - 1);
    } else {
      window.history.back();
    }
  }
  
  function goForward() {
    const currentStep = getCurrentStep();
    if (currentStep < 5) {
      if (validateCurrentStep(currentStep)) {
        navigateToStep(currentStep + 1);
      }
    } else {
      submitForm();
    }
  }
  
  /* ========== Валидации по шагам (можно расширять) ========== */
  function validateCurrentStep(step) {
    switch (step) {
      case 1: return validateStep1();
      case 2: return validateStep2();
      case 3: return validateStep3();
      case 4: return validateStep4();
      case 5: return validateStep5();
      default: return true;
    }
  }
  
  function validateStep1() {
    const required = ['lastName', 'firstName', 'workEmail'];
    let ok = true;
    required.forEach(id => {
      const el = document.getElementById(id);
      if (!el || !el.value.trim()) {
        ok = false;
        if (el) el.style.borderColor = 'red';
      } else {
        if (el) el.style.borderColor = '#f0f0f0';
      }
    });
    if (!ok) alert('Пожалуйста, заполните все обязательные поля');
    return ok;
  }
  
  function validateStep2() {
  console.log("=== ВАЛИДАЦИЯ STEP2 ЗАПУЩЕНА ===");
  let ok = true;

  const required = ['Passport_serial_number', 'Tax_Number', 'Addres'];
  required.forEach(id => {
    const el = document.getElementById(id);
    if (!el || !el.value.trim()) {
      ok = false;
      if (el) el.style.borderColor = 'red';
    } else {
      el.style.borderColor = '#f0f0f0';
    }
  });

  // Проверка военного документа
  const militaryFileInput = document.getElementById('military_document');
  const label = document.getElementById('fileName');
  const hasFile = registrationFiles && registrationFiles.military_document;

  if (!hasFile) {
    ok = false;
    if (label) {
      label.textContent = 'Файл не выбран!';
      label.style.color = 'red';
    }
  } else {
    if (label) label.style.color = '#7f69bd';
  }

  // Проверка формата серии паспорта — только цифры или буквы латиницы/кириллицы
  const passportEl = document.getElementById('Passport_serial_number');
  if (passportEl && passportEl.value.trim() && !/^[A-Za-zА-Яа-я0-9\s-]+$/.test(passportEl.value.trim())) {
    ok = false;
    passportEl.style.borderColor = 'red';
    alert('Серия и номер паспорта могут содержать только буквы, цифры и дефис');
  }

  // Проверка ИНН — только цифры, длина 10–12 символов
  const taxEl = document.getElementById('Tax_Number');
  if (taxEl && taxEl.value.trim() && !/^\d{10,12}$/.test(taxEl.value.trim())) {
    ok = false;
    taxEl.style.borderColor = 'red';
    alert('ИНН должен содержать 10–12 цифр');
  }

  if (!ok) alert('Пожалуйста, заполните все обязательные поля корректно');
  return ok;
}


  
  function validateStep3() {
    const fields = ['Clinick_Name', 'Department', 'Job_title', 'specialization', 'degree', 'birthdate'];
    let ok = true;
  
    fields.forEach(id => {
      const el = document.getElementById(id);
      if (!el) {
        ok = false;
        return;
      }
      if (el.tagName === 'SELECT') {
        if (!el.value) { ok = false; el.style.borderColor = 'red'; } else el.style.borderColor = '#f0f0f0';
      } else if (!el.value.trim()) {
        ok = false; el.style.borderColor = 'red';
      } else el.style.borderColor = '#f0f0f0';
    });
  
    const birthdate = document.getElementById('birthdate');
    if (birthdate && birthdate.value) {
      const sel = new Date(birthdate.value), now = new Date();
      if (sel > now) { ok = false; birthdate.style.borderColor = 'red'; alert('Дата аттестации не может быть в будущем'); }
    }
  
    if (!ok) alert('Пожалуйста, заполните все обязательные поля корректно');
    return ok;
  }
  
  function validateStep4() {
    console.log("=== ВАЛИДАЦИЯ STEP4 ЗАПУЩЕНА ===");
    let isValid = true;
  
    // Проверяем текстовые поля
    const textFields = ['date_id', 'Serial_number', 'Number', 'University'];
    textFields.forEach(id => {
      const el = document.getElementById(id);
      if (!el || !el.value.trim()) { isValid = false; if (el) el.style.borderColor = 'red'; }
      else el.style.borderColor = '#f0f0f0';
    });
  
    // Проверим, что файл диплома есть в registrationFiles (а не в DOM)
    if (!registrationFiles.diplomaFile) {
      isValid = false;
      const label = document.getElementById('fileName');
      if (label) { label.textContent = 'Файл не выбран!'; label.style.color = 'red'; }
    }
  
    // Серия/номер только цифры
    const serial = document.getElementById('Serial_number');
    const number = document.getElementById('Number');
    if (serial && serial.value.trim() && !/^\d+$/.test(serial.value.trim())) { isValid = false; serial.style.borderColor = 'red'; alert('Серия должна содержать только цифры'); }
    if (number && number.value.trim() && !/^\d+$/.test(number.value.trim())) { isValid = false; number.style.borderColor = 'red'; alert('Номер должен содержать только цифры'); }
  
    if (!isValid) alert('Пожалуйста, заполните все обязательные поля корректно');
    return isValid;
  }
  
  function validateStep5() {
    let ok = true;
    // Проверяем поля сертификата: дата, серия, номер, вуз и файл в registrationFiles
    const required = ['date_id', 'Serial_number', 'Number', 'University'];
    required.forEach(id => {
      const el = document.getElementById(id);
      if (!el || !el.value.trim()) { ok = false; if (el) el.style.borderColor = 'red'; } else el.style.borderColor = '#f0f0f0';
    });
  
    if (!registrationFiles.certificateFile) {
      ok = false;
      const label = document.getElementById('certificateFileName');
      if (label) label.style.color = 'red';
    }
  
    if (!ok) alert('Пожалуйста, заполните все обязательные поля корректно');
    return ok;
  }
  
  /* ========== Отправка формы (использует registrationFiles) ========== */
  async function submitForm() {
    try {
      const { photo, military_document, diplomaFile, certificateFile } = registrationFiles;
  
      const doctorData = {
        work_email: (document.getElementById('workEmail')?.value) || '',
        first_name: (document.getElementById('firstName')?.value) || '',
        surname: (document.getElementById('lastName')?.value) || '',
        last_name: (document.getElementById('middleName')?.value) || null,
        scientific_degree: (document.getElementById('degree')?.value) || '',
        date_of_last_attestation: (document.getElementById('birthdate')?.value) || '',
        diplomas: [{
          date: (document.getElementById('date_id')?.value) || '',
          series: (document.getElementById('Serial_number')?.value) || '',
          number: (document.getElementById('Number')?.value) || '',
          university: (document.getElementById('University')?.value) || ''
        }],
        certificates: [{
          date: (document.getElementById('date_id')?.value) || '',
          series: (document.getElementById('Serial_number')?.value) || '',
          number: (document.getElementById('Number')?.value) || '',
          university: (document.getElementById('University')?.value) || ''
        }],
        clinic_affiliations: [{
          clinic_name: (document.getElementById('Clinick_Name')?.value) || '',
          department: (document.getElementById('Department')?.value) || '',
          position: (document.getElementById('Job_title')?.value) || '',
          specialty: (document.getElementById('specialization')?.value) || ''
        }]
      };
  
      const formData = new FormData();
      formData.append('doctor_data', JSON.stringify(doctorData));
      if (photo) formData.append('doctors_photo', photo);
      if (military_document) formData.append('military_document', military_document);
      if (diplomaFile) formData.append('diploma_scan', diplomaFile);
      if (certificateFile) formData.append('certificate_scan', certificateFile);
  
      const token = new URLSearchParams(window.location.search).get('access_token');
  
      const res = await fetch('/api/doctor/signup', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
  
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Ошибка сервера при отправке формы');
      }
  
      const result = await res.json().catch(() => ({}));
      console.log('✅ Успешная регистрация:', result);
      alert('Регистрация успешно завершена! Ожидайте подтверждения.');
      window.location.href = '/registration_success.html';
    } catch (err) {
      console.error('Ошибка при отправке формы:', err);
      alert(`Ошибка: ${err.message}`);
    }
  }
  
  /* ========== Экспорт в PDF (jsPDF) ==========
     Этот код НЕ зависит от внешнего JsPdf_Custom_Fonts.js.
     Если у тебя раньше была ошибка TTFFont undefined — удаляй/ закомментируй подключение
     JsPdf_Custom_Fonts.js в HTML (рекомендация).
  ================================================= */
  async function exportFormToPDF() {
    try {
      if (!window.jspdf || !window.jspdf.jsPDF) {
        alert('jsPDF не найден. Убедитесь, что jsPDF подключён.');
        return;
      }
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  
      // Пытаемся загрузить шрифт Roboto (если доступен на сервере)
      try {
        const fontUrl = '/static/fonts/Roboto-Regular.ttf';
        const fontResp = await fetch(fontUrl);
        if (fontResp.ok) {
          const ab = await fontResp.arrayBuffer();
          const b64 = arrayBufferToBase64(ab);
          // Добавляем шрифт в VFS и регистрируем
          if (typeof doc.addFileToVFS === 'function' && typeof doc.addFont === 'function') {
            doc.addFileToVFS('Roboto-Regular.ttf', b64);
            doc.addFont('Roboto-Regular.ttf', 'Roboto', 'normal');
            doc.setFont('Roboto');
          }
        } else {
          // fallback - оставляем helvetica
          doc.setFont('helvetica');
        }
      } catch (e) {
        console.warn('Не удалось загрузить кастомный шрифт, используем fallback', e);
        doc.setFont('helvetica');
      }
  
      const getField = id => document.getElementById(id)?.value || '';
  
      // Данные
      const personalData = {
        "Фамилия": getField("lastName"),
        "Имя": getField("firstName"),
        "Отчество": getField("middleName"),
        "Год рождения": getField("birthYear"),
        "Пол": getField("gender"),
        "Телефон": getField("Phone_number"),
        "Рабочий email": getField("workEmail")
      };
  
      const workData = {
        "Название клиники": getField("Clinick_Name"),
        "Отделение": getField("Department"),
        "Должность": getField("Job_title"),
        "Специализация": getField("specialization"),
        "Научная степень": getField("degree"),
        "Дата последней аттестации": getField("birthdate")
      };
  
      const diplomaData = {
        "Дата выдачи": getField("date_id"),
        "Серия": getField("Serial_number"),
        "Номер": getField("Number"),
        "ВУЗ": getField("University")
      };
  
      let y = 20;
      doc.setFontSize(16);
      doc.setTextColor('#5B4296');
      doc.text("Регистрационная карта врача", 105, y, { align: 'center' });
      y += 10;
  
      // Личные данные
      doc.setFontSize(14);
      doc.setTextColor('#5B4296');
      doc.text("Личные данные", 15, y);
      y += 8;
      doc.setFontSize(12);
      doc.setTextColor('#323238');
  
      // Добавляем фото из registrationFiles, если есть
      if (registrationFiles.photo) {
        // Конвертируем в DataURL
        const dataUrl = await fileToDataUrl(registrationFiles.photo);
        // Подгоняем размеры
        const img = new Image();
        img.src = dataUrl;
        await waitImageLoad(img);
        let iw = img.width, ih = img.height;
        const maxW = 40, maxH = 40;
        if (iw > maxW) { ih = (maxW / iw) * ih; iw = maxW; }
        if (ih > maxH) { iw = (maxH / ih) * iw; ih = maxH; }
        try {
          doc.addImage(img, 'JPEG', 150, y - 15, iw, ih);
        } catch (e) {
          // Попытка как PNG
          doc.addImage(img, 'PNG', 150, y - 15, iw, ih);
        }
      }
  
      for (const [label, value] of Object.entries(personalData)) {
        doc.setTextColor('#323238');
        doc.text(`${label}:`, 15, y);
        doc.setTextColor('#000000');
        y = addTextWithLineBreaks(doc, value, 40, y, 100, 6);
      }
  
      if (y > 250) { doc.addPage(); y = 20; } else y += 10;
  
      // Профессиональные данные
      doc.setFontSize(14);
      doc.setTextColor('#5B4296');
      doc.text("Профессиональные данные", 15, y);
      y += 8;
      doc.setFontSize(12);
      for (const [label, value] of Object.entries(workData)) {
        doc.text(`${label}:`, 15, y);
        y = addTextWithLineBreaks(doc, value, 50, y, 140, 6);
      }
  
      if (y > 250) { doc.addPage(); y = 20; } else y += 10;
  
      // Данные диплома
      doc.setFontSize(14);
      doc.setTextColor('#5B4296');
      doc.text("Данные диплома", 15, y);
      y += 8;
      doc.setFontSize(12);
      for (const [label, value] of Object.entries(diplomaData)) {
        doc.text(`${label}:`, 15, y);
        y = addTextWithLineBreaks(doc, value, 40, y, 150, 6);
      }
  
      if (registrationFiles.diplomaFile) {
        doc.text("Файл диплома:", 15, y);
        y = addTextWithLineBreaks(doc, registrationFiles.diplomaFile.name, 40, y, 150, 6);
      }
  
      if (y > 250) { doc.addPage(); y = 20; } else y += 10;
  
      // Сертификат
      doc.setFontSize(14);
      doc.setTextColor('#5B4296');
      doc.text("Сертификат специалиста", 15, y);
      y += 8;
      if (registrationFiles.certificateFile) {
        doc.setFontSize(12);
        doc.text("Файл сертификата:", 15, y);
        y = addTextWithLineBreaks(doc, registrationFiles.certificateFile.name, 50, y, 140, 6);
      }
  
      if (y > 200) { doc.addPage(); y = 20; } else y = 250;
      doc.setFontSize(12);
      doc.text("Дата заполнения: " + new Date().toLocaleDateString(), 15, y);
      y += 10;
      doc.text("Подпись: ___________________", 15, y);
  
      doc.save("Регистрационная_карта_врача.pdf");
    } catch (err) {
      console.error('Ошибка экспорта PDF:', err);
      alert('Не удалось сформировать PDF: ' + (err.message || err));
    }
  }
  
  /* ========== Помощники для PDF ========== */
  function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      const slice = bytes.subarray(i, i + chunk);
      binary += String.fromCharCode.apply(null, slice);
    }
    return btoa(binary);
  }
  
  function addTextWithLineBreaks(doc, text, x, y, maxWidth, lineHeight = 5) {
    const lines = doc.splitTextToSize(text || '', maxWidth);
    doc.text(lines, x, y);
    return y + (lines.length * lineHeight);
  }
  
  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
  
  function waitImageLoad(img) {
    return new Promise(res => {
      if (img.complete && img.naturalWidth !== 0) return res();
      img.onload = () => res();
      img.onerror = () => res();
    });
  }
  
  /* ========== Автозаполнение данных (localStorage) ========== */
  function autoFillStep1Fields() {
    console.log("Автозаполнение полей шага 1...");
    const gender = localStorage.getItem('userGender');
    const birthYear = localStorage.getItem('userBirthYear');
  
    const genderInput = document.getElementById('gender');
    if (genderInput && gender) {
      genderInput.value = (gender === 'M') ? 'Мужской' : 'Женский';
    }
  
    const birthYearInput = document.getElementById('birthYear');
    if (birthYearInput && birthYear) birthYearInput.value = birthYear;
  }
  
  /* ========== Логирование данных формы по шагам ========== */
  function logStepData(step) {
    let data = {};
    switch (step) {
      case 1:
        data = {
          lastName: document.getElementById('lastName')?.value,
          firstName: document.getElementById('firstName')?.value,
          middleName: document.getElementById('middleName')?.value,
          workEmail: document.getElementById('workEmail')?.value
        };
        break;
      case 2:
        data = { militaryFile: registrationFiles.military_document?.name || '—' };
        break;
      case 3:
        data = {
          Clinick_Name: document.getElementById('Clinick_Name')?.value,
          Department: document.getElementById('Department')?.value,
          Job_title: document.getElementById('Job_title')?.value,
          specialization: document.getElementById('specialization')?.value,
          degree: document.getElementById('degree')?.value,
          birthdate: document.getElementById('birthdate')?.value
        };
        break;
      case 4:
        data = {
          diplomaFile: registrationFiles.diplomaFile?.name || '—',
          date_id: document.getElementById('date_id')?.value,
          Serial_number: document.getElementById('Serial_number')?.value,
          Number: document.getElementById('Number')?.value,
          University: document.getElementById('University')?.value
        };
        break;
      case 5:
        data = {
          certificateFile: registrationFiles.certificateFile?.name || '—',
          date_id: document.getElementById('date_id')?.value,
          Serial_number: document.getElementById('Serial_number')?.value,
          Number: document.getElementById('Number')?.value,
          University: document.getElementById('University')?.value
        };
        break;
    }
    console.log(`📋 Данные шага ${step}:`, data);
  }
  
  /* ========== Оборачиваем navigateToStep для логов ========== */
  (function wrapNavigateForLogging() {
    const originalNavigate = navigateToStep;
    navigateToStep = function (targetStep) {
      const currentStep = getCurrentStep();
      console.log(`➡️ Переход: шаг ${currentStep} → ${targetStep}`);
      if (currentStep) logStepData(currentStep);
      originalNavigate(targetStep);
    };
  })();
  
  /* ========== Image drag & zoom (single init per image instance) ========== */
  function initImageDragAndZoom(img) {
    if (!img) return;
    // не навешиваем дублирующиеся обработчики
    if (img.__dragZoomInitialized) return;
    img.__dragZoomInitialized = true;
  
    let isDragging = false;
    let startX = 0, startY = 0, translateX = 0, translateY = 0, scale = 1;
  
    img.style.cursor = 'grab';
    img.addEventListener('mousedown', function (e) {
      isDragging = true;
      startX = e.clientX - translateX;
      startY = e.clientY - translateY;
      img.style.cursor = 'grabbing';
      e.stopPropagation();
    });
  
    window.addEventListener('mousemove', function (e) {
      if (isDragging) {
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
      }
    });
  
    window.addEventListener('mouseup', function () {
      isDragging = false;
      img.style.cursor = 'grab';
    });
  
    // wheel: explicit passive: false because we call preventDefault
    img.addEventListener('wheel', function (e) {
      e.preventDefault();
      scale *= e.deltaY < 0 ? 1.1 : 0.9;
      img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
      e.stopPropagation();
    }, { passive: false });
  }
  
  /* ========== Обновление прогресс бара ========== */
  function updateProgressBar(currentStep) {
    const visibleModal = Array.from(document.querySelectorAll('.modal')).find(m => window.getComputedStyle(m).display === 'block');
    if (!visibleModal) return;
    const progressBar = visibleModal.querySelector('.progress-bar');
    if (!progressBar) return;
    const steps = progressBar.querySelectorAll('.progress-step');
    steps.forEach((step, index) => {
      if ((index + 1) <= currentStep) step.classList.add('active'); else step.classList.remove('active');
    });
  }
  
  
  



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


// Валидация email
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

// Валидация телефона
function isValidPhone(phone) {
  const re = /^[+]?\d{6,13}$/;
  return re.test(phone);
}



// Отправка базовых данных врача
async function sendDoctorBasic() {
  const token = localStorage.getItem('accessToken'); // если используется авторизация
  const url = '/api/doctor/v1/signup-doctor-basic';

  const doctorData = {
      work_email: document.getElementById('workEmail').value.trim(),
      phone_number: document.getElementById('Phone_number').value.trim(),
      first_name: document.getElementById('firstName').value.trim(),
      middle_name: document.getElementById('middleName').value.trim(),
      last_name: document.getElementById('lastName').value.trim(),
      passport_code: document.getElementById('Passport_serial_number').value.trim(),
      taxpayer_identification_number: document.getElementById('Tax_Number').value.trim(),
      place_of_registration: document.getElementById('Addres').value.trim(),
      scientific_degree: document.getElementById('Degree')?.value.trim() || '',
      date_of_last_attestation: document.getElementById('attestationDate')?.value || new Date().toISOString().split('T')[0]
  };

  try {
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              ...(token && { 'Authorization': `Bearer ${token}` })
          },
          body: JSON.stringify(doctorData)
      });

      if (!response.ok) {
          const errorData = await response.json();
          console.error('Ошибка при создании врача:', errorData);
          alert('Ошибка: ' + (errorData.detail?.[0]?.msg || response.statusText));
          return;
      }

      const result = await response.json();
      console.log('✅ Врач успешно создан:', result);
      alert('Данные успешно сохранены!');
      return result;

  } catch (err) {
      console.error('Ошибка сети или сервера:', err);
      alert('Не удалось отправить данные. Проверьте подключение к сети.');
  }
}




function validateAllSteps() {
  for (let i = 1; i <= 5; i++) {
    if (!validateStep(i)) {
      alert(`Исправьте ошибки на шаге ${i}`);
      showModal(i);
      return false;
    }
  }
  return true;
}




// Главная функция отправки формы
async function submitForm() {
  console.log("Нажата кнопка 'Отправить'");

  // 1. Проверяем все шаги
  if (!validateAllSteps()) {
      console.warn("Валидация не пройдена");
      return;
  }

  // 2. Проверяем, что все обязательные файлы загружены
  const requiredFiles = [
      { id: 'fileInput', name: 'Фото' },
      { id: 'military_document', name: 'Военно-учётный документ' },
      { id: 'diploma_file', name: 'Диплом' },
      { id: 'certificateFile', name: 'Сертификат специалиста' }
  ];

  for (const file of requiredFiles) {
      const input = document.getElementById(file.id);
      if (!input || input.files.length === 0) {
          alert(`Пожалуйста, загрузите файл: ${file.name}`);
          return;
      }
  }

  // 3. Если всё ок — вызываем API
  try {
      const result = await sendDoctorBasic();

      if (result && result.id) {
          alert('✅ Регистрация успешно завершена!');
          console.log('Созданный врач:', result);
      } else {
          alert('⚠ Не удалось подтвердить регистрацию. Проверьте данные.');
      }

  } catch (error) {
      console.error('Ошибка при отправке:', error);
      alert('Произошла ошибка при отправке данных.');
  }
}



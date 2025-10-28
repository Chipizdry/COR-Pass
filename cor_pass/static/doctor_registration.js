




      
       document.addEventListener('DOMContentLoaded', function () {

        // Показываем первый шаг
         navigateToStep(1);
       
       // Назначаем обработчики для кнопок навигации
       document.querySelectorAll('[data-translate="back-link-text"]').forEach(btn => {
           btn.onclick = goBack;
       });
       
       document.querySelectorAll('[data-translate="forward-link-text"]').forEach(btn => {
           btn.onclick = goForward;
       });
   
      makeModalDraggable('step1Modal');})
   
   
   document.getElementById('fileInput').addEventListener('change', function(event) {
       const file = event.target.files[0];
       if (file) {
           const reader = new FileReader();
           reader.onload = function(e) {
               const img = document.getElementById('previewImage');
               const placeholder = document.getElementById('placeholder');
   
               img.src = e.target.result;
               img.style.display = 'block';
               placeholder.style.display = 'none';
   
               initImageDragAndZoom(img);
           };
           reader.readAsDataURL(file);
       } else {
           // Если файл не выбран, показываем SVG-заглушку
           const img = document.getElementById('previewImage');
           const placeholder = document.getElementById('placeholder');
   
           img.style.display = 'none';
           placeholder.style.display = 'block';
       }
   });
   
   function initImageDragAndZoom(img) {
       let isDragging = false;
       let startX, startY, translateX = 0, translateY = 0;
       let scale = 1;
   
       img.addEventListener('mousedown', function(e) {
           isDragging = true;
           startX = e.clientX - translateX;
           startY = e.clientY - translateY;
           img.style.cursor = 'grabbing';
           e.stopPropagation(); // Останавливаем всплытие события
       });
   
       window.addEventListener('mousemove', function(e) {
           if (isDragging) {
               translateX = e.clientX - startX;
               translateY = e.clientY - startY;
               img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
           }
       });
   
       window.addEventListener('mouseup', function(e) {
           isDragging = false;
           img.style.cursor = 'grab';
           e.stopPropagation(); // Останавливаем всплытие события
       });
   
       img.addEventListener('wheel', function(e) {
           e.preventDefault();
           if (e.deltaY < 0) {
               scale *= 1.1; // Увеличение масштаба
           } else {
               scale /= 1.1; // Уменьшение масштаба
           }
           img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
           e.stopPropagation(); // Останавливаем всплытие события
       });
   }
   
   // Функция для отправки формы
   function submitForm() {
       // Собираем данные со всех шагов
       const formData = {};
       for (let i = 1; i <= 4; i++) {
           const stepData = localStorage.getItem(`step${i}Data`);
           if (stepData) {
               Object.assign(formData, JSON.parse(stepData));
           }
       }
       
       // Здесь можно отправить данные на сервер
       console.log('Все данные формы:', formData);
       alert('Форма успешно отправлена!');
       
       // Очищаем localStorage
       for (let i = 1; i <= 4; i++) {
           localStorage.removeItem(`step${i}Data`);
       }
   }
   
   
   // Функция для перехода на предыдущий шаг
   function goBack() {
       const currentStep = getCurrentStep();
       if (currentStep > 1) {
         //  saveFormData(currentStep); // Сохраняем данные текущего шага
           navigateToStep(currentStep - 1);
       } else {
           // Если это первый шаг, возвращаемся на предыдущую страницу
           window.history.back();
       }
   }
   
   // Функция для перехода на следующий шаг
   function goForward() {
       const currentStep = getCurrentStep();
       if (currentStep < 4) { // Предполагаем, что у нас 4 шага
           if (validateCurrentStep(currentStep)) {
           //    saveFormData(currentStep);
               navigateToStep(currentStep + 1);
           }
       } else {
           // Если это последний шаг, отправляем форму
           submitForm();
       }
   }
   
   // Функция для перехода между шагами
   function navigateToStep(targetStep) {
   
       if( checkToken()){
       // Скрываем все модальные окна
       document.querySelectorAll('.modal').forEach(modal => {
           modal.style.display = 'none';
       });
       
       // Показываем целевое модальное окно
       const targetModal = document.getElementById(`step${targetStep}Modal`);
       if (targetModal) {
           targetModal.style.display = 'block';
           makeModalDraggable(`step${targetStep}Modal`);
       } else {
           console.error(`Модальное окно step${targetStep}Modal не найдено`);
       }
       
       // Обновляем прогресс-бар
       updateProgressBar(targetStep);}
   }
   
   // Функция для получения текущего шага
   function getCurrentStep() {
       const visibleModal = document.querySelector('.modal[style*="display: block"]');
       if (visibleModal) {
           const match = visibleModal.id.match(/step(\d)Modal/);
           return match ? parseInt(match[1]) : 1;
       }
       return 1;
   }
   
   // Функция для валидации текущего шага
   function validateCurrentStep(step) {
       // Здесь можно добавить валидацию для каждого шага
       switch(step) {
           case 1:
               // Валидация для первого шага
               return validateStep1();
           case 2:
               // Валидация для второго шага
               return validateStep2();
           case 3:
               // Валидация для второго шага
               return validateStep3();
           case 4:
               // Валидация для второго шага
               return validateStep4();
           // Добавьте другие шаги по необходимости
           default:
               return true;
       }
   }
   
   
   
   // Пример функции валидации для шага 1
   function validateStep1() {
       const requiredFields = ['lastName', 'firstName', 'workEmail'];
       let isValid = true;
       
       requiredFields.forEach(fieldId => {
           const field = document.getElementById(fieldId);
           if (!field || !field.value.trim()) {
               isValid = false;
               field.style.borderColor = 'red';
           } else {
               field.style.borderColor = '#f0f0f0';
           }
       });
       
       if (!isValid) {
           alert('Пожалуйста, заполните все обязательные поля');
       }
       
       return isValid;
   }
   
   
   function validateStep2() {
       const requiredFields = ['Clinick_Name', 'Department', 'Job_title', 'specialization', 'degree', 'birthdate'];
       let isValid = true;
       
       requiredFields.forEach(fieldId => {
           const field = document.getElementById(fieldId);
           
           // Для select проверяем, что выбран не пустой option
           if (field.tagName === 'SELECT') {
               if (!field.value) {
                   isValid = false;
                   field.style.borderColor = 'red';
               } else {
                   field.style.borderColor = '#f0f0f0';
               }
           } 
           // Для input проверяем, что поле не пустое
           else if (!field.value.trim()) {
               isValid = false;
               field.style.borderColor = 'red';
           } else {
               field.style.borderColor = '#f0f0f0';
           }
       });
       
       // Дополнительная проверка для даты (если нужно)
       const birthdate = document.getElementById('birthdate');
       if (birthdate.value) {
           const selectedDate = new Date(birthdate.value);
           const currentDate = new Date();
           
           // Проверка, что дата не в будущем (если требуется)
           if (selectedDate > currentDate) {
               isValid = false;
               birthdate.style.borderColor = 'red';
               alert('Дата аттестации не может быть в будущем');
           }
       }
       
       if (!isValid) {
           alert('Пожалуйста, заполните все обязательные поля корректно');
       }
       
       return isValid;
   }
   
   function validateStep3() {
       const requiredFields = ['diplomaFile', 'date_id', 'Serial_number', 'Number', 'University'];
       let isValid = true;
       
       requiredFields.forEach(fieldId => {
           const field = document.getElementById(fieldId);
           
           // Для input type="file" проверяем, что файл выбран
           if (field.type === 'file') {
               if (!field.files || field.files.length === 0) {
                   isValid = false;
                   // Подсвечиваем текст "Файл не выбран" красным
                   const fileNameElement = document.getElementById('fileName');
                   fileNameElement.style.color = 'red';
               } else {
                   // Возвращаем стандартный цвет, если файл выбран
                   const fileNameElement = document.getElementById('fileName');
                   fileNameElement.style.color = '#7f69bd';
               }
           } 
           // Для input type="date" проверяем, что дата выбрана
           else if (field.type === 'date') {
               if (!field.value) {
                   isValid = false;
                   field.style.borderColor = 'red';
               } else {
                   field.style.borderColor = '#f0f0f0';
                   
                   // Дополнительная проверка даты (не в будущем)
                   const selectedDate = new Date(field.value);
                   const currentDate = new Date();
                   
                   if (selectedDate > currentDate) {
                       isValid = false;
                       field.style.borderColor = 'red';
                       alert('Дата выдачи не может быть в будущем');
                   }
               }
           }
           // Для остальных input проверяем, что поле не пустое
           else if (!field.value.trim()) {
               isValid = false;
               field.style.borderColor = 'red';
           } else {
               field.style.borderColor = '#f0f0f0';
           }
       });
       
       // Дополнительная проверка для серии и номера (только цифры)
       const serialNumber = document.getElementById('Serial_number');
       const number = document.getElementById('Number');
       
       if (serialNumber.value && !/^\d+$/.test(serialNumber.value)) {
           isValid = false;
           serialNumber.style.borderColor = 'red';
           alert('Серия должна содержать только цифры');
       }
       
       if (number.value && !/^\d+$/.test(number.value)) {
           isValid = false;
           number.style.borderColor = 'red';
           alert('Номер должен содержать только цифры');
       }
       
       if (!isValid) {
           alert('Пожалуйста, заполните все обязательные поля корректно');
       }
       
       return isValid;
   } 
   
   function validateStep4() {
      
       const requiredFields = ['certificateFile', 'date_id', 'Serial_number', 'Number', 'University'];
       let isValid = true;
       
       requiredFields.forEach(fieldId => {
           const field = document.getElementById(fieldId);
           
           if (field.type === 'file') {
               if (!field.files || field.files.length === 0) {
                   isValid = false;
                   const fileNameElement = document.getElementById('fileName');
                   fileNameElement.style.color = 'red';
               }
           } 
           else if (field.type === 'date' && !field.value) {
               isValid = false;
               field.style.borderColor = 'red';
           }
           else if (!field.value.trim()) {
               isValid = false;
               field.style.borderColor = 'red';
           } else {
               field.style.borderColor = '#f0f0f0';
           }
       });
       
       if (!isValid) {
           alert('Пожалуйста, заполните все обязательные поля корректно');
       }
       
       return isValid;
   }
   
   
   // Функция для отправки формы
   async function submitForm() {
       try {
           const photoFile = document.getElementById('fileInput').files[0];
           const diplomaFile = document.getElementById('diplomaFile').files[0];
           const certificateFile = document.getElementById('certificateFile').files[0];
           const doctorData = {
               work_email: document.getElementById('workEmail').value,
               first_name: document.getElementById('firstName').value,
               surname: document.getElementById('lastName').value,
               last_name: document.getElementById('middleName').value || null,
               scientific_degree: document.getElementById('degree').value,
               date_of_last_attestation: document.getElementById('birthdate').value,
               diplomas: [{
                   date: document.getElementById('date_id').value,
                   series: document.getElementById('Serial_number').value,
                   number: document.getElementById('Number').value,
                   university: document.getElementById('University').value
               }],
               certificates: [{
                   date: document.getElementById('date_id').value,
                   series: document.getElementById('Serial_number').value,
                   number: document.getElementById('Number').value,
                   university: document.getElementById('University').value
               }],
               clinic_affiliations: [{
                   clinic_name: document.getElementById('Clinick_Name').value,
                   department: document.getElementById('Department').value,
                   position: document.getElementById('Job_title').value,
                   specialty: document.getElementById('specialization').value
               }]
           };
   
           // Создаем объект FormData
           const formData = new FormData();
           
           formData.append('doctor_data', JSON.stringify(doctorData));
           
           // Добавляем файлы, если они есть
           if (photoFile) {
               formData.append('doctors_photo', photoFile);
           }
           if (diplomaFile) {
               formData.append('diploma_scan', diplomaFile);
           }
           if (certificateFile) {
               formData.append('certificate_scan', certificateFile);
           }
   
           // Получаем токен 
        //   const token = localStorage.getItem('access_token');
           const token = new URLSearchParams(window.location.search).get('access_token');
           // Отправляем запрос на сервер
           const response = await fetch('/api/doctor/signup', {
               method: 'POST',
               headers: {
                   'Authorization': `Bearer ${token}`,
                   // Не устанавливаем Content-Type вручную - браузер сам добавит с boundary
               },
               body: formData
           });
   
           // Обрабатываем ответ
           if (!response.ok) {
               const errorData = await response.json();
               throw new Error(errorData.detail || 'Ошибка сервера');
           }
   
           const result = await response.json();
           console.log('Успешная регистрация:', result);
           
           // Показываем сообщение об успехе и перенаправляем
           alert('Регистрация успешно завершена! Ожидайте подтверждения.');
           window.location.href = '/registration_success.html';
   
       } catch (error) {
           console.error('Ошибка при отправке формы:', error);
           alert(`Ошибка: ${error.message}`);
       }
   }
   
   // Назначаем функцию на кнопку отправки
   document.getElementById('submitButton').addEventListener('click', submitForm);
   
   
   document.getElementById('diplomaFile').addEventListener('change', function(e) {
       const fileNameElement = document.getElementById('fileName');
       if (this.files.length > 0) {
           fileNameElement.textContent = this.files[0].name;
           fileNameElement.classList.add('has-file');
       } else {
           fileNameElement.textContent = 'Файл не выбран';
           fileNameElement.classList.remove('has-file');
       }
   });
   
   document.getElementById('certificateFile').addEventListener('change', function(e) {
       const fileNameElement = document.getElementById('certificateFileName');
       if (this.files.length > 0) {
           fileNameElement.textContent = this.files[0].name;
           fileNameElement.style.color = '#7f69bd';
       } else {
           fileNameElement.textContent = 'Файл не выбран';
       }
   });
   
   
   async function exportFormToPDF() {
       const { jsPDF } = window.jspdf;
       const doc = new jsPDF({
           orientation: 'portrait',
           unit: 'mm',
           format: 'a4'
       });
   
       // Загрузка шрифта (если нужно)
       try {
       const fontUrl = '/static/fonts/Roboto-Regular.ttf';
       const fontResponse = await fetch(fontUrl);
       const fontArrayBuffer = await fontResponse.arrayBuffer();
   
       function arrayBufferToBase64(buffer) {
           let binary = '';
           const bytes = new Uint8Array(buffer);
           for (let i = 0; i < bytes.length; i++) {
               binary += String.fromCharCode(bytes[i]);
           }
           return btoa(binary);
       }
   
       const fontBase64 = arrayBufferToBase64(fontArrayBuffer);
       doc.addFileToVFS('Roboto-Regular.ttf', fontBase64);
       doc.addFont('Roboto-Regular.ttf', 'Roboto', 'normal');
       doc.setFont('Roboto'); // Установить шрифт до любого текста
   } catch (error) {
       console.error('Ошибка загрузки шрифта:', error);
       doc.setFont('helvetica'); // fallback
   }
   
   
       // Получение значений полей
       const getFieldValue = (id) => {
           const el = document.getElementById(id);
           return el ? el.value || '' : '';
       };
   
       // Основные данные
       const personalData = {
           "Фамилия": getFieldValue("lastName"),
           "Имя": getFieldValue("firstName"),
           "Отчество": getFieldValue("middleName"),
           "Год рождения": getFieldValue("birthYear"),
           "Пол": getFieldValue("gender"),
           "Телефон": getFieldValue("Phone_number"),
           "Рабочий email": getFieldValue("workEmail")
       };
   
       const workData = {
           "Название клиники": getFieldValue("Clinick_Name"),
           "Отделение": getFieldValue("Department"),
           "Должность": getFieldValue("Job_title"),
           "Специализация": getFieldValue("specialization"),
           "Научная степень": getFieldValue("degree"),
           "Дата последней аттестации": getFieldValue("birthdate")
       };
   
       const diplomaData = {
           "Дата выдачи": getFieldValue("date_id"),
           "Серия": getFieldValue("Serial_number"),
           "Номер": getFieldValue("Number"),
           "ВУЗ": getFieldValue("University")
       };
   
       // Стили
       const titleStyle = { fontSize: 16, fontStyle: 'bold', textColor: '#5B4296' };
       const sectionTitleStyle = { fontSize: 14, fontStyle: 'bold', textColor: '#5B4296' };
       const fieldStyle = { fontSize: 12, textColor: '#323238' };
       const valueStyle = { fontSize: 12, textColor: '#000000' };
   
       // Функция для добавления текста с переносами
       function addTextWithLineBreaks(doc, text, x, y, maxWidth, lineHeight = 5) {
           const lines = doc.splitTextToSize(text, maxWidth);
           doc.text(lines, x, y);
           return y + (lines.length * lineHeight);
       }
   
       // Первая страница - персональные данные
       let y = 20;
       
       // Заголовок
       doc.setFontSize(titleStyle.fontSize);
       doc.setTextColor(titleStyle.textColor);
       doc.setFont(titleStyle.fontStyle);
       doc.text("Регистрационная карта врача", 105, y, { align: 'center' });
       y += 10;
   
       // Логотип (если нужно)
       // doc.addImage(logoData, 'JPEG', 15, y, 30, 10);
       // y += 15;
   
       // Персональные данные
       doc.setFontSize(sectionTitleStyle.fontSize);
       doc.setTextColor(sectionTitleStyle.textColor);
       doc.text("Личные данные", 15, y);
       y += 8;
   
       doc.setFontSize(fieldStyle.fontSize);
       doc.setTextColor(fieldStyle.textColor);
       
       // Добавляем фото, если есть
       const photoFile = document.getElementById('fileInput').files[0];
       if (photoFile) {
           const reader = new FileReader();
           reader.onload = function(e) {
               // Ограничиваем размер изображения
               const img = new Image();
               img.src = e.target.result;
               
               img.onload = function() {
                   const maxWidth = 40;
                   const maxHeight = 40;
                   let width = img.width;
                   let height = img.height;
                   
                   if (width > maxWidth) {
                       height = (maxWidth / width) * height;
                       width = maxWidth;
                   }
                   
                   if (height > maxHeight) {
                       width = (maxHeight / height) * width;
                       height = maxHeight;
                   }
                   
                   doc.addImage(img, 'JPEG', 150, y - 15, width, height);
               };
           };
           reader.readAsDataURL(photoFile);
       }
   
       // Выводим персональные данные
       for (const [label, value] of Object.entries(personalData)) {
           doc.setTextColor(fieldStyle.textColor);
           doc.text(`${label}:`, 15, y);
           doc.setTextColor(valueStyle.textColor);
           y = addTextWithLineBreaks(doc, value, 40, y, 100, 6);
       }
   
       // Проверяем, нужно ли добавить новую страницу
       if (y > 250) {
           doc.addPage();
           y = 20;
       } else {
           y += 10;
       }
   
       // Рабочие данные
       doc.setFontSize(sectionTitleStyle.fontSize);
       doc.setTextColor(sectionTitleStyle.textColor);
       doc.text("Профессиональные данные", 15, y);
       y += 8;
   
       doc.setFontSize(fieldStyle.fontSize);
       
       for (const [label, value] of Object.entries(workData)) {
           doc.setTextColor(fieldStyle.textColor);
           doc.text(`${label}:`, 15, y);
           doc.setTextColor(valueStyle.textColor);
           y = addTextWithLineBreaks(doc, value, 50, y, 140, 6);
       }
   
       // Проверяем, нужно ли добавить новую страницу
       if (y > 250) {
           doc.addPage();
           y = 20;
       } else {
           y += 10;
       }
   
       // Данные диплома
       doc.setFontSize(sectionTitleStyle.fontSize);
       doc.setTextColor(sectionTitleStyle.textColor);
       doc.text("Данные диплома", 15, y);
       y += 8;
   
       doc.setFontSize(fieldStyle.fontSize);
       
       for (const [label, value] of Object.entries(diplomaData)) {
           doc.setTextColor(fieldStyle.textColor);
           doc.text(`${label}:`, 15, y);
           doc.setTextColor(valueStyle.textColor);
           y = addTextWithLineBreaks(doc, value, 40, y, 150, 6);
       }
   
       // Добавляем файл диплома, если есть
       const diplomaFile = document.getElementById('diplomaFile').files[0];
       if (diplomaFile) {
           doc.setTextColor(fieldStyle.textColor);
           doc.text("Файл диплома:", 15, y);
           doc.setTextColor(valueStyle.textColor);
           y = addTextWithLineBreaks(doc, diplomaFile.name, 40, y, 150, 6);
       }
   
       // Проверяем, нужно ли добавить новую страницу
       if (y > 250) {
           doc.addPage();
           y = 20;
       } else {
           y += 10;
       }
   
       // Сертификат специалиста
       doc.setFontSize(sectionTitleStyle.fontSize);
       doc.setTextColor(sectionTitleStyle.textColor);
       doc.text("Сертификат специалиста", 15, y);
       y += 8;
   
       // Добавляем файл сертификата, если есть
       const certificateFile = document.getElementById('certificateFile').files[0];
       if (certificateFile) {
           doc.setFontSize(fieldStyle.fontSize);
           doc.setTextColor(fieldStyle.textColor);
           doc.text("Файл сертификата:", 15, y);
           doc.setTextColor(valueStyle.textColor);
           y = addTextWithLineBreaks(doc, certificateFile.name, 50, y, 140, 6);
       }
   
       // Добавляем подпись и дату в конце
       if (y > 200) {
           doc.addPage();
           y = 20;
       } else {
           y = 250;
       }
   
       doc.setFontSize(12);
       doc.text("Дата заполнения: " + new Date().toLocaleDateString(), 15, y);
       y += 10;
       doc.text("Подпись: ___________________", 15, y);
   
       // Сохраняем PDF
       doc.save("Регистрационная_карта_врача.pdf");
   }
   
   
   // Функция для обновления прогресс бара
   function updateProgressBar(currentStep) {
       const visibleModal = document.querySelector('.modal[style*="display: block"]');
       if (visibleModal) {
           const progressBar = visibleModal.querySelector('.progress-bar');
           if (progressBar) {
               const steps = progressBar.querySelectorAll('.progress-step');
               
               steps.forEach((step, index) => {
                   if (index < currentStep) {
                       step.classList.add('active');
                   } else {
                       step.classList.remove('active');
                   }
               });
           }
       }
   }






function generateQrCodeFromText(corId) {
    const qrCodeDiv = document.getElementById("qrcode"); // Получаем элемент с ID 'qrcode'
    if (!qrCodeDiv) {
        console.error("Элемент с ID 'qrcode' не найден.");
        return;
    }
    qrCodeDiv.innerHTML = ''; // Очищаем старый QR-код
    new QRCode(qrCodeDiv, {
        text: corId,
        width: 200,
        height: 200
    });
}





function showCorIdInfo(corId) {
    if( checkToken()){
    const accessToken = getToken();
           if (!accessToken) {
               console.error('Токен не найден!');
               return;
           }

       fetch("/api/medical/cor_id/show_corid_info", {
           method: "POST",
           headers: {
               "Content-Type": "application/json",
               "Authorization": `Bearer ${accessToken}`
           },
           body: JSON.stringify({ cor_id: corId })
       })
       .then(response => {
           if (!response.ok) {
               console.error('Ошибка на сервере:', response.statusText);
               throw new Error("COR-Id не найден");
           }
           return response.json();
       })
       .then(data => {
           // Преобразование дней в дату
           const baseDate = new Date(2024, 0, 1); // 1 января 2024 года
           const registrationDate = new Date(baseDate);
           registrationDate.setDate(baseDate.getDate() + data.n_days_since);

           // Форматирование даты
           const options = { year: 'numeric', month: 'long', day: 'numeric' };
           const formattedDate = registrationDate.toLocaleDateString('ru-RU', options);

           // Отображение данных в модальном окне
           document.getElementById("corIdValue").textContent = corId;
           const corIdInfo = `
            <div class="cor-text">
               <p><strong>Дата регистрации:</strong> ${formattedDate}</p>
               <p><strong>Номер учреждения:</strong> ${data.facility_number}</p>
               <p><strong>Номер пациента за день:</strong> ${data.register_per_day}</p>
               <p><strong>Год рождения:</strong> ${data.birth_year}</p>
               <p><strong>Пол:</strong> ${data.gender}</p>
               <p><strong>Версия:</strong> ${data.version}</p>
            </div>
                  
           `;
           document.getElementById("corIdInfo").innerHTML = corIdInfo;
           openModal();

           // Генерация QR-кода только после открытия модального окна
           generateQrCodeFromText(corId); // Генерация QR-кода
       })
       .catch(error => {
           console.error("Ошибка:", error);
           alert("Ошибка при загрузке информации о COR-ID");
       });
   }}




   function initializeCheckboxes() {
    const columnState = JSON.parse(localStorage.getItem('columnsState') || '{}');
    console.log('Состояние колонок из localStorage:', columnState);

    // Пробегаемся по всем чекбоксам и обновляем их состояние
    const checkboxes = document.querySelectorAll('#columnSelectModal input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        const columnId = checkbox.id.replace('checkbox-', ''); // Извлекаем ID колонки без префикса
        console.log('ID колонки:', columnId);

        // Проверяем и устанавливаем состояние чекбокса
        if (columnState[columnId] !== undefined) {
            checkbox.checked = columnState[columnId];
            console.log(`Состояние для ${columnId}: ${columnState[columnId]}`);
        } else {
            console.log(`Нет состояния для ${columnId}, устанавливаем по умолчанию`);
        }
    });
}


function populateTable(users) {
    if( checkToken()){
    console.log("Заполнение таблицы пользователями:", users); // Проверка данных
    const tbody = document.querySelector('#userTable tbody');
    tbody.innerHTML = ''; // Очистить таблицу перед заполнением

    users.forEach(user => {
        const row = document.createElement('tr');

      // Рассчитываем разницу во времени
        const currentTime = new Date();
        const lastActiveTime = user.last_active ? new Date(user.last_active) : null;
        const timeDiff = lastActiveTime ? (currentTime - lastActiveTime) / (1000 * 60 * 60) : null; // Разница в часах

        const activityTitle = lastActiveTime
        ? (timeDiff >= 1 
            ? `${Math.floor(timeDiff)} ч ${Math.floor((timeDiff % 1) * 60)} мин назад` // Часы и минуты
            : `${Math.floor(timeDiff * 60)} минут назад`) // Только минуты
            : 'Неактивен';

        let activityColor = 'gray'; // По умолчанию - серый

        if (timeDiff !== null) {
            if (timeDiff <= 24) {
                // Рассчитываем коэффициент для интерполяции цвета (от 0 до 1)
                const gradientFactor = timeDiff / 24;

                // Вычисляем цвет от зелёного (0, 255, 0) к красному (255, 0, 0)
                const red = Math.round(gradientFactor * 255); // Увеличивается с течением времени
                const green = Math.round((1 - gradientFactor) * 255); // Уменьшается с течением времени
                activityColor = `rgb(${red}, ${green}, 0)`; // Получаем итоговый цвет
            }
        }


        row.innerHTML = `
        ${document.getElementById('header-user_index').style.display !== 'none' ? `<td>${user.user_index}</td>` : ''}
        ${document.getElementById('header-id').style.display !== 'none' ? `<td>${user.id}</td>` : ''}
        ${document.getElementById('header-cor_id').style.display !== 'none' ? `<td class="cor-id-cell">${user.cor_id}</td>` : ''}
        ${document.getElementById('header-user_sex').style.display !== 'none' ? `<td>${user.user_sex}</td>` : ''}
        ${document.getElementById('header-birth').style.display !== 'none' ? `<td>${user.birth}</td>` : ''}
        ${document.getElementById('header-email').style.display !== 'none' ? `<td>${user.email}</td>` : ''}
        ${document.getElementById('header-created_at').style.display !== 'none' ? `<td>${new Date(user.created_at).toLocaleString()}</td>` : ''}
        ${document.getElementById('header-last_password_change').style.display !== 'none' ? `<td>${new Date(user.last_password_change).toLocaleString()}</td>` : ''}      
        ${document.getElementById('header-last_active').style.display !== 'none' ? `<td>${new Date(user.last_active).toLocaleString()}</td>` : ''} 
            <td> <select onchange="confirmStatusChange('${user.email}', this.value)">
                    <option value="basic" ${user.account_status === 'basic' ? 'selected' : ''}>basic</option>
                    <option value="premium" ${user.account_status === 'premium' ? 'selected' : ''}>premium</option>
                </select>
            </td>
            <td> <span class="delete-icon" onclick="deleteUser('${user.email}')">🗑️</span>
                <span class="toggle-status-icon" onclick="toggleUserStatus('${user.email}', ${user.is_active ?? true})">
                 ${user.is_active !== false ? '🔓' : '🔒'}</span>
                 <span class="roles-icon" onclick="showUserRoles('${user.cor_id}')">👤</span>
                     <span class="activity-indicator" style="background: ${activityColor}; display: inline-block; width: 12px; height: 12px;" title="Активность: ${activityTitle}"></span>
            </td>
        `;

        tbody.appendChild(row);
    });
    adjustTableLayout();
}}

      // Функция для удаления пользователя
      async function deleteUser(email) {
        const url = `/api/admin/${email}`;

        if (confirm(`Вы уверены, что хотите удалить пользователя с email: ${email}?`)) {
            try {
                const response = await fetch(url, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + getToken()
                    }
                });

                if (response.ok) {
                    alert(`Пользователь ${email} успешно удален.`);
                    getAllUsers(); // Обновить таблицу после удаления
                } else {
                    const errorData = await response.json();
                    alert(`Ошибка удаления: ${errorData.message || response.statusText}`);
                }
            } catch (error) {
                console.error('Ошибка при удалении пользователя:', error);
                alert('Произошла ошибка при удалении пользователя.');
            }
        }
    }


  // Функция для переключения отображения колонок
  function toggleColumn(column) {
    const header = document.getElementById(`header-${column}`);
    if (!header) return;
    
    const isVisible = header.style.display !== 'none';
    header.style.display = isVisible ? 'none' : '';

    const columnIndex = Array.from(header.parentNode.children).indexOf(header) + 1;
    document.querySelectorAll(`tbody td:nth-child(${columnIndex})`).forEach(cell => {
        cell.style.display = header.style.display;
    });

    const columnState = JSON.parse(localStorage.getItem('columnsState') || '{}');
    columnState[column] = !isVisible;
    localStorage.setItem('columnsState', JSON.stringify(columnState));

    initializeCheckboxes();

    // Сначала пересчёт ширины и колонок, потом загрузка данных
    adjustTableLayout();
   
    loadPage();
}
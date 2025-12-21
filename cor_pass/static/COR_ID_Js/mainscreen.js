



async function deleteSession(sessionId) {
try {
    const accessToken =getToken();
    const response = await fetch(`/api/user/sessions/${sessionId}`, {
        method: "DELETE",
        headers: {
            "Authorization": `Bearer ${accessToken}`,
            "Content-Type": "application/json;charset=utf-8"
        }
    });

    if (!response.ok) {
        throw new Error(`Ошибка: ${response.status}`);
    }

    const result = await response.json();
    console.log("Сессия удалена:", result);
  
    // Обновляем список сессий после удаления
    await getSessions();
    
    // Можно добавить уведомление об успешном удалении
    alert("Сессия успешно удалена!!!");
    
} catch (error) {
    console.error("Ошибка удаления сессии:", error);
    alert("Не удалось удалить сессию: " + error.message);
}
}




// Функция для получения данных о сессиях
async function getSessions() {
try {
    const accessToken =getToken();
    const response = await fetch("/api/user/sessions/all?skip=0&limit=150", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${accessToken}`,
            "Content-Type": "application/json;charset=utf-8"
        }
    });

    if (!response.ok) {
        throw new Error(`Ошибка: ${response.status}`);
    }

    const sessions = await response.json();
    console.log("Список сессий:", sessions);

    const cardsContainer = document.getElementById("sessionCardsContainer");
    cardsContainer.innerHTML = "";

    sessions.forEach(session => {
        const card = document.createElement("div");
        card.className = "session-card";
        card.innerHTML = `
        <div class="card-content">
          <div class="session-text">
            <p><strong>${dict.session_about_device || "Про устройство:"}</strong> ${session.device_info}</p>
            <p><strong>${dict.session_device || "Устройство:"}</strong> ${session.device_type || "-"}, ${session.device_os || "-"}</p>
            <p><strong>${dict.session_ip || "IP-адрес:"}</strong> ${session.ip_address || "-"}</p>
            <p><strong>${dict.session_place || "Местоположение:"}</strong> ${session.city_name || "-"}</p>
            <p><strong>${dict.session_dates || "Дата:"}</strong>
                ${dict.session_created || "Создана:"} ${new Date(session.created_at).toLocaleString()},
                ${dict.session_updated || "Обновлена:"} ${new Date(session.updated_at).toLocaleString()}
            </p>
          </div>
            <button style="
            color: transparent;
            background: transparent;
            outline: none;
            border: none;" 
            class="modal-button session-delete-button" data-session-id="${session.id}">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
                    <path fill-rule="evenodd" clip-rule="evenodd" d="M18.6872 5.31275C19.1042 5.72975 19.1042 
                    6.40584 18.6872 6.82284L6.82284 18.6873C6.40584 19.1042 5.72975 19.1042 5.31275 
                    18.6873C4.89575 18.2702 4.89575 17.5942 5.31275 17.1772L17.1772 5.31275C17.5942 
                    4.89575 18.2702 4.89575 18.6872 5.31275Z" fill="#B1A1DA"></path>
                    <path fill-rule="evenodd" clip-rule="evenodd" d="M18.6873 18.6873C18.2702 19.1042 
                    17.5942 19.1042 17.1772 18.6873L5.31275 6.82284C4.89575 6.40584 4.89575 5.72975 
                    5.31275 5.31275C5.72975 4.89575 6.40584 4.89575 6.82284 5.31275L18.6873 
                    17.1772C19.1042 17.5942 19.1042 18.2702 18.6873 18.6873Z" fill="#B1A1DA"></path>
                </svg>
          </button>
        </div>
        `;
        cardsContainer.appendChild(card);
    });

    // Добавляем обработчики событий для кнопок удаления
    document.querySelectorAll('.modal-button.session-delete-button').forEach(button => {
        button.addEventListener('click', async function() {
            const sessionId = this.getAttribute('data-session-id');
            await deleteSession(sessionId);
        });
    });

// Рассчитываем высоту всех карточек
    const cardsHeight = Array.from(cardsContainer.children).reduce((totalHeight, card) => {
    return totalHeight + card.offsetHeight;}, 0);
    const padding = 40; // Отступы внутри модального окна
    const modal = document.getElementById("sessionsModal");

} catch (error) {
    console.error("Ошибка получения сессий:", error);
}
}



 async function fetchCorId() {
    const accessToken =getToken();
    if (!checkToken()) {
        console.error("Токен не найден!!!");
        document.getElementById('userCorId').textContent = userCorIdElement.textContent = dict.corid_token_not_found || "Токен не найден!!!";
        return;
    }

    try {
        const response = await fetch('/api/user/my_core_id', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error("Ошибка при получении COR-ID:", errorData);
            document.getElementById('userCorId').textContent = userCorIdElement.textContent = dict.corid_fetch_error || "Ошибка при получении COR-ID.";
            return;
        }

        const corId = await response.json();
        const userCorIdElement = document.getElementById('userCorId');
        userCorIdElement.textContent = `${corId}`;
        extractAndSaveGenderAndBirthYear(corId);

            // Обработчик клика для отображения QR-кода
            userCorIdElement.addEventListener('click', () => toggleQrCode(corId));
            // Обработчик клика на сам QR-код для его скрытия
        const qrCodeContainer = document.getElementById('qrCodeContainer');
        qrCodeContainer.addEventListener('click', () => {
            qrCodeContainer.style.display = 'none'; 
            qrCodeContainer.innerHTML = ''; 
        });
    } catch (error) {
        console.error("Ошибка при запросе COR-ID:", error);
        document.getElementById('userCorId').textContent = userCorIdElement.textContent = dict.corid_load_error || "Ошибка при загрузке COR-ID.";
    }
}




    function toggleQrCode(corId) {
        const qrCodeContainer = document.getElementById('qrCodeContainer');
        if( checkToken()){
        if (qrCodeContainer.style.display === 'block') {
            // Скрываем QR-код, если он уже отображается
            qrCodeContainer.style.display = 'none';
            qrCodeContainer.innerHTML = ''; // Очищаем контейнер
        } else {
            // Показываем QR-код
            qrCodeContainer.style.display = 'block';

            // Очищаем предыдущий QR-код (если есть)
            qrCodeContainer.innerHTML = '';

            // Генерация нового QR-кода
            new QRCode(qrCodeContainer, {
                text: corId,
                width: 160,
                height: 160
            });
        }}
    }
    


    
function extractAndSaveGenderAndBirthYear(corId) {
    try {
        console.log("Обрабатываем COR-ID:", corId); 
        const match = corId.match(/^(.{9})-(\d{4})([MF])$/);  
        if (match) {
            const coreId = match[1];        // 1TJF3GDHL
            const birthYear = match[2];     // 2008
            const gender = match[3];        // M или F    
            console.log("Извлеченные данные:", { coreId, birthYear, gender });   
            // Сохраняем в localStorage
            localStorage.setItem('userGender', gender);
            localStorage.setItem('userBirthYear', birthYear);
                   
            console.log("Данные сохранены в localStorage:");
            console.log("Пол:", localStorage.getItem('userGender'));
            console.log("Год рождения:", localStorage.getItem('userBirthYear'));
            
            
        } else {
            console.warn("Не верный формат COR-ID:", corId);
        }
        
    } catch (error) {
        console.error("Ошибка при обработке COR-ID:", error);
    }
}


/* Применяем роли пользователя к интерфейсу */
function applyRolesToUI({accessToken,dict,buttons,adminButtonContainer}) {
    if (!accessToken) {
        console.warn("Нет токена — роли не применяются");
        return;
    }

    try {
        const decodedToken = decodeToken(accessToken);
        console.log("Decoded token:", decodedToken);

        if (!decodedToken.roles || !Array.isArray(decodedToken.roles)) {
            console.warn("Роли отсутствуют или неверны");
            return;
        }

        decodedToken.roles.forEach(role => {
            switch (role) {

                case 'admin': {
                    const adminButton = document.createElement('button');
                    adminButton.innerText =
                        dict?.admin_button || 'Администрирование';

                    adminButton.onclick = () => {
                        window.location.href = `/static/COR_ID/admin.html`;
                    };

                    adminButtonContainer.appendChild(adminButton);
                    break;
                }

                case 'cor-int':
                    buttons.corErp?.classList.remove('hidden');
                    break;

                case 'energy_manager':
                    buttons.energyManager?.classList.remove('hidden');
                    break;

                case 'doctor':
                case 'lab_assistant':
                    buttons.doctor?.classList.remove('hidden');
                    break;

                case 'financier':
                    buttons.financier?.classList.remove('hidden');
                    break;

                case 'lawyer':
                    buttons.lawyer?.classList.remove('hidden');
                    buttons.manager?.classList.remove('hidden');
                    break;

                case 'device_user':
                    buttons.deviceUser?.classList.remove('hidden');
                    break;

                default:
                    console.log(`Неизвестная роль: ${role}`);
            }
        });

    } catch (error) {
        console.error("Ошибка применения ролей:", error);
    }
}




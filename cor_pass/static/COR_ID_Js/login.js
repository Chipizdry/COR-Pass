
document.addEventListener('DOMContentLoaded', function () {
    // Открытие модального окна
    document.getElementById('recovery-btn').onclick = function() {
        document.getElementById('recovery_modal').style.display = 'block';
        document.getElementById('email-recovery').style.display = 'none';
        document.getElementById('email-recovery-label').style.display = 'none';
        document.getElementById('send-recovery-btn').style.display = 'none';
        document.getElementById('file-upload-field').style.display = 'none';
        document.getElementById('super-password-field').style.display = 'none';

    }

    // Ввод супер-пароля
        document.getElementById('super-password-btn').onclick = function() {
        document.getElementById('super-password-field').style.display = 'block';
        document.getElementById('file-upload-field').style.display = 'none';
        document.getElementById('email-recovery').style.display = 'block';
        document.getElementById('email-recovery-label').style.display = 'block';
        document.getElementById('send-recovery-btn').style.display = 'block';
    }

    // Прикрепление файла восстановления
        document.getElementById('file-upload-btn').onclick = function() {
        document.getElementById('file-upload-field').style.display = 'block';
        document.getElementById('super-password-field').style.display = 'none';
        document.getElementById('email-recovery').style.display = 'block';
        document.getElementById('email-recovery-label').style.display = 'block';
        document.getElementById('send-recovery-btn').style.display = 'block';
    }

        document.getElementById('custom-file-upload-btn').addEventListener('click', function () {
        document.getElementById('recovery-file').click(); // Открыть окно выбора файла
         });


    document.getElementById('recovery-file').addEventListener('change', function () {
    const fileName = this.files[0] ? this.files[0].name : translations[selectedLanguage]["recovery-modal-no-file"];
    document.getElementById('file-name').textContent = fileName;
});
    // Закрытие модального окна при клике вне его
    window.onclick = function(event) {
        if (event.target == document.getElementById('recovery_modal')) {
            document.getElementById('recovery_modal').style.display = 'none';
        }
    }
// Обработка отправки данных формы
document.getElementById('send-recovery-btn').addEventListener('click', async function() {
    const email = document.getElementById('email-recovery').value;
    const recoveryFile = document.getElementById('recovery-file').files[0];
    const superPassword = document.getElementById('super-password').value;

    if (recoveryFile) {
        // Если файл прикреплен, используем восстановление по файлу
        const formData = new FormData();
        formData.append('email', email);
        formData.append('file', recoveryFile);

        try {
            const response = await fetch('api/auth/restore_account_by_recovery_file', {
                method: 'POST',
                body: formData 
            });

            if (response.ok) {
               
            const result = await response.json();
            console.log('Ответ сервера:', result); 
            alert('Успешное восстановление доступа по файлу');
            localStorage.setItem('access_token', result.access_token);
            setTimeout(() => {
                            const refreshToken = result.refresh_token;
                            const accessToken = result.access_token;

                            localStorage.setItem('access_token', result.access_token);
                            localStorage.setItem('refresh_token', result.refresh_token);
                            const url = `/static/COR_ID/mainscreen.html`;

                            window.location.href = url;
                        }, 500);


            } else {
                const errorData = await response.json();
                alert(`Ошибка: ${errorData.detail}`);
                const errorMessage = getErrorMessage(xhr.status, messageDiv);
                console.error("Error during login.");
                messageDiv.innerText = errorMessage;
                messageDiv.style.color = 'red';
            }
        } catch (error) {
            alert('Произошла ошибка при восстановлении доступа по файлу');
        }
    } else if (superPassword) {
        // Если введен супер-пароль, используем восстановление по супер-паролю
        const body = {
            email: email,
            recovery_code: superPassword
        };

        try {
            const response = await fetch('api/auth/restore_account_by_text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Ответ сервера:', result);
                alert('Успешное восстановление доступа по супер-паролю');
                localStorage.setItem('access_token', result.access_token);
                setTimeout(() => {
                           
                            localStorage.setItem('access_token', response.access_token);
                            localStorage.setItem('refresh_token', response.refresh_token);
                            const url = `/static/COR_ID/mainscreen.html`;
                            window.location.href = url;
                        }, 500);
              
            } else {
                const errorData = await response.json();
                alert(`Ошибка: ${errorData.detail}`);
                const errorMessage = getErrorMessage(xhr.status, messageDiv);
                console.error("Error during login.");
                messageDiv.innerText = errorMessage;
                messageDiv.style.color = 'red';
            }
        } catch (error) {
            alert('Произошла ошибка при восстановлении доступа по супер-паролю');
        }
    } else {
        alert('Пожалуйста, выберите способ восстановления и заполните необходимые поля.');
    }
});




// Генерация уникального идентификатора устройства (если его нет)
function getDeviceId() {
    let deviceId = localStorage.getItem("device_id");
    if (!deviceId) {
        deviceId = crypto.randomUUID();
        localStorage.setItem("device_id", deviceId);
    }
    return deviceId;
}


async function loadVersion() {
    try {
      const response = await fetch("/version");
      const data = await response.json();
      console.log("Версия сборки:", data.version);
      document.getElementById("app-version").innerText = data.version;
    } catch (err) {
      console.error("Ошибка при получении версии:", err);
      document.getElementById("app-version").innerText = "Не удалось получить версию";
    }
  }

  loadVersion();

});
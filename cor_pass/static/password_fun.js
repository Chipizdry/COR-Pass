

async function deleteCurrentRecord() {
    if (checkToken()) {
    const id = parseInt(window.currentRecordId); // важно: window
    if (isNaN(id)) {
        alert("Record ID is invalid.");
        return;
    }

    if (!confirm('Are you sure you want to delete this record?')) return;

    try {
        const response = await fetch(`/api/records/${id}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + getToken()
            }
        });

        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }

        alert('Record deleted successfully');
        document.getElementById('editModal').style.display = 'none';
        await fetchRecords(); // Обновление списка
    } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
    }
}}



async function saveEdit() {
    if (checkToken()) {
    const editForm = document.getElementById('editRecordForm');
   // const editForm = document.getElementById('editForm');
    const editModal = document.getElementById('editModal');
    const saveChangesButton = document.getElementById('saveChangesButton');

    if (!editForm || !editModal || !saveChangesButton) {
        console.warn('Не найдены элементы editForm, editModal или saveChangesButton');
        return;
    }

    const formData = new FormData(editForm);
    const data = Object.fromEntries(formData.entries());

    console.log('Updating record with ID:', window.currentRecordId);
    console.log('Data to be sent:', data);

    try {
        const response = await fetch(`/api/records/${window.currentRecordId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' +getToken()
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const errorMessage = await response.text();
            throw new Error('Network response was not ok: ' + response.statusText + ', ' + errorMessage);
        }

        const updatedRecord = await response.json();
        alert('Изменения сохранены');
        editModal.style.display = 'none';
        await fetchRecords();
    } catch (error) {
        console.error('Ошибка при сохранении изменений:', error);
        alert('Ошибка при сохранении изменений');
    }
}}



async function savePasswordStorageSettings() {
    if (checkToken()) {
    console.log('Кнопка "Сохранить настройки" нажата');

    const localPasswordStorage = document.getElementById('localStorageCheckbox').checked;
    const cloudPasswordStorage = document.getElementById('serverStorageCheckbox').checked;

    console.log('Полученные значения настроек:', { localPasswordStorage, cloudPasswordStorage });

    const settingsData = {
        local_password_storage: localPasswordStorage,
        cloud_password_storage: cloudPasswordStorage
    };

    try {
        const response = await fetch('/api/user/settings/password_storage', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' +getToken()
            },
            body: JSON.stringify(settingsData)
        });

        console.log('Ответ от сервера на запрос изменения настроек:', response.status);

        if (!response.ok) {
            throw new Error('Ошибка сети: ' + response.statusText);
        }

        const result = await response.json();
        console.log('Сервер успешно обновил настройки:', result.message);

    } catch (error) {
        console.error('Ошибка при сохранении настроек:', error);
    }
}}



async function fetchRecords(skip = 0, limit = 5) {
    if (checkToken()) {
    console.log('Starting fetchRecords function');

    try {
        const url = `/api/records/all?skip=${skip}&limit=${limit}`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' +getToken(),
            },
        });

        if (!response.ok) {
            throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
        }

        const records = await response.json();
        console.log('Records fetched:', records);

        populateTable(records);
        checkRecords(records);
    } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
        checkRecords([]); // передаём пустой массив, если ошибка
    }
}}




async function fetchSettings() {
    if (checkToken()) {
        try {
            const response = await fetch('/api/user/get_settings', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + getToken(),
                }
            });

            console.log('Ответ от сервера получен, статус ответа:', response.status);

            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }

            const data = await response.json();
            console.log('Настройки, полученные с сервера:', data);

            document.getElementById('localStorageCheckbox').checked = !!data.local_password_storage;
            document.getElementById('serverStorageCheckbox').checked = !!data.cloud_password_storage;

        } catch (error) {
            console.error('Ошибка при получении настроек:', error);
        }
    }
}

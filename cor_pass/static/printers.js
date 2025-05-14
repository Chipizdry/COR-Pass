document.getElementById('sendLabelButton').addEventListener('click', async () => {
    const apiUrl = '/api/print_labels'; 
    
    const requestData = {
        labels: [
            {
                model_id: 8,
                content: "FF|S24B0460|A|1|L0|H&E|?|TDAJ92Z7-1983M",
                uuid: Date.now().toString()  
            }
        ]
    };

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Unknown error');
        }

        const result = await response.json();
        console.log('Печать успешна:', result);
        alert('Задание отправлено на принтер');
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при печати: ' + error.message);
    }
});
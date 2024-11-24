


function makeModalDraggable(modalId) {
    const modal = document.getElementById(modalId);
    const header = modal.querySelector('.modal-header');
    let isDragging = false;
    let offsetX = 0, offsetY = 0;

    header.onmousedown = function(e) {
        isDragging = true;
        // Вычисляем начальное смещение курсора относительно модального окна
        offsetX = e.clientX - modal.offsetLeft;
        offsetY = e.clientY - modal.offsetTop;

        // Добавляем события перемещения и отпускания мыши
        document.onmousemove = function(e) {
            if (isDragging) {
                modal.style.left = `${e.clientX - offsetX}px`;
                modal.style.top = `${e.clientY - offsetY}px`;
            }
        };

        document.onmouseup = function() {
            isDragging = false;
            document.onmousemove = null;
            document.onmouseup = null;
        };
    };
}


// Объект для хранения состояния каждого модального окна
const modalStates = {};

// Универсальная функция для закрытия модального окна
function closeModal(modalId) {
    console.log(`Закрытие модального окна: ${modalId}`); 
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}

// Универсальная функция для минимизации модального окна
function minimizeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('minimized'); // Добавляем класс минимизированного состояния
        modalStates[modalId] = { ...modalStates[modalId], minimized: true };
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}

// Универсальная функция для максимизации/восстановления модального окна
function maximizeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        const isMaximized = modalStates[modalId]?.maximized || false;
        modal.classList.remove('minimized'); // Убираем класс минимизации
        if (isMaximized) {
            // Восстановление окна до исходного состояния
            modal.style.width = '';
            modal.style.height = '';
            modal.style.top = '50%';
            modal.style.left = '50%';
            modal.style.transform = 'translate(-50%, -50%)';
        } else {
            // Максимизация окна
            modal.style.width = '100%';
            modal.style.height = '100%';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.transform = 'none';
        }

        modalStates[modalId] = { ...modalStates[modalId], maximized: !isMaximized };
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}

// Универсальная функция для инициализации кнопок модального окна
function initModalControls(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        // Добавление слушателей событий для кнопок управления
        const closeButton = modal.querySelector('[data-action="close"]');
        const minimizeButton = modal.querySelector('[data-action="minimize"]');
        const maximizeButton = modal.querySelector('[data-action="maximize"]');

        if (closeButton) closeButton.addEventListener('click', () => closeModal(modalId));
        if (minimizeButton) minimizeButton.addEventListener('click', () => minimizeModal(modalId));
        if (maximizeButton) maximizeButton.addEventListener('click', () => maximizeModal(modalId));

        // Сохранение начального состояния модального окна
        modalStates[modalId] = { maximized: false, minimized: false };
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}

// Инициализация всех модальных окон на странице
function initAllModals() {
    const modals = document.querySelectorAll('.modal'); // Предполагаем, что все модальные окна имеют класс "modal"
    modals.forEach((modal) => {
        const modalId = modal.id;
        if (modalId) {
            initModalControls(modalId);
        }
    });
}

// Автоматическая инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', initAllModals);

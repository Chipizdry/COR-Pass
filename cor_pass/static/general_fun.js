
const modalConfigs = {
    columnSelectModal: { width: '250px', height: '300px', top: '300px', left: '200px' },
    corIdModal: { width: '300px', height: '500px', top: '300px', left: '250px' },
    editModal: { width: '250px', height: '500px', top: '50px', left: '50px' },
    myModal: { width: '250px', height: '500px', top: '50px', left: '250px' },
    settingsModal: { width: '500px', height: '560px', top: '50px', left: '450px' },
};

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
    const maximizeButton = modal.querySelector('[data-action="maximize"]');

    if (modal) {
        // Сохраняем текущее состояние перед минимизацией
        if (!modalStates[modalId]?.minimized) {
            modalStates[modalId] = {
                ...modalStates[modalId],
                width: modal.style.width || getComputedStyle(modal).width,
                height: modal.style.height || getComputedStyle(modal).height,
                top: modal.style.top || getComputedStyle(modal).top,
                left: modal.style.left || getComputedStyle(modal).left,
                minimized: true,
                maximized: false,
            };
        }

        // Применяем минимизацию
        modal.classList.add('minimized');
        modal.style.width = '200px'; // Размеры минимизированного окна
        modal.style.height = '40px';
        modal.style.top = 'auto';
        modal.style.left = '10px';
        modal.style.transform = 'none';

        // Изменяем иконку кнопки максимизации/восстановления
        if (maximizeButton) maximizeButton.textContent = '🗖';
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}

// Универсальная функция для максимизации/восстановления модального окна

function maximizeModal(modalId) {
    const modal = document.getElementById(modalId);
    const maximizeButton = modal.querySelector('[data-action="maximize"]');

    if (modal) {
        const isMaximized = modalStates[modalId]?.maximized || false;
        const isMinimized = modalStates[modalId]?.minimized || false;

        if (isMinimized) {
            // Восстановление из минимизированного состояния
            modal.classList.remove('minimized');
            modal.style.width = modalStates[modalId].width;
            modal.style.height = modalStates[modalId].height;
            modal.style.top = modalStates[modalId].top;
            modal.style.left = modalStates[modalId].left;
            modal.style.transform = 'none';
            modalStates[modalId].minimized = false;

            // Изменяем иконку кнопки на двойной квадрат
            if (maximizeButton) maximizeButton.textContent = '🗖';
        } else if (isMaximized) {
            // Восстановление окна до исходного состояния из modalConfigs
            const defaultConfig = modalConfigs[modalId];
            if (defaultConfig) {
                modal.style.width = defaultConfig.width;
                modal.style.height = defaultConfig.height;
                modal.style.top = defaultConfig.top;
                modal.style.left = defaultConfig.left;
                modal.style.transform = 'none';
            }
            modalStates[modalId].maximized = false;

            // Изменяем иконку кнопки на двойной квадрат
            if (maximizeButton) maximizeButton.textContent = '🗖';
        } else {
            // Максимизация окна
            modalStates[modalId] = {
                ...modalStates[modalId],
                width: modal.style.width || getComputedStyle(modal).width,
                height: modal.style.height || getComputedStyle(modal).height,
                top: modal.style.top || getComputedStyle(modal).top,
                left: modal.style.left || getComputedStyle(modal).left,
            };

            modal.style.width = '100%';
            modal.style.height = '100%';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.transform = 'none';
            modalStates[modalId].maximized = true;

            // Изменяем иконку кнопки на одинарный квадрат
            if (maximizeButton) maximizeButton.textContent = '🗗';
        }
    } else {
        console.error(`Модальное окно с id "${modalId}" не найдено.`);
    }
}


function initModalControls(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        const closeButton = modal.querySelector('[data-action="close"]');
        const minimizeButton = modal.querySelector('[data-action="minimize"]');
        const maximizeButton = modal.querySelector('[data-action="maximize"]');

        if (closeButton) closeButton.addEventListener('click', () => closeModal(modalId));
        if (minimizeButton) minimizeButton.addEventListener('click', () => minimizeModal(modalId));
        if (maximizeButton) maximizeButton.addEventListener('click', () => maximizeModal(modalId));

        // Устанавливаем начальные размеры и положение
        const config = modalConfigs[modalId];
        if (config) {
            modal.style.width = config.width;
            modal.style.height = config.height;
            modal.style.top = config.top;
            modal.style.left = config.left;
            modal.style.transform = 'none'; // Убираем стандартное центрирование
        }

        // Сохраняем начальное состояние окна
        modalStates[modalId] = {
            maximized: false,
            minimized: false,
            ...config // Сохраняем параметры для восстановления
        };
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

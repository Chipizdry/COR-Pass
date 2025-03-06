
const modalConfigs = {
    columnSelectModal: { width: '250px', height: '300px', top: '300px', left: '200px' },
    corIdModal: { width: '300px', height: '500px', top: '300px', left: '250px' },
    editModal: { width: '250px', height: '500px', top: '50px', left: '50px' },
    myModal: { width: '250px', height: '450px', top: '50px', left: '250px' },
    settingsModal: { width: '550px', height: '560px', top: '50px', left: '450px' },
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


function togglePassword(inputId, iconId) {
    const passwordInput = document.getElementById(inputId);
    const eyeIcon = document.getElementById(iconId);

    // Переключение типа поля
    const isPasswordHidden = passwordInput.type === 'password';
    passwordInput.type = isPasswordHidden ? 'text' : 'password';

    // Обновление иконки в зависимости от состояния
    updateEyeIcon(eyeIcon, isPasswordHidden);
}

// Функция установки иконки (по умолчанию закрытый глаз)
function updateEyeIcon(eyeIcon, isPasswordHidden) {
    
    eyeIcon.innerHTML = ''; // Очистка
    const svgIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgIcon.setAttribute('width', '25');
    svgIcon.setAttribute('height', '24');
    svgIcon.setAttribute('viewBox', '0 0 25 24');
    svgIcon.setAttribute('fill', 'none');
    svgIcon.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
   
    if (isPasswordHidden) {
        // Открытый глаз
        svgIcon.innerHTML = `
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.1918 11.4766C22.1623 11.41 21.4476 9.82457 19.8588 8.23578C17.7418 6.11881 15.068 
              5 12.125 5C9.182 5 6.50815 6.11881 4.39118 8.23578C2.8024 9.82457 2.08437 11.4125 2.05821 
              11.4766C2.01983 11.563 2 11.6564 2 11.7508C2 11.8453 2.01983 11.9387 2.05821 12.0251C2.08774 
              12.0917 2.8024 13.6763 4.39118 15.2651C6.50815 17.3812 9.182 18.5 12.125 18.5C15.068 18.5 
              17.7418 17.3812 19.8588 15.2651C21.4476 13.6763 22.1623 12.0917 22.1918 12.0251C22.2302 
              11.9387 22.25 11.8453 22.25 11.7508C22.25 11.6564 22.2302 11.563 22.1918 11.4766ZM12.125 
              17.15C9.52794 17.15 7.25909 16.2059 5.3809 14.3445C4.61028 13.5781 3.95464 12.7042 3.43437 
              11.75C3.95444 10.7957 4.6101 9.92172 5.3809 9.15547C7.25909 7.29416 9.52794 6.35 12.125 
              6.35C14.7221 6.35 16.9909 7.29416 18.8691 9.15547C19.6412 9.92159 20.2983 10.7955 20.8198 
              11.75C20.2115 12.8857 17.5613 17.15 12.125 17.15ZM12.125 7.7C11.324 7.7 10.541 7.93753 
              9.87494 8.38255C9.20892 8.82757 8.68982 9.46009 8.38328 10.2001C8.07675 10.9402 7.99655 
              11.7545 8.15282 12.5401C8.30909 13.3257 8.69481 14.0474 9.26121 14.6138C9.82762 15.1802 
              10.5493 15.5659 11.3349 15.7222C12.1205 15.8785 12.9348 15.7983 13.6749 15.4917C14.4149 
              15.1852 15.0474 14.6661 15.4925 14.0001C15.9375 13.334 16.175 12.551 16.175 11.75C16.1739 
              10.6762 15.7468 9.64674 14.9876 8.88745C14.2283 8.12817 13.1988 7.70112 12.125 7.7ZM12.125 
              14.45C11.591 14.45 11.069 14.2917 10.625 13.995C10.1809 13.6983 9.83488 13.2766 9.63052 
              12.7833C9.42617 12.2899 9.3727 11.747 9.47688 11.2233C9.58106 10.6995 9.83821 10.2184 
              10.2158 9.84082C10.5934 9.46321 11.0745 9.20606 11.5983 9.10188C12.122 8.9977 12.6649 
              9.05117 13.1582 9.25553C13.6516 9.45989 14.0733 9.80595 14.37 10.25C14.6666 10.694 14.825 
              11.216 14.825 11.75C14.825 12.4661 14.5405 13.1528 14.0342 13.6592C13.5278 14.1655 12.8411 
              14.45 12.125 14.45Z" fill="#5B4296"/>
            </svg>
        `;
    } else {
        // Закрытый глаз
        svgIcon.innerHTML = `
          <svg width="25" height="24" viewBox="0 0 25 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <g id="icon / 24x24 / eye closed">
        <path id="Vector" d="M22.5469 14.6062C22.4594 14.6561 22.3629 14.6882 22.263 14.7008C22.163
           14.7133 22.0616 14.7061 21.9645 14.6794C21.8674 14.6527 21.7765 14.6071 21.697 14.5453C21.6175
           14.4834 21.551 14.4065 21.5013 14.3189L19.6819 11.1399C18.6242 11.8551 17.4575 12.3938 16.2272
           12.7351L16.7892 16.1076C16.8058 16.2069 16.8027 16.3084 16.78 16.4065C16.7573 16.5046 16.7155 
           16.5972 16.657 16.6791C16.5985 16.761 16.5244 16.8306 16.439 16.8838C16.3535 16.9371 16.2585 
           16.973 16.1592 16.9895C16.1183 16.9962 16.077 16.9997 16.0357 17C15.8544 16.9997 15.6792 16.9352
           15.541 16.8179C15.4029 16.7006 15.3108 16.5382 15.2811 16.3594L14.7286 13.0483C13.5635 13.2104 
           12.3815 13.2104 11.2164 13.0483L10.6639 16.3594C10.6342 16.5385 10.5418 16.7012 10.4033 
           16.8186C10.2647 16.9359 10.089 17.0002 9.90745 17C9.8651 16.9998 9.82284 16.9963 9.78105 
           16.9895C9.68175 16.973 9.58668 16.9371 9.50127 16.8838C9.41585 16.8306 9.34177 16.761 9.28326
           16.6791C9.22474 16.5972 9.18294 16.5046 9.16025 16.4065C9.13756 16.3084 9.13441 16.2069 9.15099
           16.1076L9.71594 12.7351C8.48611 12.3927 7.32 11.853 6.26308 11.137L4.44951 14.3189C4.39921 
           14.4066 4.33214 14.4834 4.25213 14.5452C4.17212 14.6069 4.08074 14.6522 3.9832 14.6786C3.88566
           14.7051 3.78387 14.712 3.68365 14.6991C3.58343 14.6861 3.48674 14.6536 3.3991 14.6033C3.31145
           14.553 3.23457 14.4859 3.17285 14.4059C3.11112 14.3259 3.06576 14.2345 3.03935 14.137C3.01295
           14.0394 3.00601 13.9377 3.01894 13.8374C3.03187 13.7372 3.06441 13.6405 3.11471 13.5529L5.02977
           10.2015C4.35711 9.62037 3.73856 8.97939 3.18174 8.28645C3.11229 8.20892 3.05938 8.11805 3.02623
           8.01939C2.99307 7.92072 2.98037 7.81634 2.9889 7.71261C2.99744 7.60887 3.02702 7.50796 3.07584 
           7.41604C3.12467 7.32412 3.19171 7.24311 3.27289 7.17797C3.35406 7.11282 3.44766 7.0649 3.54797 
           7.03713C3.64828 7.00936 3.7532 7.00232 3.85632 7.01645C3.95944 7.03057 4.0586 7.06557 4.14775 
           7.11929C4.2369 7.17301 4.31416 7.24434 4.37482 7.32892C5.96433 9.29569 8.745 11.6378 12.9715 
           11.6378C17.1981 11.6378 19.9788 9.29282 21.5683 7.32892C21.6283 7.24261 21.7053 7.16957 21.7948 
           7.11433C21.8842 7.05909 21.984 7.02285 22.088 7.00784C22.192 6.99284 22.298 6.99941 22.3994 
           7.02713C22.5008 7.05485 22.5954 7.10314 22.6773 7.16899C22.7592 7.23483 22.8267 7.31683 22.8756
           7.40988C22.9244 7.50293 22.9536 7.60504 22.9613 7.70986C22.969 7.81467 22.9551 7.91995 22.9204
           8.01915C22.8856 8.11834 22.8309 8.20933 22.7595 8.28645C22.2026 8.97939 21.5841 9.62037 20.9114 
           10.2015L22.8265 13.5529C22.8779 13.6402 22.9114 13.7369 22.9252 13.8374C22.939 13.9378 22.9327 
           14.04 22.9067 14.1379C22.8807 14.2359 22.8355 14.3277 22.7737 14.4081C22.7119 14.4885 22.6348 
           14.5558 22.5469 14.6062Z" fill="#5B4296"/>
        </g>
        </svg>
        `;
    }

    eyeIcon.appendChild(svgIcon);
}
// Автоматическая инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', initAllModals);

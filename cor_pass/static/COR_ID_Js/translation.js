
/*




function setLanguage(language) {
    const elements = document.querySelectorAll("[data-translate]");
    elements.forEach(element => {
        const key = element.getAttribute("data-translate");
        if (translations[language] && translations[language][key]) {
            if (element.tagName === 'INPUT' && (element.type === 'text' || element.type === 'button')) {
                if (element.type === 'text') {
                    element.placeholder = translations[language][key];
                } else if (element.type === 'button') {
                    element.value = translations[language][key];
                }
            } else {
                element.textContent = translations[language][key];
            }
        }
    });
    localStorage.setItem('selectedLanguage', language);
}
*/

/*
function setLanguage(language) {
    const elements = document.querySelectorAll("[data-translate]");
    elements.forEach(element => {
        const key = element.getAttribute("data-translate");
        if (translations[language] && translations[language][key]) {
            if ((element.tagName === 'INPUT')||(element.tagName === 'password')) {
                if (element.type === 'text' || element.type === 'password') {
                    element.placeholder = translations[language][key];
                } else if (element.type === 'button') {
                    element.value = translations[language][key];
                }
            } else {
                element.textContent = translations[language][key];
            }
        }
    });
    localStorage.setItem('selectedLanguage', language);
}

*/
function setLanguage(language) {
    const elements = document.querySelectorAll("[data-translate]");
    elements.forEach(element => {
        const key = element.getAttribute("data-translate");

        // Проверяем, есть ли перевод для данного языка и ключа
        if (translations[language] && translations[language][key]) {
            const translation = translations[language][key];

            // Обработка разных типов элементов
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                // Для input и textarea обрабатываем placeholder и value
                if (element.type === 'text' || element.type === 'password' || element.type === 'email') {
                    element.placeholder = translation;
                } else if (element.type === 'button' || element.type === 'submit') {
                    element.value = translation;
                }
            } else if (element.tagName === 'SELECT') {
                // Для select переводим placeholder (disabled option)
                const placeholderOption = element.querySelector("option[disabled][selected]");
                if (placeholderOption) {
                    placeholderOption.textContent = translation;
                }
            } else if (element.tagName === 'OPTION') {
                // Для option заменяем текст
                element.textContent = translation;
            } else {
                // Для остальных элементов заменяем текстовое содержимое
                element.textContent = translation;
            }
        }
    });

    // Сохраняем выбранный язык в localStorage
    localStorage.setItem('selectedLanguage', language);
}




function switchLanguage(language) {
    setLanguage(language);
}

document.addEventListener('DOMContentLoaded', function() {
    const userLang = localStorage.getItem('selectedLanguage') || navigator.language || navigator.userLanguage;
    const defaultLang = userLang.startsWith('ru') ? 'ru' : 
                        userLang.startsWith('en') ? 'en' : 
                        userLang.startsWith('zh') ? 'zh' :
                        userLang.startsWith('uk') ? 'uk' :'ru';
    setLanguage(defaultLang);
});




const translations = {
    ru: {
        title: "Авторизация",
        "email-label": "Электронная почта:",
        "password-label": "Пароль:",
        "login-button": "Войти",
        "login-button-google": "Войти через Google",
        "login-button-facebook": "Войти через Facebook",
        "registration": "Регистрация",
        "registration-button": "Регистрация",
        "forgot-password-button": "Забыли пароль?",
        "message-ok": "Успешный вход",
        "message-error": "Произошла ошибка, пожалуйста, попробуйте снова",
        "confirmation-message": "Код подтверждения выслан Вам на имейл!",
        "error-message": "Произошла ошибка при отправке кода подтверждения на почту.",
        "send-code-on-male": "Отправить код на имейл",
        "invalid-code": "Неверный код, пожалуйста, попробуйте снова",
        "passwordsDoNotMatch": 'Пароли не совпадают!',
        "passwordsMatch": 'Пароли совпадают!',
        "password-requirements": "Пароль должен быть от 8 до 15 символов",
        "signup-title": "Регистрация",
        "confirm-password-label": "Подтвердите пароль:",
        "signup-button": "Зарегистрироваться",
        "password-message": "Пароль должен содержать от 8 до 15 символов",
        "verification-code-placeholder": "Введите код",
        "confirm-button": "Подтвердить",
        "send-again-countdown": "Отправить ещё через {countdown}с",
        "send-code-email": "Отправить код на имейл",
        "error-message": "Произошла ошибка при отправке кода подтверждения на почту.",
        "back-link-text": "<назад",
        "password-placeholder": "Введите пароль",
        "confirm-password-placeholder": "Подтвердите пароль",
        "confirmationMessage": "Ваша почта успешно подтверждена!",
        "registrationSuccess": 'Регистрация прошла успешно!',
        "heading" : "Сброс пароля",
        'loginSuccess': 'Вход выполнен успешно!',
        'password-changed': 'Пароль изменён!',
        'fillAllFields': "Заполните все поля",
        'login-error': 'Ошибка входа.',
        'recovery-button': 'Восстановить доступ',
        "recovery-modal-title": "Восстановление доступа",
        "recovery-modal-select-method": "Выберите способ восстановления:",
        "recovery-modal-super-password-btn": "Ввести супер-пароль",
        "recovery-modal-file-upload-btn": "Прикрепить файл",
        "recovery-modal-email-label": "Email:",
        "recovery-modal-super-password-label": "Супер-пароль:",
        "recovery-modal-recovery-file-label": "Файл восстановления:",
        "recovery-modal-send-btn": "Отправить",
        "recovery-modal-choose-file": "Выберите файл",
        "recovery-modal-no-file": "Файл не выбран",
        "no-account-text":"Нет аккаунта?",
        "password_placeholder": "Пароль",
        "gender-label": "Пол:",
        "female-option":"Женский",
        "male-option":"Мужской",
        "birth-year-placeholder":"Выберите год рождения",
        "LogOut-button": "Выйти",
        "welcome-message": "Приветствуем в COR-ID"
    },
    en: {
        title: "Authorization",
        "email-label": "Email:",
        "password-label": "Password:",
        "login-button": "Login",
        "login-button-google": "Login with Google",
        "login-button-facebook": "Login with Facebook",
        "registration": "Registration",
        "registration-button": "Register",
        "forgot-password-button": "Forgot Password?",
        "message-ok": "Successful Login",
        "message-error": "An error occurred, please try again",
        "confirmation-message": "Confirmation code sent to your email!",
        "error-message": "An error occurred while sending the verification code to your email.",
        "send-code-on-male": "Send code to email",
        "invalid-code": "Invalid code, please try again",
        "passwordsDoNotMatch": 'Passwords do not match!',
        "passwordsMatch": 'Passwords match!',
        "password-requirements": "Password must be 8 to 15 characters long",
        "signup-title": "Registration",
        "confirm-password-label": "Confirm Password:",
        "signup-button": "Sign Up",
        "password-message": "Password must be between 8 and 15 characters long",
        "verification-code-placeholder": "Enter code",
        "confirm-button": "Confirm",
        "send-again-countdown": "Send again in {countdown}s",
        "send-code-email": "Send code to email",
        "error-message": "An error occurred while sending the verification code to your email.",
        "back-link-text": "<<<back<<<",
        "password-placeholder": "Enter password",
        "confirm-password-placeholder": "Confirm password",
        "confirmationMessage" : "Your email has been successfully confirmed!",
        "registrationSuccess": 'Registration successful!',
        "heading" : "Password Reset",
        'loginSuccess': 'Login successful!',
        'password-changed': 'Password has been changed!',
        'fillAllFields': "Please fill out all fields",
        'login-error': 'Login error.',
        'recovery-button': 'Access Recovery',
        "recovery-modal-title": "Access Recovery",
        "recovery-modal-select-method": "Choose a recovery method:",
        "recovery-modal-super-password-btn": "Enter Super Password",
        "recovery-modal-file-upload-btn": "Attach Recovery File",
        "recovery-modal-email-label": "Email:",
        "recovery-modal-super-password-label": "Super Password:",
        "recovery-modal-recovery-file-label": "Recovery File:",
        "recovery-modal-send-btn": "Send",
        "recovery-modal-choose-file": "Choose File",
        "recovery-modal-no-file": "No file selected",
        "no-account-text":"Have no account?",
        "password_placeholder": "Password",
        "gender-label": "Gender:",
        "female-option":"Female",
        "male-option":"Male",
        "birth-year-placeholder":"Select year of birth" ,
        "LogOut-button": "Log Out",
        "welcome-message": "Welcome to COR-ID"
    },
    zh: {
        title: "授权",
        "email-label": "电子邮件：",
        "password-label": "密码：",
        "login-button": "登录",
        "login-button-google": "通过Google登录",
        "login-button-facebook": "通过Facebook登录",
        "registration": "注册",
        "registration-button": "注册",
        "forgot-password-button": "忘记密码？",
        "message-ok": "登录成功",
        "message-error": "发生错误，请重试",
        "confirmation-message": "确认码已发送至您的电子邮件",
        "error-message": "发送验证码到您的邮箱时出错。",
        "send-code-on-male": "发送验证码到邮箱",
        "invalid-code": "无效的验证码，请重试",
        "passwordsDoNotMatch": '密码不匹配!',
        "passwordsMatch": '密码匹配!',
        "password-requirements": "密码长度必须为8到15个字符",
        "signup-title": "注册",
        "confirm-password-label": "确认密码：",
        "signup-button": "注册",
        "password-message": "密码长度必须在8到15个字符之间",
        "verification-code-placeholder": "输入代码",
        "confirm-button": "确认",
        "send-again-countdown": "{countdown}秒后再发送",
        "send-code-email": "发送验证码到邮箱",
        "error-message": "发送验证码到您的邮箱时出错。",
        "back-link-text": "<<<返回<<<",
        "password-placeholder": "输入密码",
        "confirm-password-placeholder": "确认密码",
        "confirmationMessage" : "您的邮件已成功确认！",
        "registrationSuccess": '注册成功！',
        "heading" : "重设密码",
        'loginSuccess': '登录成功！',
        'password-changed': '密码已更改。',
        'fillAllFields': "请填写所有字段",
        'login-error': '登录错误。',
        'recovery-button': '恢复访问权限',
        "recovery-modal-title": "访问恢复",
        "recovery-modal-select-method": "选择恢复方式：",
        "recovery-modal-super-password-btn": "输入超级密码",
        "recovery-modal-file-upload-btn": "附加恢复文件",
        "recovery-modal-email-label": "电子邮件：",
        "recovery-modal-super-password-label": "超级密码：",
        "recovery-modal-recovery-file-label": "恢复文件：",
        "recovery-modal-send-btn": "发送",
        "recovery-modal-choose-file": "选择文件",
        "recovery-modal-no-file": "未选择文件",
        "no-account-text": "没有账户？",
        "password_placeholder": "密码",
        "gender-label": "性别:",
        "female-option":"女性",
        "male-option":"男性",
        "birth-year-placeholder":"选择出生年份" ,
        "LogOut-button": "退出",
        "welcome-message": "欢迎来到 COR-ID"
    },
    uk: {
        title: "Авторизація",
        "email-label": "Електронна пошта:",
        "password-label": "Пароль:",
        "login-button": "Увійти",
        "login-button-google": "Увійти через Google",
        "login-button-facebook": "Увійти через Facebook",
        "registration": "Реєстрація",
        "registration-button": "Зареєструватися",
        "forgot-password-button": "Забули пароль?",
        "message-ok": "Успішний вхід",
        "message-error": "Сталася помилка, спробуйте ще раз",
        "confirmation-message": "Код підтвердження відправлено на Вашу пошту",
        "error-message": "Сталася помилка під час відправлення коду підтвердження на електронну пошту.",
        "send-code-on-male": "Надіслати код на електронну пошту",
        "invalid-code": "Невірний код, спробуйте ще раз",
        "passwordsDoNotMatch": 'Паролі не співпадають!',
        "passwordsMatch": 'Паролі співпадають!',
        "password-requirements": "Пароль повинен бути від 8 до 15 символів",
        "signup-title": "Реєстрація",
        "confirm-password-label": "Підтвердіть пароль:",
        "signup-button": "Зареєструватися",
        "password-message": "Пароль має містити від 8 до 15 символів",
        "verification-code-placeholder": "Введіть код",
        "confirm-button": "Підтвердити",
        "send-again-countdown": "Надіслати знову через {countdown}с",
        "send-code-email": "Надіслати код на електронну пошту",
        "error-message": "Сталася помилка під час відправлення коду підтвердження на електронну пошту.",
        "back-link-text": "<<<назад<<<",
        "password-placeholder": "Введіть пароль",
        "confirm-password-placeholder": "Підтвердіть пароль",
        "confirmationMessage" : "Вашу пошту успішно підтверджено!",
        "registrationSuccess": 'Реєстрація пройшла успішно!',
        "heading" : "Скидання пароля",
        'loginSuccess': 'Вхід виконано успішно!',
        'password-changed': 'Пароль змінено!',
        'login-error': 'Помилка входу.',
        'recovery-button': 'Восстановить доступ',
        "recovery-modal-title": "Відновлення доступу",
        "recovery-modal-select-method": "Виберіть спосіб відновлення:",
        "recovery-modal-super-password-btn": "Ввести супер-пароль",
        "recovery-modal-file-upload-btn": "Прикріпити файл",
        "recovery-modal-email-label": "Електронна пошта:",
        "recovery-modal-super-password-label": "Супер-пароль:",
        "recovery-modal-recovery-file-label": "Файл відновлення:",
        "recovery-modal-send-btn": "Надіслати",
        "recovery-modal-choose-file": "Оберіть файл",
        "recovery-modal-no-file": "Файл не вибран",
        "no-account-text":"Немає акаунта?",
        "password_placeholder": "Пароль",
        "gender-label": "Стать:",
        "female-option":"Жіноча",
        "male-option":"Чоловіча",
        "birth-year-placeholder":"Оберіть рік народження" ,
        "LogOut-button": "Вийти",
        "welcome-message": "Вітаємо в COR-ID"
    },}
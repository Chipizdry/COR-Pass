

function sendVerificationCode() {
    const userLang = localStorage.getItem('selectedLanguage');
    var form = document.getElementById("registrationForm");
    var emailInput = form.elements.email;
    var messageDiv = document.getElementById("message");
    var confirmationMessageDiv = document.getElementById("confirmationMessage");
    var messageDivErr = document.getElementById('messageDivErr');
    var email = emailInput.value;
    const gender = document.getElementById('user_sex').value;       
    const birthYear = document.getElementById('birth').value;
    var sendCodeButton = document.getElementById('sendVerifCode');

    // Проверяем заполнены ли поля
    if (!gender || !birthYear) {
        messageDiv.innerText = translations[userLang]["fillAllFields"];
        messageDiv.style.color = 'red';
        return;
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/auth/send_verification_code");
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                console.log("Код подтверждения отправлен на вашу электронную почту.");
                confirmationMessageDiv.textContent = translations[userLang]["confirmation-message"];
                confirmationMessageDiv.style.color = "#5B4296";
                
                confirmationMessageDiv.classList.remove('hidden');
                messageDivErr.classList.add('hidden');
                messageDiv.classList.add('hidden');
                
                showVerificationCodeInput();
                document.getElementById('ConfirmationCodeInput').classList.remove('hidden');
                document.getElementById('gender-field').classList.add('hidden');
                document.getElementById('birth-year-field').classList.add('hidden');
                
                // Активируем все поля ввода OTP
                activateOTPFields();
                startCountdown(sendCodeButton, userLang);

            } else {
                var error = JSON.parse(xhr.responseText);
                console.error("Произошла ошибка при отправке кода подтверждения на почту.");
                messageDiv.innerText = error.detail || "Произошла ошибка при отправке кода подтверждения на почту.";
                messageDiv.style.color = 'red';
                confirmationMessageDiv.classList.add('hidden');
            }
        }
    };

    xhr.send(JSON.stringify({ email: email }));
}




function showVerificationCodeInput() {
    var verificationCodeWindow = document.getElementById("verificationCodeWindow");
    var otpContainer = document.querySelector(".otp-container");
    verificationCodeWindow.classList.remove("hidden");
    otpContainer.classList.remove("hidden");
    otpContainer.style.display = "flex";
}



function verifyVerificationCode() {
    const userLang = localStorage.getItem('selectedLanguage');
    var verificationCodeInput = document.getElementById("verificationCodeInput");

    let hiddenInput = document.getElementById("verificationCodeInput");
    let otpInputs = document.querySelectorAll(".otp-input");

    // Обновляем значение кода перед проверкой
    updateHiddenInput();

    var verificationCode = hiddenInput.value;
    var emailInput = document.getElementById("email");
    var confirmationMessageDiv = document.getElementById("confirmationMessage");
    var email = emailInput.value;
    var verificationCode = verificationCodeInput.value;

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/auth/confirm_email");
    xhr.setRequestHeader("Content-Type", "application/json");

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                confirmationMessageDiv.innerText = translations[userLang]["confirmationMessage"]; 
                confirmationMessageDiv.style.color = 'green';
                confirmationMessageDiv.classList.remove('hidden');
                
                console.log("Код подтверждения верный.");                     
                const containers = document.querySelectorAll('.password-container');
                containers.forEach(container => { container.classList.remove('hidden'); });
                
                document.getElementById('sendVerifCode').classList.add('hidden');
                document.getElementById('registration-button').classList.remove('hidden');
                document.getElementById('ConfirmationCodeInput').classList.add('hidden');
                document.getElementById('verificationCodeInput').classList.add('hidden');
                document.getElementById('verificationCodeWindow').classList.add('hidden');
                document.getElementById('message').classList.add('hidden');
                
            } else {
                console.error("Неверный код подтверждения.");
                confirmationMessageDiv.innerText = translations[userLang]["invalid-code"];
                confirmationMessageDiv.style.color = 'red';
                confirmationMessageDiv.classList.remove('hidden');
                
                const containers = document.querySelectorAll('.password-container');
                containers.forEach(container => { container.classList.add('hidden'); });
                
                setTimeout(function() {
                    verificationCodeInput.value = "";
                    confirmationMessageDiv.innerText = " ";
                }, 3000);
            }
        }
    };

    xhr.send(JSON.stringify({ email: email, verification_code: verificationCode }));
}




function activateOTPFields() {
    let otpInputs = document.querySelectorAll(".otp-input");
    
    otpInputs.forEach((input, index) => {
        input.disabled = false; // Активируем поле
        input.value = ''; // Очищаем поле
        
        // Добавляем обработчики событий для навигации
        input.addEventListener('input', function(e) {
            if (e.inputType === "deleteContentBackward") {
                // Если удаляем символ, переходим к предыдущему полю
                if (index > 0) {
                    otpInputs[index - 1].focus();
                }
            } else {
                // Если вводим символ, переходим к следующему полю
                if (index < otpInputs.length - 1 && this.value !== "") {
                    otpInputs[index + 1].focus();
                }
            }
            updateHiddenInput(); // Обновляем скрытое поле
        });
        
        // Обработчик для клавиш (для лучшей навигации)
        input.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft' && index > 0) {
                otpInputs[index - 1].focus();
            } else if (e.key === 'ArrowRight' && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus();
            }
        });
    });
    
    // Фокус на первое поле
    if (otpInputs.length > 0) {
        otpInputs[0].focus();
    }
}


// Функция обновления скрытого поля с кодом
function updateHiddenInput() {
    let otpInputs = document.querySelectorAll(".otp-input");
    let hiddenInput = document.getElementById("verificationCodeInput");

    if (!hiddenInput) {
        console.error("Ошибка: скрытое поле для кода не найдено.");
        return;
    }

    let code = Array.from(otpInputs).map(input => input.value).join("");
    hiddenInput.value = code;
}

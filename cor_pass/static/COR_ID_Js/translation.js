

/* Словарь должен быть объявлен до функций, которые его используют */
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
        "back-link-text": "<<<назад<<<",
        "password-placeholder": "Введите пароль",
        "confirm-password-placeholder": "Подтвердите пароль",
        "confirmationMessage": "Ваша почта успешно подтверждена!",
        "registrationSuccess": 'Регистрация прошла успешно!',
        "heading": "Сброс пароля",
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
        "no-account-text": "Нет аккаунта?",
        "password_placeholder": "Пароль",
        "gender-label": "Пол:",
        "female-option": "Женский",
        "male-option": "Мужской",
        "birth-year-placeholder": "Выберите год рождения",
        "LogOut-button": "Выйти",
        "welcome-message": "Приветствуем в COR-ID",
        "doc": "Врач",
        "lab": "Лаборант",
        "medCardPage": "Вся медкарта",
        "direction": "Направление",
        "tenderloin": "Вырезка",
        "glass": "Стекла",
        "conclusion": "Заключение",
        "exploration": "Исследования",
        "currentCases": "Текущие кейсы",
        "sign": "Подписать",
        "signature": "Подпись",
        "printReport": "Печать исследования",
        "createDoctorSign": "Создать подпись",
        "waitingSignatureQRTitle": "Вам необходимо подтвердить действие",
        "waitingSignatureQRDescription": "Пожалуйста, отсканируйте QR-код ниже и выполните все шаги подтверждения в приложении COR-ID.",
        "waitingSignatureQRLoading": "Ожидание...",
        "waitingSignatureQRBtn": "Подписать принудительно",
        "main-title-report": "Патоморфологическое исследование",
        "subtitle1": "МЕДИЦИНСКАЯ ДОКУМЕНТАЦИЯ 014/о",
        "subtitle2": "Утверждено приказом МОЗ Украины 29.05.2013 г. № 435",
        "reportType": "Патогистология",
        "biopsyDate": "Дата биопсии:",
        "arrivalDate": "Дата поступления:",
        "reportDate": "Дата окончания:",
        "patient": "Пациент:",
        "f": "Жен",
        "m": "Муж",
        "patientBirthDate": "Д/р:",
        "age": "Возраст: ",
        "yearsSuffix": "л.",
        "contact": "Контакты",
        "medCard": "Мед. карта:",
        "medCentre": "Мед. центр:",
        "medDepartment": "Отделение:",
        "attendingDoctor": "Лечащий врач:",
        "clinicalData": "Клинические данные:",
        "clinicalDiagnosis": "Клинический диагноз:",
        "containersAmount": "Количество контейнеров:",
        "received": "Получено",
        "declared": "Заявлено",
        "blocksAmount": "Количество блоков:",
        "fixation": "Фиксация:",
        "decalcification": "Декальцинация:",
        "macroarchive": "Макроархив:",
        "painting": "Окрашивание:",
        "macrodescription": "Макроскопическое описание: ",
        "microdescription": "Микроскопическое описание: ",
        "macrodes_short": "Макроописание: ",
        "microdes_short": "Микроописание: ",
        "immunohistochemicalProfile": "Иммуногистохимический профиль: ",
        "molecularGeneticProfile": "Молекулярно-генетический профиль: ",
        "pathomorphologicalDiagnosis": "Патогистологическое заключение: ",
        "comment": "Комментарий: ",
        "footer-right": "Документ создано ПО COR-Lab",
        "currentDoctor": "Врач: ",
        "date": "Дата: ",
        "owner": "Владелец: ",
        "ownCase": "Личный кейс",
        "takeCase": "Забрать кейс", 
        "icdCode": "Код ICD",
        "updateReport": "Обновить репорт",
        "conclusionUpdated": "Заключение успешно обновлено",
        "noReferrals": "У вас нет ни одного направления",
        "searchPlaceholder": "Поиск",
        "saveButton": "Сохранить",
        "microdesSuccess": "Микроописание успешно обновлено",
        "microdesDenial": "Чтобы записать микроописание, вы должны быть владельцем кейса.",
        "upload": "Загрузить",
        "excisionCommonParams": "Общие параметры вырезки",
        "sampleType": "Тип образцов",
        "macrodes": "Макроописание",
        "sample": "Образец",
        "withArchive": "с архивом",
        "withoutArchive": "без архива",
        "caseSettings": "Параметры кейса",
        "docPhotoScan": "Фото/скан документа",
        "scan": "Сканировать",
        "colorChangeSuccess": "Окраска стекла успешно изменена",
        "cassettesCreated": "Кассеты успешно созданы",
        "cassetteCreated": "Кассета успешно создана",
        "glassesCreated": "Стёкла успешно созданы",
        "glassCreated": "Стекло успешно создано",
        "expQRprinted": "QR исследования распечатан",
        "expCassettesPrinted": "Кассеты исследования распечатаны",
        "expGlassesPrinted": "Стёкла исследования распечатаны",
        "glassesPrinted": "Стёкла образца распечатаны",
        "cassettesScaned": "Кассета отсканирована",
        "glassPrinted": "Стекло распечатано",
        "casesDeleted": "Кейсы успешно удалены",
        "caseDeleted": "Кейс успешно удалён",
        "casesCreated": "Кейсы успешно созданы",
        "caseCreated": "Кейс успешно создан",
        "specimensDeleted": "Образцы успешно удалены",
        "specimenDeleted": "Образец успешно удалён",
        "specimensCreated": "Образцы успешно созданы",
        "specimenCreated": "Образец успешно создан",
        "cassettesDeleted": "Кассеты успешно удалены",
        "cassetteDeleted": "Кассета успешно удалена",
        "glassesDeleted": "Стёкла успешно удалены",
        "glassDeleted": "Стекло успешно удалено",
        "macrodesSuccess": "Макроописание успешно обновлено"
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
        "back-link-text": "<<<back<<<",
        "password-placeholder": "Enter password",
        "confirm-password-placeholder": "Confirm password",
        "confirmationMessage": "Your email has been successfully confirmed!",
        "registrationSuccess": 'Registration successful!',
        "heading": "Password Reset",
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
        "no-account-text": "Have no account?",
        "password_placeholder": "Password",
        "gender-label": "Gender:",
        "female-option": "Female",
        "male-option": "Male",
        "birth-year-placeholder": "Select year of birth",
        "LogOut-button": "Log Out",
        "welcome-message": "Welcome to COR-ID",
        "doc": "Doctor",
        "lab": "Lab Assistant",
        "medCardPage": "Full medical record",
        "direction": "Referral",
        "tenderloin": "Tissue Section",
        "glass": "Slides",
        "conclusion": "Conclusion",
        "exploration": "Examination",
        "currentCases": "Current Cases",
        "sign": "Sign",
        "signature": "Signature",
        "printReport": "Print Report",
        "createDoctorSign": "Create Signature",
        "waitingSignatureQRTitle": "Action confirmation required",
        "waitingSignatureQRDescription": "Please scan the QR-code below and complete all verification steps in the COR-ID application",
        "waitingSignatureQRLoading": "Waiting...",
        "waitingSignatureQRBtn": "Force Signature",
        "main-title-report": "Pathomorphological Examination",
        "subtitle1": "MEDICAL DOCUMENTATION FORM No. 014/o",
        "subtitle2": "Approved by the Order of the Ministry of Health of Ukraine No. 435 dated 29.05.2013",
        "reportType": "Pathohistology",
        "biopsyDate": "Biopsy Date:",
        "arrivalDate": "Specimen Received:",
        "reportDate": "Report Completed:",
        "patient": "Patient:",
        "f": "Female",
        "m": "Male",
        "patientBirthDate": "DOB:",
        "age": "Age: ",
        "yearsSuffix": "y.o.",
        "contact": "Contact Info",
        "medCard": "Medical record No.:",
        "medCentre": "Medical Facility:",
        "medDepartment": "Department:",
        "attendingDoctor": "Attending Doctor:",
        "clinicalData": "Clinical Data:",
        "clinicalDiagnosis": "Clinical Diagnosis:",
        "containersAmount": "Number of Containers:",
        "received": "Received",
        "declared": "Declared",
        "blocksAmount": "Number of Blocks:",
        "fixation": "Fixation:",
        "decalcification": "Decalcification:",
        "macroarchive": "Macro Archive:",
        "painting": "Staining Methods:",
        "macrodescription": "Macrodescription: ",
        "microdescription": "Microdescription: ",
        "macrodes_short": "Macrodescription: ",
        "microdes_short": "Microdescription: ",
        "immunohistochemicalProfile": "Immunohistochemical Profile: ",
        "molecularGeneticProfile": "Molecular-genetic profile: ",
        "pathomorphologicalDiagnosis": "Pathohistological Diagnosis: ",
        "comment": "Comment: ",
        "footer-right": "Document generated by COR-Lab software",
        "currentDoctor": "Doctor: ",
        "date": "Date: ",
        "owner": "Owner: ",
        "ownCase": "Assigned Case",
        "takeCase": "Take Case", 
        "icdCode": "Code ICD",
        "updateReport": "Update Report",
        "conclusionUpdated": "Conclusion successfully updated",
        "noReferrals": "You have no referrals",
        "searchPlaceholder": "Search",
        "saveButton": "Save",
        "microdesSuccess": "Microdescription successfully updated",
        "microdesDenial": "To save a microdescription, you must be the case owner.",
        "upload": "Upload",
        "excisionCommonParams": "Section parameters",
        "sampleType": "Sample type",
        "macrodes": "Macroscopic description",
        "sample": "Sample",
        "withArchive": "with archive",
        "withoutArchive": "without archive",
        "caseSettings": "Case settings",
        "docPhotoScan": "Document photo/scan",
        "scan": "Scan",
        "colorChangeSuccess": "Slide color successfully changed",
        "cassettesCreated": "Cassettes successfully created",
        "cassetteCreated": "Cassette successfully created",
        "glassesCreated": "Slides successfully created",
        "glassCreated": "Slide successfully created",
        "expQRprinted": "Research QR printed",
        "expCassettesPrinted": "Research cassettes printed",
        "expGlassesPrinted": "Research slides printed",
        "glassesPrinted": "Sample slides printed",
        "cassettesScaned": "Cassette scanned",
        "glassPrinted": "Slide printed",
        "casesDeleted": "Cases successfully deleted",
        "caseDeleted": "Case successfully deleted",
        "casesCreated": "Cases successfully created",
        "caseCreated": "Case successfully created",
        "specimensDeleted": "Specimens successfully deleted",
        "specimenDeleted": "Specimen successfully deleted",
        "specimensCreated": "Specimens successfully created",
        "specimenCreated": "Specimen successfully created",
        "cassettesDeleted": "Cassettes successfully deleted",
        "cassetteDeleted": "Cassette successfully deleted",
        "glassesDeleted": "Slides successfully deleted",
        "glassDeleted": "Slide successfully deleted",
        "macrodesSuccess": "Macrodescription successfully updated"
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
        "back-link-text": "<<<返回<<<",
        "password-placeholder": "输入密码",
        "confirm-password-placeholder": "确认密码",
        "confirmationMessage": "您的邮件已成功确认！",
        "registrationSuccess": '注册成功！',
        "heading": "重设密码",
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
        "female-option": "女性",
        "male-option": "男性",
        "birth-year-placeholder": "选择出生年份",
        "LogOut-button": "退出",
        "welcome-message": "欢迎来到 COR-ID",
        "doc": "医生",
        "lab": "实验技师",
        "medCardPage": "完整病历",
        "direction": "转诊单",
        "tenderloin": "组织切片",
        "glass": "载玻片",
        "conclusion": "结论",
        "exploration": "检查",
        "currentCases": "当前病例",
        "sign": "签名",
        "signature": "签名",
        "printReport": "打印报告",
        "createDoctorSign": "创建签名",
        "waitingSignatureQRTitle": "需要确认操作",
        "waitingSignatureQRDescription": "请扫描下方二维码并在 COR-ID 应用中完成所有验证步骤",
        "waitingSignatureQRLoading": "等待中...",
        "waitingSignatureQRBtn": "强制签名",
        "main-title-report": "病理形态学检查报告",
        "subtitle1": "医疗文档表格编号 014/o",
        "subtitle2": "根据乌克兰卫生部 2013 年 5 月 29 日第 435 号命令批准",
        "reportType": "病理组织学",
        "biopsyDate": "活检日期：",
        "arrivalDate": "样本接收日期：",
        "reportDate": "报告完成日期：",
        "patient": "患者：",
        "f": "女",
        "m": "男",
        "patientBirthDate": "出生日期：",
        "age": "年龄：",
        "yearsSuffix": "岁",
        "contact": "联系方式",
        "medCard": "病历号：",
        "medCentre": "医疗机构：",
        "medDepartment": "科室：",
        "attendingDoctor": "主治医生：",
        "clinicalData": "临床资料：",
        "clinicalDiagnosis": "临床诊断：",
        "containersAmount": "样本容器数量：",
        "received": "已接收",
        "declared": "申报内容",
        "blocksAmount": "石蜡块数量：",
        "fixation": "固定：",
        "decalcification": "脱钙：",
        "macroarchive": "宏观档案：",
        "painting": "染色方法：",
        "macrodescription": "宏观描述：",
        "microdescription": "显微描述：",
        "macrodes_short": "宏观描述: ",
        "microdes_short": "显微描述: ",
        "immunohistochemicalProfile": "免疫组化特征：",
        "molecularGeneticProfile": "分子遗传特征：",
        "pathomorphologicalDiagnosis": "病理组织学诊断：",
        "comment": "备注：",
        "footer-right": "由 COR-Lab 软件生成的文件",
        "currentDoctor": "医生：",
        "date": "日期：",
        "owner": "负责人：",
        "ownCase": "分配病例",
        "takeCase": "领取病例",
        "icdCode": "ICD 编码",
        "updateReport": "更新报告",
        "conclusionUpdated": "结论已成功更新",
        "noReferrals": "您没有任何转诊单",
        "searchPlaceholder": "搜索",
        "saveButton": "保存",
        "microdesSuccess": "微描述已成功更新",
        "microdesDenial": "要保存微描述，您必须是案例所有者。",
        "upload": "上传",
        "excisionCommonParams": "切取参数",
        "sampleType": "样本类型",
        "macrodes": "宏观描述",
        "sample": "样本",
        "withArchive": "带存档",
        "withoutArchive": "无存档",
        "caseSettings": "病例参数",
        "docPhotoScan": "文件照片/扫描",
        "scan": "扫描",
        "colorChangeSuccess": "载玻片颜色已成功更改",
        "cassettesCreated": "盒已成功创建",
        "cassetteCreated": "盒已成功创建",
        "glassesCreated": "载玻片已成功创建",
        "glassCreated": "载玻片已成功创建",
        "expQRprinted": "研究 QR 已打印",
        "expCassettesPrinted": "研究盒已打印",
        "expGlassesPrinted": "研究载玻片已打印",
        "glassesPrinted": "样本载玻片已打印",
        "cassettesScaned": "盒已扫描",
        "glassPrinted": "载玻片已打印",
        "casesDeleted": "病例已成功删除",
        "caseDeleted": "病例已成功删除",
        "casesCreated": "病例已成功创建",
        "caseCreated": "病例已成功创建",
        "specimensDeleted": "样本已成功删除",
        "specimenDeleted": "样本已成功删除",
        "specimensCreated": "样本已成功创建",
        "specimenCreated": "样本已成功创建",
        "cassettesDeleted": "盒已成功删除",
        "cassetteDeleted": "盒已成功删除",
        "glassesDeleted": "载玻片已成功删除",
        "glassDeleted": "载玻片已成功删除",
        "macrodesSuccess": "宏观描述已成功更新"
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
        "back-link-text": "<<<назад<<<",
        "password-placeholder": "Введіть пароль",
        "confirm-password-placeholder": "Підтвердіть пароль",
        "confirmationMessage": "Вашу пошту успішно підтверджено!",
        "registrationSuccess": 'Реєстрація пройшла успішно!',
        "heading": "Скидання пароля",
        'loginSuccess': 'Вхід виконано успішно!',
        'password-changed': 'Пароль змінено!',
        'login-error': 'Помилка входу.',
        'recovery-button': 'Відновити доступ',
        "recovery-modal-title": "Відновлення доступу",
        "recovery-modal-select-method": "Виберіть спосіб відновлення:",
        "recovery-modal-super-password-btn": "Ввести супер-пароль",
        "recovery-modal-file-upload-btn": "Прикріпити файл",
        "recovery-modal-email-label": "Електронна пошта:",
        "recovery-modal-super-password-label": "Супер-пароль:",
        "recovery-modal-recovery-file-label": "Файл відновлення:",
        "recovery-modal-send-btn": "Надіслати",
        "recovery-modal-choose-file": "Оберіть файл",
        "recovery-modal-no-file": "Файл не вибрано",
        "no-account-text": "Немає акаунта?",
        "password_placeholder": "Пароль",
        "gender-label": "Стать:",
        "female-option": "Жіноча",
        "male-option": "Чоловіча",
        "birth-year-placeholder": "Оберіть рік народження",
        "LogOut-button": "Вийти",
        "welcome-message": "Вітаємо в COR-ID",
        "doc": "Лікар",
        "lab": "Лаборант",
        "medCardPage": "Вся медкартка",
        "direction": "Направлення",
        "tenderloin": "Вирізка",
        "glass": "Скельця",
        "conclusion": "Заключення",
        "exploration": "Дослідження",
        "currentCases": "Поточні кейси",
        "sign": "Підписати",
        "signature": "Підпис",
        "printReport": "Друкувати дослідження",
        "createDoctorSign": "Створити підпис",
        "waitingSignatureQRTitle": "Вам необхідно підтвердити дію",
        "waitingSignatureQRDescription": "Будь ласка, відскануйте QR-код нижче та виконайте всі кроки підтвердження в додатку COR-ID",
        "waitingSignatureQRLoading": "Очікування...",
        "waitingSignatureQRBtn": "Підписати примусово",
        "main-title-report": "Патоморфологічне дослідження",
        "subtitle1": "МЕДИЧНА ДОКУМЕНТАЦІЯ 014/о",
        "subtitle2": " Затверджена наказом МОЗ України 29.05.2013 р. № 435",
        "reportType": "Патогістологія",
        "biopsyDate": "Дата біопсії:",
        "arrivalDate": "Дата надходження:",
        "reportDate": "Дата завершення:",
        "patient": "Пацієнт:",
        "f": "Жін",
        "m": "Чол",
        "patientBirthDate": "Д/н:",
        "age": "Вік: ",
        "yearsSuffix": "р.",
        "contact": "Контакти",
        "medCard": "Медична карта:",
        "medCentre": "Медичний заклад:",
        "medDepartment": "Відділення:",
        "attendingDoctor": "Лікар-куратор:",
        "clinicalData": "Клінічні дані:",
        "clinicalDiagnosis": "Клінічний діагноз:",
        "containersAmount": "Кількість контейнерів:",
        "received": "Отримано",
        "declared": "Заявлено",
        "blocksAmount": "Кількість блоків:",
        "fixation": "Фіксація:",
        "decalcification": "Декальцинація:",
        "macroarchive": "Макроархів:",
        "painting": "Фарбування:",
        "macrodescription": "Макроскопічний опис: ",
        "microdescription": "Мікроскопічний опис: ",
        "macrodes_short": "Макроопис: ",
        "microdes_short": "Мікроопис: ",
        "immunohistochemicalProfile": "Імуногістохімічний профіль: ",
        "molecularGeneticProfile": "Молекулярно-генетичний профіль: ",
        "pathomorphologicalDiagnosis": "Патогістологічний висновок: ",
        "comment": "Коментар: ",
        "footer-right": "Документ створено ПЗ COR-Lab",
        "currentDoctor": "Лікар: ",
        "date": "Дата: ",
        "owner": "Власник: ",
        "ownCase": "Особистий кейс",
        "takeCase": "Забрати кейс",
        "icdCode": "Код ICD",
        "updateReport": "Оновити репорт",
        "conclusionUpdated": "Заключення успішно оновлено",
        "noReferrals": "У вас немає жодного направлення",
        "searchPlaceholder": "Пошук",
        "saveButton": "Зберегти",
        "microdesSuccess": "Мікроопис успішно оновлений",
        "microdesDenial": "Для того, щоб записати мікроопис, Ви повинні бути власником кейсу.",
        "upload": "Завантажити",
        "excisionCommonParams": "Загальні параметри вирізки",
        "sampleType": "Тип зразків",
        "macrodes": "Макроопис",
        "sample": "Зразок",
        "withArchive": "з архівом",
        "withoutArchive": "без архіву",
        "caseSettings": "Параметри кейсу",
        "docPhotoScan": "Фото/скан документу",
        "scan": "Сканувати",
        "colorChangeSuccess": "Забарвлення скельця успішно зміненно",
        "cassettesCreated": "Касети успішно створені",
        "cassetteCreated": "Касета успішно створена",
        "glassesCreated": "Скельця успішно створені",
        "glassCreated": "Скельце успішно створено",
        "expQRprinted": "QR дослідження роздруковано",
        "expCassettesPrinted": "Касети дослідження роздруковані",
        "expGlassesPrinted": "Скельця дослідження роздруковані",
        "glassesPrinted": "Скельця зразка роздруковані",
        "cassettesScaned": "Касета відсканована",
        "glassPrinted": "Скельце роздруковано",
        "casesDeleted": "Кейси успішно видалені",
        "caseDeleted": "Кейс успішно видалено",
        "casesCreated": "Кейси успішно створені",
        "caseCreated": "Кейс успішно створено",
        "specimensDeleted": "Зразки успішно видалені",
        "specimenDeleted": "Зразок успішно видалено",
        "specimensCreated": "Зразки успішно створені",
        "specimenCreated": "Зразок успішно створено",
        "cassettesDeleted": "Касети успішно видалені",
        "cassetteDeleted": "Касета успішно видалена",
        "glassesDeleted": "Скельця успішно видалені",
        "glassDeleted": "Скельце успішно видалено",
        "macrodesSuccess": "Макроопис успішно оновлений"
    }
}


/**
 * Получает сохранённый язык из localStorage
 * или выбирает язык по настройкам браузера.
 */

 function getSavedLang() {
   const saved = localStorage.getItem('selectedLanguage');
   if (saved && translations?.[saved]) return saved;

   const userLang = String(navigator.language || navigator.userLanguage || 'ru').toLowerCase();

  // Базовый код языка до дефиса (например, 'en-US' → 'en')
  const base = userLang.split('-')[0];
  // Определяем язык на основе кода

let picked =
    base.startsWith('uk') ? 'uk' :
    base.startsWith('en') ? 'en' :
    base.startsWith('zh') ? 'zh' :
    base.startsWith('ru') ? 'ru' : 'ru';

    return picked;
}
/**
 * Сохраняет выбранный язык в localStorage
 */
function setSavedLang(lang) {
   localStorage.setItem('selectedLanguage', lang);
}

// ----------------------------------------
// Перевод узла и всех его дочерних элементов
// ----------------------------------------

/**
 * Переводит указанный элемент (и его потомков),
 * у которых есть атрибут data-translate.
 *
 * @param {HTMLElement} node - элемент, в котором выполняется перевод
 * @param {string} language - выбранный язык
 */


function translateNodeDeep(node, language) {
  if (!(node instanceof HTMLElement)) return;
  const dict = translations?.[language];
  if (!dict) return;

  const list = node.matches?.('[data-translate]')
    ? [node, ...node.querySelectorAll('[data-translate]')]
    : node.querySelectorAll?.('[data-translate]');

  list?.forEach((el) => {
    const key = el.getAttribute('data-translate');
    const t = dict[key];
    if (!t) return;

    const tag = el.tagName;
    const type = (el.getAttribute('type') || '').toLowerCase();

    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      if (type === 'text' || type === 'password' || type === 'email' || type === '') {
        el.placeholder = t;
      } else if (type === 'button' || type === 'submit') {
        el.value = t;
      } else {
        el.placeholder = t;  // на случай нестандартных input-типов
      }
    } else if (tag === 'SELECT') {
      const ph = el.querySelector('option[disabled][selected]');
      if (ph) ph.textContent = t;
    } else if (tag === 'OPTION') {
      el.textContent = t;
    } else {
      el.textContent = t;
    }
  });
}


// ------------------------------
// Установка языка для всей страницы
// ------------------------------

/**
 * Устанавливает язык интерфейса и переводит все элементы.
 */


function setLanguage(language) {
  if (!translations?.[language]) return;
  document.querySelectorAll('[data-translate]').forEach((el) => translateNodeDeep(el, language));
  setSavedLang(language);
}

// ------------------------------
// Защита от ошибок (fallback)
// ------------------------------

/**
 * Если функция не определена, создаём пустую,
 * чтобы не вызвать ошибку при поздней инициализации.
 */


if (!window.setLanguage) {
  window.setLanguage = function(){};
}

// ------------------------------
// Публичные API-функции
// ------------------------------


function switchLanguage(language) { setLanguage(language); }
function applySavedLanguage() { setLanguage(getSavedLang()); }

// ------------------------------
// Автоматический перевод при изменениях DOM
// ------------------------------

/**
 * Следит за добавлением новых элементов в DOM и автоматически переводит их.
 */


let __langObserverStarted = false;
function startTranslationObserver() {
  if (__langObserverStarted) return;
  __langObserverStarted = true;

  const observer = new MutationObserver((mutations) => {
    const lang = getSavedLang();
    mutations.forEach((m) => m.addedNodes.forEach((node) => translateNodeDeep(node, lang)));
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

// ------------------------------
// Безопасная инициализация при загрузке
// ------------------------------

/**
 * Выполняет инициализацию перевода после полной загрузки DOM.
 * Также убирает CSS-класс i18n-loading, если он использовался для скрытия контента.
 */

(function safeLateInit() {
  document.addEventListener('DOMContentLoaded', () => {
    try {
      applySavedLanguage();
      startTranslationObserver();
    } finally {
      document.documentElement.classList.remove('i18n-loading');
    }
  });
})();

// ------------------------------
// Автоматическая инициализация при старте
// ------------------------------


try {
  applySavedLanguage();
  window.__i18nReady = true;
  document.dispatchEvent(new Event('i18n:ready'));
} catch (e) {
  console.error('i18n failed:', e);
  window.__i18nReady = false;
}


// ------------------------------
// Экспорт функций в глобальную область
// ------------------------------


window.getSavedLang = getSavedLang;
window.setSavedLang = setSavedLang;
window.setLanguage = setLanguage;
window.switchLanguage = switchLanguage;
window.applySavedLanguage = applySavedLanguage;
window.startTranslationObserver = startTranslationObserver;
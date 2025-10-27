const DEFAULT_ALERT_TIME = 5000;
const ALERT_STATUSES = {
    "SUCCESS": {
        title: "Успіх",
        icon: (`
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="24" height="24" rx="12" fill="#49AC26"/>
            <path d="M16.8296 8.27305C17.0223 8.45522 17.1347 8.70645 17.1422 8.97152C17.1497 9.23658 17.0517 9.49377 16.8696 9.68655L11.2023 15.6872C11.1104 15.7843 11 15.862 10.8777 15.9157C10.7553 15.9694 10.6234 15.998 10.4897 15.9999C10.3561 16.0018 10.2235 15.9768 10.0996 15.9266C9.97579 15.8763 9.86329 15.8017 9.76877 15.7072L6.76842 12.7069C6.59176 12.5173 6.49558 12.2666 6.50016 12.0075C6.50473 11.7484 6.60969 11.5011 6.79293 11.3179C6.97617 11.1347 7.22337 11.0297 7.48247 11.0251C7.74157 11.0206 7.99233 11.1167 8.18192 11.2934L10.4555 13.5657L15.4161 8.31306C15.5983 8.12036 15.8495 8.0079 16.1145 8.0004C16.3796 7.9929 16.6368 8.09097 16.8296 8.27305Z" fill="white"/>
        </svg>
        `)
    },
    "INFO": {
        title: "Інформація",
        icon: (`
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="24" height="24" rx="12" fill="#7B43F2"/>
            <path d="M11 11C11 10.4477 11.4477 10 12 10C12.5523 10 13 10.4477 13 11V16C13 16.5523 12.5523 17 12 17C11.4477 17 11 16.5523 11 16V11Z" fill="white"/>
            <path d="M13 8C13 8.55228 12.5523 9 12 9C11.4477 9 11 8.55228 11 8C11 7.44772 11.4477 7 12 7C12.5523 7 13 7.44772 13 8Z" fill="white"/>
        </svg>
        `),
    },
    "ERROR": {
        title: "Помилка",
        icon: (`
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="24" height="24" rx="12" fill="#DF1125"/>
            <path d="M14.8691 7.72437C15.2618 7.40402 15.8408 7.42662 16.207 7.79273C16.5731 8.15885 16.5957 8.73785 16.2753 9.13063L16.207 9.2068L13.414 11.9998L16.207 14.7927L16.2753 14.8689C16.5957 15.2617 16.5731 15.8407 16.207 16.2068C15.8408 16.5729 15.2618 16.5955 14.8691 16.2752L14.7929 16.2068L11.9999 13.4138L9.20696 16.2068C8.81643 16.5973 8.18342 16.5973 7.79289 16.2068C7.40237 15.8163 7.40237 15.1833 7.79289 14.7927L10.5859 11.9998L7.79289 9.2068L7.72453 9.13063C7.40418 8.73785 7.42678 8.15885 7.79289 7.79273C8.15901 7.42662 8.73801 7.40402 9.13078 7.72437L9.20696 7.79273L11.9999 10.5857L14.7929 7.79273L14.8691 7.72437Z" fill="white"/>
        </svg>
        `),
    },
    "WARNING": {
        title: "Попередження",
        icon: (`
        <svg width="26" height="24" viewBox="0 0 26 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10.9864 2.16875C11.8768 0.610416 14.1238 0.610416 15.0143 2.16875L24.9348 19.5296C25.8184 21.0759 24.7018 23 22.9208 23H3.07985C1.29882 23 0.182245 21.0759 1.06589 19.5296L10.9864 2.16875Z" fill="#F8A441"/>
            <path d="M12 15C12 15.5523 12.4477 16 13 16C13.5523 16 14 15.5523 14 15V10C14 9.44772 13.5523 9 13 9C12.4477 9 12 9.44772 12 10V15Z" fill="white"/>
            <path d="M14 18C14 17.4477 13.5523 17 13 17C12.4477 17 12 17.4477 12 18C12 18.5523 12.4477 19 13 19C13.5523 19 14 18.5523 14 18Z" fill="white"/>
        </svg>
        `),
    }
}



const alertTemplate = (text, alertStatus, duration) => {

    let alertTimeOut = null
    const div = document.createElement('div')
    div.classList = "alertWrapper df"
    div.innerHTML = `
    ${alertStatus.icon}
    <div>
        <div class="alertTitle">
            ${alertStatus.title}
        </div>
        <div class="alertDescription">
            ${text}
        </div>
    </div>
    <div class="alertClose">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M18.6872 5.31275C19.1042 5.72975 19.1042 6.40584 18.6872 6.82284L6.82284 18.6873C6.40584 19.1042 5.72975 19.1042 5.31275 18.6873C4.89575 18.2702 4.89575 17.5942 5.31275 17.1772L17.1772 5.31275C17.5942 4.89575 18.2702 4.89575 18.6872 5.31275Z" fill="#B1A1DA"/>
            <path fill-rule="evenodd" clip-rule="evenodd" d="M18.6873 18.6873C18.2702 19.1042 17.5942 19.1042 17.1772 18.6873L5.31275 6.82284C4.89575 6.40584 4.89575 5.72975 5.31275 5.31275C5.72975 4.89575 6.40584 4.89575 6.82284 5.31275L18.6873 17.1772C19.1042 17.5942 19.1042 18.2702 18.6873 18.6873Z" fill="#B1A1DA"/>
        </svg>
    </div>
    `

    div.querySelector('.alertClose').addEventListener('click', () => {
        clearTimeout(alertTimeOut)
        div.remove()
    })

    document.body.append(div)

    alertTimeOut = setTimeout(() => {
        div.remove()
    }, duration || DEFAULT_ALERT_TIME)
}

const showSuccessAlert = (text, duration) => {
    alertTemplate(text, ALERT_STATUSES.SUCCESS, duration)
}

const showErrorAlert = (text, duration) => {
    alertTemplate(text, ALERT_STATUSES.ERROR, duration)
}

const showInfoAlert = (text, duration) => {
    alertTemplate(text, ALERT_STATUSES.INFO, duration)
}

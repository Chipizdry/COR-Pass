const API_BASE_URL = "https://dev-corid.cor-medical.ua";
// const API_BASE_URL = "http://localhost:8000";
const ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvaWQiOiJkYTFhNGYwNy0yODI0LTQyMWEtYmY0OC00NjhiOWQ4ZGVmYjEiLCJjb3JpZCI6IjE1MzM0OFROMS0xOTk0TSIsInJvbGVzIjpbImFkbWluIiwibGF3eWVyIiwiZG9jdG9yIiwiYWN0aXZlX3VzZXIiXSwiaWF0IjoxNzQ4NDQ2MTk4LCJleHAiOjUzNDg0NDYxOTgsInNjcCI6ImFjY2Vzc190b2tlbiIsImp0aSI6ImNjYmU1YzU4LWJkOTAtNDNmZC04NmYyLTZhYzcwNTcxNTM4MCJ9.RE50AEsl6ZgjuMMJTNIo5cjDuSLZI4uJr8_IU-6vZec";


const glassPaintList = [
    {
        id: "H&E",
        name: "H&E",
        short: "H&E",
    },
    {
        id: "Alcian PAS",
        name: "Alcian Pas",
        short: "AP",
    },
    {
        id: "Congo red",
        name: "Congo red",
        short: "CR",
    },
    {
        id: "Masson Trichrome",
        name: "Masson Trichrome",
        short: "MT",
    },
    {
        id: "van Gieson",
        name: "Van Gieson",
        short: "VG",
    },
    {
        id: "Ziehl Neelsen",
        name: "Ziehl Neelsen",
        short: "ZN",
    },
    {
        id: "Warthin-Starry Silver",
        name: "Warthin-Starry Silver",
        short: "WSS",
    },
    {
        id: "Grocott's Methenamine Silver",
        name: "Grocott's Methenamine Silver",
        short: "GMS",
    },
    {
        id: "Toluidine Blue",
        name: "Toluidine Blue",
        short: "TB",
    },
    {
        id: "Perls Prussian Blue",
        name: "Perls Prussian Blue",
        short: "PPB",
    },
    {
        id: "PAMS",
        name: "PAMS",
        short: "PAMS",
    },
    {
        id: "Picrosirius",
        name: "Picrosirius",
        short: "P",
    },
    {
        id: "Sirius red",
        name: "Sirius red",
        short: "SR",
    },
    {
        id: "Thioflavin T",
        name: "Thioflavin T",
        short: "TT",
    },
    {
        id: "Trichrome AFOG",
        name: "Trichrome AFOG",
        short: "TA",
    },
    {
        id: "von Kossa",
        name: "Von Kossa",
        short: "VK",
    },
    {
        id: "Giemsa",
        name: "Giemsa",
        short: "G",
    },
    {
        id: "Other",
        name: "Other",
        short: "O",
    },
]

const getImages = async (fileUrl) => {
    if(!fileUrl){
        return null
    }

    return fetch(`${API_BASE_URL}/api${fileUrl}`, {
        method: "GET",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
    })
        .then(response => response.blob())
        .then(blob => {
            return blob
        })
}

const getGlassImages = async (currentGlass) => {
    if(!currentGlass?.id || !currentGlass.preview_url){
        return null
    }

    return fetch(`${API_BASE_URL}/api/glasses/${currentGlass.id}/preview`, {
        method: "GET",
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
    })
        .then(res => res.blob())
        .then((blob) => {
            return blob
        })
}

const decodeTokenJWT = (token) => {
    if(!token){
        return null
    }

    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (error) {
        console.error("Failed to decode token:", error);
        return null;
    }
}

const getShortName = (lastName, firstName, middleName) => {
    let result = `${lastName} `;

    if(firstName){
        result += `${firstName.slice(0, 1)}.`
    }
    if(middleName){
        result += `${middleName.slice(0, 1)}.`
    }

    return result;
}

const getCaseColor = (currentCase) => {
    if(isCaseIsClosed(currentCase?.grossing_status)){
        return "#49AC26"
    }

    if(currentCase?.grossing_status === "PROCESSING"){
        return "#F8A441"
    }

    return "#5B4296"
}

const getItemCountByAllKeys = (entity, keys = []) => {
    let currentLevel = [entity];

    return keys.reduce((counts, key) => {
        const nextLevel = currentLevel.flatMap(item => item[key] || []);

        counts[key] = nextLevel.length;
        currentLevel = nextLevel;
        return counts;
    }, {});
}


const showTextareaButton = (textareaId) => {
    const textareaNODE = document.querySelector(`#${textareaId}`);
    textareaNODE?.addEventListener('focus', () => {
        textareaNODE.nextElementSibling.classList.add('open');
    })
}


const getAge = (birthDate) => {
    const today = new Date();
    const birth = new Date(birthDate); // Can accept string like '2000-01-01'

    let age = today.getFullYear() - birth.getFullYear();

    // Check if the birthday has occurred this year
    const hasHadBirthdayThisYear =
        today.getMonth() > birth.getMonth() ||
        (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());

    if (!hasHadBirthdayThisYear) {
        age--;
    }

    return age;
}


const isCaseIsClosed = (grossingStatus) => {
    return ["IN_SIGNING_STATUS", "COMPLETED"].includes(grossingStatus)
}

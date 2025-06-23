const API_BASE_URL = "https://dev-corid.cor-medical.ua";
const ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvaWQiOiJkYTFhNGYwNy0yODI0LTQyMWEtYmY0OC00NjhiOWQ4ZGVmYjEiLCJjb3JpZCI6IjE1MzM0OFROMS0xOTk0TSIsInJvbGVzIjpbImFkbWluIiwibGF3eWVyIiwiZG9jdG9yIiwiYWN0aXZlX3VzZXIiXSwiaWF0IjoxNzQ4NDQ2MTk4LCJleHAiOjUzNDg0NDYxOTgsInNjcCI6ImFjY2Vzc190b2tlbiIsImp0aSI6ImNjYmU1YzU4LWJkOTAtNDNmZC04NmYyLTZhYzcwNTcxNTM4MCJ9.RE50AEsl6ZgjuMMJTNIo5cjDuSLZI4uJr8_IU-6vZec";

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
    textareaNODE.addEventListener('focus', () => {
        textareaNODE.nextElementSibling.style.display = "block";
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

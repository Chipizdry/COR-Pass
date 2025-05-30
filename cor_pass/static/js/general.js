const PATIENT_COR_ID = "1GSVPC5PX-2000M";
const ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvaWQiOiJkYTFhNGYwNy0yODI0LTQyMWEtYmY0OC00NjhiOWQ4ZGVmYjEiLCJjb3JpZCI6IjE1MzM0OFROMS0xOTk0TSIsInJvbGVzIjpbImFkbWluIiwibGF3eWVyIiwiZG9jdG9yIiwiYWN0aXZlX3VzZXIiXSwiaWF0IjoxNzQ3MjE0ODE0LCJleHAiOjUzNDcyMTQ4MTQsInNjcCI6ImFjY2Vzc190b2tlbiJ9.IZrSncxvOpq1rZQCYFVxPhya1bSV7GIWungEYWn6_BU";
const API_BASE_URL = "https://dev-corid.cor-medical.ua";

const getItemCountByAllKeys = (entity, keys = []) => {
    let currentLevel = [entity];

    return keys.reduce((counts, key) => {
        const nextLevel = currentLevel.flatMap(item => item[key] || []);

        counts[key] = nextLevel.length;
        currentLevel = nextLevel;
        return counts;
    }, {});
}

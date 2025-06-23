document.addEventListener("DOMContentLoaded", (event) => {
    //CREATE CASSETTE
    document.querySelectorAll('.modal').forEach(elem => {
        elem.addEventListener( "click", (e) => {
            const element = e.target;
            if(element.classList.contains("modal")){
                element.classList.remove('open')
            }
        })
    })
});

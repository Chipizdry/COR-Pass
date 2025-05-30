document.addEventListener("DOMContentLoaded", (event) => {
    //CREATE CASSETTE
    document.querySelector('.modal').addEventListener( "click", (e) => {
        const element = e.target;

        if(element.classList.contains("modal")){
            element.classList.remove('open')
        }
    })
});

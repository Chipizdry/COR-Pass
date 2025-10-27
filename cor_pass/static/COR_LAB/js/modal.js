document.addEventListener("DOMContentLoaded", (event) => {
    //CREATE CASSETTE
    document.querySelectorAll('.modalCustom').forEach(elem => {
        console.log(elem, '1')
        elem.addEventListener( "click", (e) => {
            const element = e.target;
            const modalWrapper = e.currentTarget;

            if(element.classList.contains("modalCustom")){
                modalWrapper.classList.remove('open')
            }
        })
    })
});




  /* ========== Автозаполнение данных (localStorage) ========== */
  function autoFillStep1Fields() {
    console.log("Автозаполнение полей шага 1...");
    const gender = localStorage.getItem('userGender');
    const birthYear = localStorage.getItem('userBirthYear');
  
    const genderInput = document.getElementById('gender');
    if (genderInput && gender) {
      genderInput.value = (gender === 'M') ? 'Мужской' : 'Женский';
    }
  
    const birthYearInput = document.getElementById('birthYear');
    if (birthYearInput && birthYear) birthYearInput.value = birthYear;
  }



    /* ========== Image drag & zoom (single init per image instance) ========== */
    function initImageDragAndZoom(img) {
      if (!img) return;
      // не навешиваем дублирующиеся обработчики
      if (img.__dragZoomInitialized) return;
      img.__dragZoomInitialized = true;
    
      let isDragging = false;
      let startX = 0, startY = 0, translateX = 0, translateY = 0, scale = 1;
    
      img.style.cursor = 'grab';
      img.addEventListener('mousedown', function (e) {
        isDragging = true;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
        img.style.cursor = 'grabbing';
        e.stopPropagation();
      });
    
      window.addEventListener('mousemove', function (e) {
        if (isDragging) {
          translateX = e.clientX - startX;
          translateY = e.clientY - startY;
          img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
        }
      });
    
      window.addEventListener('mouseup', function () {
        isDragging = false;
        img.style.cursor = 'grab';
      });
    
      // wheel: explicit passive: false because we call preventDefault
      img.addEventListener('wheel', function (e) {
        e.preventDefault();
        scale *= e.deltaY < 0 ? 1.1 : 0.9;
        img.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
        e.stopPropagation();
      }, { passive: false });
    }



    
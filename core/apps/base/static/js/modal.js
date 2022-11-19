document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn_modal');
    const vist_modal = document.getElementById('modal_vist');
    const conten = document.getElementById('cont_mod');
  

    btn.addEventListener('click', () => {
        vist_modal.style.opacity = "0";
        vist_modal.style.visibility = "hidden";
        conten.style.transform = "translateY(-30%)";
    });
  });

const emailInput = document.getElementById('id_digitaCorreo-email');
const icon1 = document.querySelector(".icon1");
const icon2 = document.querySelector(".icon2");
const error = document.querySelector(".text-error");

emailInput.addEventListener('input', () => {
  const emails = emailInput.value.split(/,\s*/);
  const validEmails = [];

  for (const email of emails) {
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      validEmails.push(email);
    }
  }

  if (validEmails.length === 0) {
    emailInput.style.borderColor="lightgrey";
    emailInput.style.background ="#fff";
        icon1.style.display ="none";
        icon2.style.display ="none";
        error.style.display ="none";
  } else if (validEmails.length === emails.length) {
    emailInput.style.borderColor="#27ae60";
    emailInput.style.background="#eafaf1";
        icon1.style.display ="none";
        icon2.style.display ="block";
        error.style.display ="none";
  } else {
    emailInput.style.borderColor="#e74c3c";
    emailInput.style.background="#fceae9";
        icon1.style.display ="block";
        icon2.style.display ="none";
        error.style.display ="block";
  }
});


document.getElementById("btn_final").addEventListener("click", cargad);
const carga_ds = document.getElementById("load_a") ;

function cargad() {

        carga_ds.style.opacity = "1";
        carga_ds.style.visibility = "visible";
    
};

const imgLogoElement = document.getElementById("logo-loader");
Loadgo.init(imgLogoElement);

Loadgo.loop(document.getElementById('logo-loader'), 10);

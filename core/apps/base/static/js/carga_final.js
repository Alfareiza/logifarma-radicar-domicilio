const carga_ds = document.getElementById("load_a") ;
const correo = document.getElementById("id_digitaCorreo-email");
const regExp = /^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-4])?\.)+[a-z0-4](?:[a-z0-4-]*[a-z0-4])?$/;

const icon1 = document.querySelector(".icon1");
const icon2 = document.querySelector(".icon2");
const error = document.querySelector(".text-error");

document.getElementById("btn_final").addEventListener("click", cargad);

function corrvali() {
    if (correo.value.match(regExp)) {
        correo.style.borderColor="#27ae60";
        correo.style.background="#eafaf1";
        icon1.style.display ="none";
        icon2.style.display ="block";
        error.style.display ="none";
    }else{
        correo.style.borderColor="#e74c3c";
        correo.style.background="#fceae9";
        icon1.style.display ="block";
        icon2.style.display ="none";
        error.style.display ="block";
    }

    if (correo.value=="") {
        correo.style.borderColor="lightgrey";
        correo.style.background ="#fff";
        icon1.style.display ="none";
        icon2.style.display ="none";
        error.style.display ="none";
    }
};

function letra(e) {
    key=e.keyCode || e.which;
    teclado = String.fromCharCode(key).toLowerCase();
    letras =" abcdefghijklmnñopqrstuvwxyz";
    especiales = "8-37-38-46-164";
    teclado_especial = false;
    for(var i in especiales){
        if (key==especiales[i]) {
            teclado_especial=true;break;
        }
        if (letras.indexOf(teclado)==-1 && !teclado_especial) {
            return false;
        }
    }
};

function cargad() {

        carga_ds.style.opacity = "1";
        carga_ds.style.visibility = "visible";
    
    

};


const imgLogoElement = document.getElementById("logo-loader");
Loadgo.init(imgLogoElement);

Loadgo.loop(document.getElementById('logo-loader'), 10);

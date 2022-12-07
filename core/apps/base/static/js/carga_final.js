
const carga_ds = document.getElementById("load_a") ;

document.getElementById("btn_final").addEventListener("click", cargad);

function cargad() {
    
let campo = document.getElementById("id_digitaCorreo-email");
let regExp = /^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-4])?\.)+[a-z0-4](?:[a-z0-4-]*[a-z0-4])?$/;

    if (campo.value.match(regExp)) {

        carga_ds.style.opacity = "1";
        carga_ds.style.visibility = "visible";
    } else {
        carga_ds.style.opacity = "0";
    carga_ds.style.visibility = "hidden";
    }
    

};

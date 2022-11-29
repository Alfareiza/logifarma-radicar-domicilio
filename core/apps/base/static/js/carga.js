
const carga = document.getElementById("btn_carga") ;

document.getElementById("btn_conti").addEventListener("click", cargar);

function cargar() {
    
    carga.style.display = "block";
};


const carga_ds = document.getElementById("load_a") ;

document.getElementById("btn_final").addEventListener("click", cargad);

function cargad() {
    carga_ds.style.opacity = "1";
    carga_ds.style.visibility = "visible";
}
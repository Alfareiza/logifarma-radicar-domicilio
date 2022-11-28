
const carga = document.getElementById('btn_carga') ;

document.getElementById('btn_conti').addEventListener("click", cargar);

function cargar() {
    carga.style.display = "block";
}

const carga_ds = document.getElementById('load_a') ;

document.getElementById('btn_btn_final').addEventListener("click", cargadd);

function cargadd() {
    carga_ds.style.opacity = "1";
    carga_ds.style.visibility = "visible";
}
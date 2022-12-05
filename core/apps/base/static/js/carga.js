
const carga = document.getElementById("btn_carga") ;

document.getElementById("btn_conti").addEventListener("click", cargar);

function cargar() {

    let campo = document.getElementById("id_autorizacionServicio-num_autorizacion");
    if (campo < 8) {
        carga.style.display = "none"; 
    } else {
        carga.style.display = "block";
    }
    
};


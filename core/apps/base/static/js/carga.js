

function cargar() {
    let carga = document.getElementById("btn_carga") ;
    
        carga.style.display = "block";
    
};


function cargar_aut() {
    let carga = document.getElementById("btn_carga") ;
    let camp = document.getElementById("id_autorizacionServicio-num_autorizacion").value;
    
    if (camp > 100000) {

        carga.style.display = "block";
    }else{

        carga.style.display = "none";
    };
};


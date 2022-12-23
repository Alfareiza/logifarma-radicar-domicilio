const carga = document.getElementById("btn_carga") ;

function cargar2() {

    /* let inp = document.getElementById('id_digitaDireccionBarrio-direccion').addEventListener("keyup"); */

    if ($('.select_opt').is(':checked')) {
        
    if($('#id_digitaDireccionBarrio-direccion').val().length != 0){

        carga.style.display = "block";

    }else{
        carga.style.display = "none";
    }
}

};

function cargar3() {
    let numvali = document.getElementById("id_digitaCelular-celular");

    if (numvali.value < 1000000000) {
        
        carga.style.display = "none";
    }else{
        carga.style.display = "block";
    }
};

function cargar4() {
    
    carga.style.display = "block";

};

function cargar5() {
    /* let selecheck = document.getElementsByClassName("select_opt"); */

    if ($('.select_opt').is(':checked') ) {
        
        carga.style.display = "block";
    }else{
        carga.style.display = "none";
    }
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


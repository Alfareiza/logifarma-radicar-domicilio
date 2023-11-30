const carga = document.getElementById("btn_carga") ;
const cargahome = document.getElementById("btn_carga_home") ;

function animabotoncarga_direccion() {

    /* let inp = document.getElementById('id_digitaDireccionBarrio-direccion').addEventListener("keyup"); */

    if ($('.select_opt').is(':checked')) {
        
    if($('#id_digitaDireccionBarrio-direccion').val().length != 0){

        carga.style.display = "block";

    }else{
        carga.style.display = "none";
    }
}

};

function animabotoncarga_celular() {
    let numvali = document.getElementById("id_digitaCelular-celular");

    if (numvali.value < 1000000000) {
        
        carga.style.display = "none";
    }else{
        carga.style.display = "block";
    }
};

function animabotoncarga_home() {
    
    cargahome.style.display = "block";

};

function animabotoncarga_general() {
    
    carga.style.display = "block";

};

function animabotoncarga_municipio() {
    /* let selecheck = document.getElementsByClassName("select_opt"); */

    if ($('.select_opt').is(':checked') ) {
        
        carga.style.display = "block";
    }else{
        carga.style.display = "none";
    }
};


function animabotoncarga_autorizacion() {
    let carga = document.getElementById("btn_carga") ;
    let camp = document.getElementById("id_autorizacionServicio-num_autorizacion").value;
    
    if (camp > 100000) {

        carga.style.display = "block";
    }else{

        carga.style.display = "none";
    };
};

function animabotoncarga_sin_autorizacion() {
    let carga = document.getElementById("btn_carga") ;
    let camp = document.getElementById("id_sinAutorizacion-identificacion").value;

    if($('#id_sinAutorizacion-identificacion').val().length >= 6){
    console.log('adlkfajsh;ljs')
        carga.style.display = "block";
    }else{

        carga.style.display = "none";
    };
};

function animabotoncarga_correo() {
    let carga = document.getElementById("btn_carga") ;
    // let camp = document.getElementById("id_digitaCorreo-email").value;

    if($('id_digitaCorreo-email').val().length >= 6){
    console.log('adlkfajsh;ljs')
        carga.style.display = "block";
    }else{

        carga.style.display = "none";
    };
};
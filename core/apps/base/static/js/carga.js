const carga = document.getElementById("btn_carga") ;

function cargar() {
    let combo = document.getElementById("id_eligeMunicipio-municipio");
    let selected = combo.options[combo.selectedIndex].text;

    if (selected == "Seleccione un municipio") {
        
        carga.style.display = "none";
    }else{
        carga.style.display = "block";
    }
};


function cargar2() {
    let combo = document.getElementById("id_digitaDireccionBarrio-barrio");
    let selected = combo.options[combo.selectedIndex].text;

    let inp = document.querySelector('#id_digitaDireccionBarrio-direccion');

    if (inp.value != 0) {
        
    if(selected != "Seleccione el barrio"){

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


function cargar_aut() {
    let carga = document.getElementById("btn_carga") ;
    let camp = document.getElementById("id_autorizacionServicio-num_autorizacion").value;
    
    if (camp > 100000) {

        carga.style.display = "block";
    }else{

        carga.style.display = "none";
    };
};


$(window).ready(function() {
$("#form-id").on("keypress", function (event) {
    var keyPressed = event.keyCode || event.which;
    if (keyPressed === 13) {
        //alert("You pressed the Enter key!!");
        event.preventDefault();
        $('#btn_conti').click();
        return false;
    }
});
});

box_o = document.getElementById("elecci");
escri = document.getElementById("escri");
cover = document.getElementById("cover-ctn-search");

try {

    document.getElementById("escri").addEventListener("keyup", buscador_interno);

$('.labelfil').click(function() {
    var esteLi = $(this).text();
    $('#escri').val(esteLi);
  });

function buscador_interno(){

    function removeAccents(str) {
        return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
      }

    filter = escri.value.toUpperCase();
    li = box_o.getElementsByTagName("div");

    //Recorriendo elementos a filtrar mediante los "li"
    for (i = 0; i < li.length; i++){

        a = li[i].getElementsByTagName("label")[0];
        textValue = a.textContent || a.innerText;


        if(removeAccents(textValue.toUpperCase()).indexOf(removeAccents(filter)) > -1){

            li[i].style.display = "";
            box_o.style.display = "block";

            if (escri.value === ""){
                box_o.style.display = "block";
            }

        }else{
            li[i].style.display = "none";
        }
    };
};
    
} catch (error) {
    
}


const btnPageTwo = document.getElementById('btn_final');

btnPageTwo.addEventListener('click', function() {
  
  const timestamp = Date.now();

  localStorage.setItem('timestamp', timestamp);
});

const savedTimestamp = localStorage.getItem('timestamp');

function  verificarTiempo(){

    if (savedTimestamp) {

        const elapsedTime = (Date.now() - savedTimestamp) / 1000;
      
        if (elapsedTime >= 1800) {
          localStorage.removeItem('timestamp');
      
          window.location.href = "/";
        };
      };

};

setInterval(verificarTiempo, 5000);



const inp_whatsapp = document.getElementById("id_digitaCelular-whatsapp");
const inp_numero = document.getElementById("id_digitaCelular-celular");
const error_vacio = document.getElementById("error_vacio");
const error_celu = document.getElementById("error_celu");

function habilitarcampo() {

    const check_whatsapp = document.getElementById("btn-switch");

    if (check_whatsapp.checked) {

        if ( inp_numero.value !== "" ) {

            if (inp_numero.value > 1000000000 && inp_numero.value < 10000000000) {

                inp_whatsapp.value = inp_numero.value;
                inp_whatsapp.disabled = true;
                error_vacio.style.display = "none";
                error_celu.style.display = "none";

           }else{

            check_whatsapp.checked = false;
            error_celu.style.display = "block";
           }

        }else {
            check_whatsapp.checked = false;
            error_vacio.style.display = "block";
        }
        
    } else{
        inp_whatsapp.value = "";
        inp_whatsapp.disabled = false;
    }

    

  };
  
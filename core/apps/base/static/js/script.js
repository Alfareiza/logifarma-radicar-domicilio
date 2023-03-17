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


    filter = escri.value.toUpperCase();
    li = box_o.getElementsByTagName("div");

    //Recorriendo elementos a filtrar mediante los "li"
    for (i = 0; i < li.length; i++){

        a = li[i].getElementsByTagName("label")[0];
        textValue = a.textContent || a.innerText;


        if(textValue.toUpperCase().indexOf(filter) > -1){

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


const btnPageTwo = document.getElementById('btn_conti');

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
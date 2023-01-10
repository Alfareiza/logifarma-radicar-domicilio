$(window).ready(function() {
$("#form-id").on("keypress", function (event) {
    var keyPressed = event.keyCode || event.which;
    if (keyPressed === 13) {
        //alert("You pressed the Enter key!!");
        event.preventDefault();
        $('#btn_con').click();
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


document.addEventListener("DOMContentLoaded", () => {
    // click del botón
    const $boton = document.querySelector("#btnCrearPdf");
    $boton.addEventListener("click", () => {
        const $elementoParaConvertir = document.querySelector("#vista11"); // elemento del DOM
        html2pdf()
            .set({
                margin: 0,
                filename: 'Radicado.pdf',
                image: {
                    type: 'jpeg',
                    quality: 0.98
                },
                html2canvas: {
                    scale: 3, // resolucion
                    letterRendering: true,
                },
                jsPDF: {
                    unit: "in",
                    format: "a3",
                    orientation: 'portrait' // landscape o portrait
                }
            })
            .from($elementoParaConvertir)
            .save()
            .catch(err => console.log(err));
    });
});
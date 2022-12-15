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

$(document).ready(function () {
    $('select').selectize({
        sortField: 'text'
    });
});
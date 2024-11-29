document.addEventListener('DOMContentLoaded', () => {

    try {
        var vist_modal = document.getElementById('modal_vist');
        var conten = document.getElementById('cont_mod');
    } catch(error) {
        console.error('btn "conten" or "modal_vist" with error: ' + error);
    }

    function hideModal() {
        vist_modal.style.opacity = "0";
        vist_modal.style.visibility = "hidden";
        conten.style.transform = "translateY(-30%)";
    }

    try {
        var btn = document.getElementById('btn_modal');
        btn.addEventListener('click', () => {
            hideModal();
        });
    } catch(error) {
        console.error('btn "btn" with error: ' + error);
    }

    try {
        var entiendo = document.getElementById('entiendo');
        entiendo.addEventListener('click', () => {
            hideModal();
        });
    } catch(error) {
        console.error('btn "entiendo" with error: ' + error);
    }

    try {
        document.getElementById('new_formula').addEventListener('click', function () {
        // Create a hidden input field dynamically
        const flagInput = document.createElement('input');
        flagInput.type = 'hidden';
        flagInput.name = 'flag_new_formula'; // Send the flag via POST
        flagInput.value = '1';
        flagInput.id = 'temp_flag_input'; // Add an ID for easy removal
        // hide modal
        vist_modal.style.opacity = "0";
        vist_modal.style.visibility = "hidden";
        conten.style.transform = "translateY(-30%)";
        // Append the flag input to the form
        const form = document.getElementById('form-id');
        form.appendChild(flagInput);

        // Trigger the submit button click
        document.getElementById('btn_conti').click();
      });
    } catch (error) {
        console.error(error)
    }

});


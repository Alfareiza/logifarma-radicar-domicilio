document.addEventListener('DOMContentLoaded', () => {
    try {
        document.getElementById('new_formula').addEventListener('click', function () {
        // Create a hidden input field dynamically
        const flagInput = document.createElement('input');
        flagInput.type = 'hidden';
        flagInput.name = 'flag_new_formula'; // Send the flag via POST
        flagInput.value = '1';
        flagInput.id = 'temp_flag_input'; // Add an ID for easy removal
        // hide modal
        const dialog = document.getElementById("error-modal");
        const closeBtn = document.getElementById("entiendo");
        closeBtn.addEventListener("click", () => {
            dialog.close(); // closes the modal
        });
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


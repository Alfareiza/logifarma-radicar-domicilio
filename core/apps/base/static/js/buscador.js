document.addEventListener('DOMContentLoaded', function() {
    let searchButton = document.querySelector('.card-block button[type="submit"]');
//    var searchInput = document.getElementById('icon-search');
    let cardBlock = document.querySelector('.card-block');

    const baseUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8001' // Development URL
        : 'https://domicilios.logifarma.com.co'; // Production URL

    searchButton.addEventListener('click', function(event) {
        event.preventDefault(); // Evita la recarga de la página al hacer clic en el botón

        let searchInput = document.getElementById('icon-search');
        let searchButton = document.querySelector('.card-block button[type="submit"]');

        documento = searchInput.value.trim();
        if (documento) {
            const apiUrl = `${baseUrl}/api/v1/radicaciones/?paciente_cc=${documento}`;
            searchInput.value = documento;
            searchButton.disabled = true;

            // Mostrar el spinner
            cardBlock.innerHTML = `
                <div class="row justify-content-center">
                    <div class="col-sm-3">
                        <input type="text" id="icon-search" class="form-control mb-4"
                               placeholder="Digita el numero de documento " value="${documento}">
                    </div>
                    <div class="col-sm-2">
                        <button type="submit" class="btn btn-primary mb-2 disabled">Submit</button>
                    </div>
                </div>
                <div class="d-flex justify-content-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                </div>
            `;

            fetch(apiUrl)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    // Limpiar el contenido actual del card-block
                    cardBlock.innerHTML = `
                        <div class="row justify-content-center">
                            <div class="col-sm-3">
                                <input type="text" id="icon-search" class="form-control mb-4"
                                       placeholder="Digita el numero de documento " value="${documento}">
                            </div>
                            <div class="col-sm-2">
                                <button type="submit" class="btn btn-primary mb-2">Submit</button>
                            </div>
                        </div>
                    `;
                    renderizarTabla(data.results, cardBlock);
                    // Volver a agregar el event listener al nuevo botón
                    const newSearchButton = cardBlock.querySelector('button[type="submit"]');
                    newSearchButton.addEventListener('click', arguments.callee); // Reutilizar la misma función
                })
                .catch(error => {
                    console.error('Error al llamar a la API:', error);
                    cardBlock.innerHTML = `
                        <div class="row justify-content-center">
                            <div class="col-sm-3">
                                <input type="text" id="icon-search" class="form-control mb-4"
                                       placeholder="Digita el numero de documento " value="${documento}">
                            </div>
                            <div class="col-sm-2">
                                <button type="submit" class="btn btn-primary mb-2">Submit</button>
                            </div>
                        </div>
                    `;
                    // Volver a agregar el event listener al nuevo botón en caso de error
                    const newSearchButton = cardBlock.querySelector('button[type="submit"]');
                    newSearchButton.addEventListener('click', arguments.callee); // Reutilizar la misma función
                });
        } else {
            alert('Por favor, digita el número de documento.');
        }
    });

    function renderizarTabla(radicados, contenedor) {
        if (radicados && radicados.length > 0) {
            const tablaHTML = `
                <div class="table-responsive mt-3">
                    <table id="myTable" class="table table-hover display">
                        <thead>
                        <tr>
                            <th>Numero radicado</th>
                            <th>Celular</th>
                            <th>Municipio/Departamento</th>
                            <th>Fecha de radicado</th>
                            <th>Más</th>
                        </tr>
                        </thead>
                        <tbody>
                            ${radicados.map(rad => `
                                <tr class="unread">
                                    <td>
                                        <h6 class="m-0">${rad.numero_radicado}</h6>
                                        <p class="mb-1">${rad.paciente_nombre}</p>
                                    </td>
                                    <td>
                                        <h6 class="mb-1">${rad.cel_uno}</h6>
                                        <h6 class="text-muted">${rad.cel_dos || ''}</h6>
                                    </td>
                                    <td>
                                        <h6 class="mb-1">${rad.municipio.name || ''} / ${rad.municipio.departamento || ''}</h6>
                                        <h6 class="mb-1">${rad.direccion || ''}</h6>
                                    </td>
                                    <td>
                                        <h6 class="text-muted">
                                            ${new Date(rad.datetime).toLocaleDateString()} ${new Date(rad.datetime).toLocaleTimeString().slice(0, 5)}
                                        </h6>
                                    </td>
                                    <td>
                                        ${rad.acta_entrega ? `<span class="label theme-bg text-white f-12">${rad.acta_entrega}</span>` : ''}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            contenedor.insertAdjacentHTML('beforeend', tablaHTML);
        } else {
            contenedor.insertAdjacentHTML('beforeend', `
                <div class="alert alert-info mt-3" role="alert">
                    No se encontraron radicaciones para el documento ingresado.
                </div>
            `);
        }
    }
});
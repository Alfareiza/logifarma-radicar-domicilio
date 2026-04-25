# Step-by-Step: Implementing a New "Convenio"

This guide outlines the necessary steps to integrate a new healthcare agreement (convenio) into the Domicilios project.

## 1. Identify and Model the Source of Information
The first step is determining where the convenio data resides and how to access it.

### 1.1 Source: Plain Files (TXT, CSV, XLSX)

If the information is provided in a static file:
- **Create a Model**: Define a new model in `core/apps/base/models.py` that represents the columns of the file.
- **Import Script**: Use an AI-generated script (or a manual one) to parse the file and insert the data into the database. 
- **Recommendation**: Always run and verify the script in a local environment before executing it against the production database.

### 1.2 Source: SAP Database
If the information is hosted on an internal SAP database:
- Integrate with the existing `SAP` class (usually found in `core/apps/base/resources/sap.py`).
- Implement the retrieval logic within the `SAP` class or a specific wrapper.

### 1.3 Source: External API
If the information is retrieved via an external API:
- **Dedicated Resource**: Create a new file in `core/apps/base/resources/` named after the convenio (e.g., `new_convenio.py`).
- **Class Implementation**: Implement a class similar to `MutualSerAPI` in `core/apps/base/resources/mutual_ser.py` to handle the API communication.
- **Centralize Calls**: Create a wrapper function inside `core/apps/base/resources/api_calls.py` to maintain the centralized structure for external requests.

### 1.4 Source: Web Scraping
If the information is only available via web scraping:
- Follow the same procedure as **Step 1.3**. Implement the scraping logic within a dedicated resource file and wrap it in `api_calls.py`.

---

## 2. Update Configuration (`settings.py`)
Add the new convenio to the `TIPO_USUARIO` mapping. This key is used throughout the application to route logic correctly.

```python
TIPO_USUARIO = {
    'c': 'proteger',
    'f': 'fomag',
    'm': 'mutualser',
    'fn': 'new_convenio', # Example key for the new provider
}
```

## 3. Centralize Lookup Logic (`api_calls.py`)
Regardless of the source, ensure there is a standard function to retrieve the data.

```python
def obtener_datos_identificacion_new_convenio(tipo: str, value: str) -> dict:
    # Logic to call model (1.1), SAP (1.2), API (1.3), or Scraper (1.4)
    # Must return a standardized dict: {'NOMBRE', 'PRIMER_NOMBRE', 'APELLIDO', 'status', ...}
```

## 4. Integrate with the Dispatcher (`proteger.py`)
Update `obtener_datos_identificacion` in `core/apps/base/resources/proteger.py` to include the new convenio entry.

```python
def obtener_datos_identificacion(eps: str, tipo: str, value: str) -> dict:
    func = {
        'proteger': obtener_datos_identificacion_proteger,
        'fomag': obtener_datos_identificacion_fomag,
        'foneca': obtener_datos_identificacion_foneca,
        'mutualser': obtener_datos_identificacion_mutual_ser,
        'new_convenio': obtener_datos_identificacion_new_convenio,
    }
    return func[eps](tipo, value)
```

## 5. UI and Form Updates
- **Assets**: Add the provider logo to `core/apps/base/static/img/`.
- **Home View**: Update `core/apps/base/templates/home.html` to present the new convenio as an option.
- **Form Logic**: Verify if `core/apps/base/forms.py` (specifically `SinAutorizacion`) requires special handling for the new provider.

## 6. Data Migration & Deployment
- **Database Schema**: Run `python manage.py makemigrations` and `python manage.py migrate` if a new model was created.
- **Data Load**: Execute the AI-generated import script to populate the local database if working with plain files.
- **Verification**: Test the full flow from the homepage to ensure the affiliate data is correctly identified and passed through the Wizard.

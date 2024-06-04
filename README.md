# firma_electronica_mid

API MID para la implementación de firma electronica.

## Especificaciones Técnicas

### Tecnologías Implementadas y Versiones
* [Flask (Python)](https://flask.palletsprojects.com/en/1.1.x/)


### Variables de Entorno
```shell
# parametros de api
API_PORT=[Puerto de exposición del API]
DOCUMENTOS_CRUD_URL=[URL API documentos_crud]
GESTOR_DOCUMENTAL=[URL API gestor_documental_mid]
```


**NOTA:** Las variables se pueden ver en el fichero api.py ...

### Ejecución del Proyecto
```shell
#1. Obtener el repositorio con git
git clone https://github.com/udistrital/firma_electronica_mid.git

#2. Moverse a la carpeta del repositorio
cd firma_electronica

# 3. Moverse a la rama **develop**
git pull origin develop && git checkout develop

# 4. alimentar todas las variables de entorno que utiliza el proyecto.
export API_PORT=8080 DOCUMENTOS_CRUD_URL=http://xxxxxxxxx/v1/ GESTOR_DOCUMENTAL_URL=http://xxxxxxxxx/v1/

# 5. instalar dependencias de python
pip install -r requirements.txt

# 6. Ejecutar el api
python api.py
```

### Documentacion

## Estado CI
| Develop | Relese 0.0.1 | Master |
| -- | -- | -- |
| [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica/status.svg?ref=refs/heads/develop)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica) | [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica/status.svg?ref=refs/heads/release/0.0.1)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica) | [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica/status.svg?ref=refs/heads/master)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica) |


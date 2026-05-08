# firma_electronica_mid

API MID para la implementación de firma electronica.

## Especificaciones Técnicas

### Tecnologías Implementadas y Versiones
* [Flask (Python)](https://flask.palletsprojects.com/en/1.1.x/)


### Variables de Entorno
```shell
# parametros de api
FIRMA_ELECTRONICA_MID_API_PORT=[Puerto de exposición del API]
FIRMA_ELECTRONICA_MID_DOCUMENTOS_CRUD_URL=[URL API documentos_crud]
FIRMA_ELECTRONICA_MID_GESTOR_DOCUMENTAL_URL=[URL API gestor_documental_mid]
FIRMA_ELECTRONICA_MID_VERIFICACION=[URL de verificación interna]
FIRMA_ELECTRONICA_MID_VERIFICACION_EXTERNA=[URL de verificación externa y destino del QR]
FIRMA_ELECTRONICA_MID_QR_SECRET_PROVIDER=[Proveedor de secretos, requerido; usar aws en prod]
FIRMA_ELECTRONICA_MID_QR_SECRET_NAME=[Nombre del secreto QR en AWS Secrets Manager, requerido si no se usa ARN]
FIRMA_ELECTRONICA_MID_QR_SECRET_ARN=[Opcional, ARN completo del secreto]
FIRMA_ELECTRONICA_MID_QR_SECRET_ACTIVE_VERSION=[Solo local/dev con provider=env]
FIRMA_ELECTRONICA_MID_QR_SECRET_VERSIONS_JSON=[Solo local/dev con provider=env: mapa version->secreto]
FIRMA_ELECTRONICA_MID_QR_SIGNING_SECRET=[Fallback legado/local]
FIRMA_ELECTRONICA_MID_RUN_MODE=[Modo de ejecución]
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
export FIRMA_ELECTRONICA_MID_API_PORT=8080
export FIRMA_ELECTRONICA_MID_DOCUMENTOS_CRUD_URL=http://xxxxxxxxx/v1/
export FIRMA_ELECTRONICA_MID_GESTOR_DOCUMENTAL_URL=http://xxxxxxxxx/v1/
export FIRMA_ELECTRONICA_MID_VERIFICACION=https://verificacion.interna
export FIRMA_ELECTRONICA_MID_VERIFICACION_EXTERNA=https://verificacion.externa
export FIRMA_ELECTRONICA_MID_QR_SECRET_PROVIDER=aws
export FIRMA_ELECTRONICA_MID_QR_SECRET_NAME=firma-electronica-mid/dev/qr-token
export FIRMA_ELECTRONICA_MID_RUN_MODE=dev

# 5. instalar dependencias de python
pip install -r requirements.txt

# 6. Ejecutar el api
python api.py
```

### Documentacion

## Estado CI
| Develop | Relese 0.0.1 | Master |
| -- | -- | -- |
| [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica_mid/status.svg?ref=refs/heads/develop)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica_mid) | [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica_mid/status.svg?ref=refs/heads/release/0.0.1)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica_mid) | [![Build Status](https://hubci.portaloas.udistrital.edu.co/api/badges/udistrital/firma_electronica_mid/status.svg?ref=refs/heads/master)](https://hubci.portaloas.udistrital.edu.co/udistrital/firma_electronica_mid) |
 

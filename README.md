# firma_electronica_mid

API MID para la implementación de firma electrónica.

## Variables de Entorno

```shell
API_PORT=[Puerto de exposición del API]
GUNICORN_RELOAD=[true|false]
RUN_MODE=[dev|prod]

DOCUMENTOS_CRUD_URL=[URL API documentos_crud]
GESTOR_DOCUMENTAL_URL=[URL API gestor_documental_mid]

VERIFICACION=[URL de verificación interna]
VERIFICACION_EXTERNA=[URL de verificación externa y destino del QR]

QR_SECRET_PROVIDER=[dev|prod]
QR_SECRET_NAME=[Nombre del secreto QR]

# Solo para desarrollo local con QR_SECRET_PROVIDER=dev
QR_SECRET_ACTIVE_VERSION=[Versión activa simulada]
QR_SECRET_VERSIONS_JSON=[Mapa version->secreto]

# Solo legado/local si se requiere compatibilidad
QR_SIGNING_SECRET=[Fallback legado]
```

## Ejecución local

```shell
git clone https://github.com/udistrital/firma_electronica_mid.git
cd firma_electronica_mid
git pull origin develop && git checkout develop

docker compose up -d --build
```

## Modos de secreto QR

- `QR_SECRET_PROVIDER=dev`: usa el mapa local `QR_SECRET_VERSIONS_JSON`.
- `QR_SECRET_PROVIDER=prod`: usa AWS Secrets Manager. La versión activa se resuelve con `AWSCURRENT` y la validación histórica usa el `VersionId` embebido en el QR.

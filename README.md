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

# Firma v2 con DynamoDB
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://host.docker.internal:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DIPLOMAS_DYNAMODB_FIRMA_TABLE=firma_electronica
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

## Firma v2

`POST /api/v2/firma_electronica` mantiene compatibilidad con `repositorio_documental=nuxeo` y agrega `repositorio_documental=diplomas` para firmar, estampar solo QR, registrar metadata inmutable en DynamoDB y devolver el PDF firmado en Base64. El sistema consumidor guarda el documento en su repositorio.

`GET /api/v2/firma_electronica/{firma_id}` consulta la metadata por PK `firma_id`. La SK se genera como `repositorio_documental#{repositorio_documental}#documento_id#{documento_id}`. No existe endpoint `PUT/PATCH/DELETE` para esta tabla.

Si se ejecuta el MID directamente en la máquina, `AWS_ENDPOINT_URL` debe ser `http://localhost:4566`.

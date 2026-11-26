"""Verificación de diplomas privados; nunca entrega material de firma al cliente."""
import base64
import hashlib
import json
from pathlib import PurePosixPath
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from conf.conf import _get_env
from services.document_store import _aws_client, build_document_sk, get_firma_metadata


class VerificationError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def diploma_metadata(payload):
    """Solo un token ya validado puede autorizar una lectura de diploma."""
    try:
        identifier = str(UUID(str(payload['uuid_documento'])))
        document_id = int(payload['documento_id'])
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise VerificationError(400, 'Token de diploma incompleto') from exc
    if document_id <= 0 or payload.get('repositorio_documental') != 'diplomas':
        raise VerificationError(403, 'Repositorio de documento inválido')
    metadata = get_firma_metadata(identifier, build_document_sk('diplomas', document_id))
    if not metadata:
        raise VerificationError(404, 'Firma electrónica no encontrada')
    if (metadata.get('activo') is not True
            or metadata.get('repositorio_documental') != 'diplomas'
            or str(metadata.get('documento_id')) != str(document_id)
            or metadata.get('uuid_documento') != identifier
            or str(metadata.get('firma_id')) != str(payload.get('firma_id'))):
        raise VerificationError(403, 'Token y metadatos del documento no coinciden')
    return metadata


def verify_pdf_signature(metadata, binary):
    """RSA se calcula sobre base64 canónico del PDF, como en emisión."""
    if hashlib.sha256(binary).hexdigest() != metadata.get('hash_sha256'):
        return False
    keys = metadata.get('llaves')
    keys = json.loads(keys) if isinstance(keys, str) else keys
    public_key = load_pem_public_key(base64.urlsafe_b64decode(keys['llave_publica']))
    try:
        public_key.verify(
            base64.urlsafe_b64decode(keys['firma']),
            base64.b64encode(binary),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False
    return True


def diploma_file(metadata):
    bucket = _get_env('DIPLOMAS_S3_BUCKET')
    if not bucket:
        raise RuntimeError('DIPLOMAS_S3_BUCKET is required for diploma verification')
    identifier = str(UUID(metadata['uuid_documento']))
    prefix = f'diplomas/{identifier}/'
    client = _aws_client('s3')
    # La ruta de emisión lleva un nombre de archivo variable. Buscar solo ese UUID.
    objects = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=2)
    candidates = [item['Key'] for item in objects.get('Contents', [])
                  if item['Key'].startswith(prefix) and item['Key'].lower().endswith('.pdf')]
    if objects.get('IsTruncated') or len(candidates) > 1:
        raise VerificationError(409, 'Más de un archivo asociado al diploma')
    if not candidates:
        raise VerificationError(404, 'PDF original no encontrado')
    response = client.get_object(Bucket=bucket, Key=candidates[0])
    try:
        binary = response['Body'].read()
    finally:
        response['Body'].close()
    if not verify_pdf_signature(metadata, binary):
        raise VerificationError(409, 'El PDF almacenado no coincide con la firma electrónica')
    filename = PurePosixPath(candidates[0]).name
    filename = filename.replace('"', '').replace('\r', '').replace('\n', '')
    return binary, filename

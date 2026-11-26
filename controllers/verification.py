"""Contratos del cliente de verificación atendidos por Firma Electrónica."""
import base64
import binascii
import json
import logging
from uuid import UUID

import requests
from flask import Response, request

from conf.conf import _get_env
from services.diploma_verification import (
    VerificationError,
    diploma_file,
    diploma_metadata,
    verify_pdf_signature,
)
from services.document_store import get_firma_metadata

logger = logging.getLogger(__name__)


def _json(payload, status=200):
    return Response(json.dumps(payload), status=status, mimetype='application/json',
                    headers={'Cache-Control': 'no-store'})


def resolve_diploma_qr(payload, token, include_file=False):
    try:
        metadata = diploma_metadata(payload)
        if not include_file:
            return _json({'Status': '200', 'res': {
                'firma_id': metadata['firma_id'], 'filename': 'diploma.pdf',
                'token': token, 'file_path': '/qr/file',
            }})
        binary, filename = diploma_file(metadata)
        disposition = f'inline; filename="{filename}"'
        if request.accept_mimetypes.best_match(['application/pdf', 'application/json']) == 'application/pdf':
            return Response(binary, mimetype='application/pdf', headers={
                'Content-Disposition': disposition, 'Cache-Control': 'no-store',
                'X-Content-Type-Options': 'nosniff',
            })
        return _json({'Status': '200', 'res': {
            'token': token, 'filename': filename, 'mime_type': 'application/pdf',
            'encoding': 'base64', 'content_disposition': disposition,
            'file': base64.b64encode(binary).decode('ascii'),
        }})
    except VerificationError as error:
        return _json({'Status': str(error.status), 'Error': str(error)}, error.status)
    except Exception:
        logger.exception('No fue posible recuperar el diploma del QR')
        return _json({'Status': '502', 'Error': 'No fue posible consultar el documento firmado'}, 502)


def _scan_pdf(encoded):
    endpoint = _get_env('ESCANEAR_ARCHIVO_URL').rstrip('/')
    if not endpoint:
        raise VerificationError(503, 'Servicio antivirus no configurado')
    try:
        response = requests.post(endpoint + '/verificar', json={'pdf_base64': encoded}, timeout=(5, 30))
        if response.status_code != 200:
            raise VerificationError(502, 'Servicio antivirus no disponible')
        result = response.json()
        if 'body' in result:
            if result.get('statusCode') != 200:
                raise VerificationError(502, 'Servicio antivirus no disponible')
            result = json.loads(result['body'])
        if result.get('status') not in ('clean', 'infected'):
            raise VerificationError(502, 'Respuesta inválida del antivirus')
        return {'message': 'Verificación de virus completada correctamente.',
                'archive': result['status'], 'statusCode': 200}
    except requests.Timeout as exc:
        raise VerificationError(504, 'El antivirus no respondió a tiempo') from exc
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise VerificationError(502, 'No fue posible consultar antivirus') from exc


def verify_manual(data, legacy_verify):
    """Conserva Success/Status/Data/Message y análisis antivirus del MID anterior."""
    try:
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise VerificationError(400, 'Se requiere un archivo para verificar')
        item = data[0]
        try:
            identifier = str(UUID(str(item.get('firma', ''))))
            encoded = ''.join(item.get('pdf_base64', '').split())
            binary = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, AttributeError, binascii.Error) as exc:
            raise VerificationError(400, 'Código de firma o PDF base64 inválido') from exc
        if not binary.startswith(b'%PDF-'):
            raise VerificationError(400, 'El archivo no es un PDF')
        virus = _scan_pdf(encoded)
        verification = None
        if virus['archive'] == 'clean':
            metadata = get_firma_metadata(identifier) if _get_env('DIPLOMAS_DYNAMODB_FIRMA_TABLE') else None
            if metadata is not None:
                if (metadata.get('activo') is not True
                        or metadata.get('repositorio_documental') != 'diplomas'
                        or metadata.get('firma_id') != identifier
                        or metadata.get('uuid_documento') != identifier):
                    raise VerificationError(403, 'Firma de diploma no disponible')
                equal = verify_pdf_signature(metadata, binary)
            else:
                response = legacy_verify([{'firma': identifier, 'fileUp': encoded,
                                           'urlFileUp': item.get('urlFileUp', '')}])
                if response.status_code != 200:
                    raise VerificationError(response.status_code, 'No fue posible verificar la firma')
                result = response.get_json()
                equal = result['res'][0].get('fileEqual') is True
            verification = {'statusCode': 200, 'fileEqual': equal,
                            'Message': 'Verificación de firma completada correctamente.'}
        message = 'El archivo contiene virus.' if virus['archive'] == 'infected' else 'El archivo PDF está limpio.'
        if verification and not verification['fileEqual']:
            message += ' Pero los archivos no coinciden con la firma proporcionada.'
        return _json({'Success': True, 'Status': 200, 'Data': {
            'Virus': virus, 'Verificacion': verification}, 'Message': message})
    except VerificationError as error:
        return _json({'Success': False, 'Status': error.status, 'Data': None, 'Message': str(error)}, error.status)
    except Exception:
        logger.exception('Error al verificar documento')
        return _json({'Success': False, 'Status': 502, 'Data': None,
                      'Message': 'No fue posible verificar el documento'}, 502)

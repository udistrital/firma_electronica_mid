import base64
import hashlib
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from conf.conf import (
    get_aws_access_key_id,
    get_aws_endpoint_url,
    get_aws_region,
    get_aws_secret_access_key,
    get_diplomas_dynamodb_firma_table,
)


def _aws_client(service_name):
    kwargs = {
        "region_name": get_aws_region(),
    }
    endpoint_url = get_aws_endpoint_url()
    access_key = get_aws_access_key_id()
    secret_key = get_aws_secret_access_key()

    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key

    return boto3.client(service_name, **kwargs)


def build_document_sk(repositorio_documental, documento_id):
    repositorio = str(repositorio_documental).strip().lower()
    return f"repositorio_documental#{repositorio}#documento_id#{documento_id}"


def calculate_base64_sha256(base64_pdf):
    pdf_bytes = base64.b64decode(base64_pdf)
    return hashlib.sha256(pdf_bytes).hexdigest()


def put_firma_metadata(item):
    table_name = get_diplomas_dynamodb_firma_table()
    repositorio_documental = item["repositorio_documental"]
    sk = build_document_sk(repositorio_documental, item["documento_id"])
    dynamodb_item = {
        "firma_id": {"S": item["firma_id"]},
        "sk": {"S": sk},
        "repositorio_documental": {"S": repositorio_documental},
        "documento_id": {"S": str(item["documento_id"])},
        "codigo_autenticidad": {"S": item["codigo_autenticidad"]},
        "llaves": {"S": item["llaves"]},
        "firmantes": {"S": item["firmantes"]},
        "firma_encriptada": {"S": item["firma_encriptada"]},
        "activo": {"BOOL": item.get("activo", True)},
        "fecha_creacion": {"S": item["fecha_creacion"]},
        "uuid_documento": {"S": item["uuid_documento"]},
        "hash_sha256": {"S": item.get("hash_sha256", "")},
        "qr_url_segura": {"S": item.get("qr_url_segura") or ""},
    }

    try:
        _aws_client("dynamodb").put_item(
            TableName=table_name,
            Item=dynamodb_item,
            ConditionExpression="attribute_not_exists(firma_id) AND attribute_not_exists(sk)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise ValueError("firma_electronica already exists for firma_id and sk") from exc
        raise

    return {
        "table": table_name,
        "firma_id": item["firma_id"],
        "sk": sk,
        "repositorio_documental": repositorio_documental,
        "documento_id": item["documento_id"],
    }


def _from_dynamodb_value(value):
    if "S" in value:
        return value["S"]
    if "N" in value:
        number = value["N"]
        return int(number) if number.isdigit() else float(number)
    if "BOOL" in value:
        return value["BOOL"]
    if "NULL" in value:
        return None
    if "M" in value:
        return {key: _from_dynamodb_value(child) for key, child in value["M"].items()}
    if "L" in value:
        return [_from_dynamodb_value(child) for child in value["L"]]
    return value


def get_firma_metadata(firma_id, sk=None):
    table_name = get_diplomas_dynamodb_firma_table()
    if sk:
        response = _aws_client("dynamodb").get_item(
            TableName=table_name,
            Key={
                "firma_id": {"S": str(firma_id)},
                "sk": {"S": str(sk)},
            },
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return {key: _from_dynamodb_value(value) for key, value in item.items()}

    response = _aws_client("dynamodb").query(
        TableName=table_name,
        KeyConditionExpression="firma_id = :firma_id",
        ExpressionAttributeValues={":firma_id": {"S": str(firma_id)}},
        ConsistentRead=True,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None
    return {key: _from_dynamodb_value(value) for key, value in items[0].items()}


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

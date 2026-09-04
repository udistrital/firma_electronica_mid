import base64
import hashlib
import json
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from cryptography.fernet import Fernet, InvalidToken
from conf.conf import get_qr_base_url, get_qr_signing_secret
from services.secret_manager import (
    get_active_secret_material,
    get_secret_material_by_kid,
)


def _encode_header(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_header(segment: str) -> dict[str, Any]:
    padded = segment + "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))


def _legacy_secret() -> bytes | None:
    secret = get_qr_signing_secret()
    if not secret:
        return None
    return secret.encode("utf-8")


def is_qr_enabled() -> bool:
    return bool(get_qr_base_url() and (_legacy_secret() or _has_secret_manager_material()))


def _has_secret_manager_material() -> bool:
    try:
        get_active_secret_material()
        return True
    except (NotImplementedError, ValueError, json.JSONDecodeError):
        return False


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _build_fernet(secret: bytes | str) -> Fernet | None:
    if not secret:
        return None
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def build_qr_token(firma_id: Any, documento_id: Any, extra_payload: dict[str, Any] | None = None) -> str | None:
    secret_material = get_active_secret_material()
    fernet = _build_fernet(secret_material.value)
    if not fernet:
        return None

    payload = {
        "kid": secret_material.kid,
        "firma_id": str(firma_id),
        "documento_id": str(documento_id),
    }
    if extra_payload:
        payload.update(extra_payload)
    header = _encode_header({"kid": secret_material.kid})
    encrypted_payload = fernet.encrypt(_json_dumps(payload)).decode("utf-8")
    return f"{header}.{encrypted_payload}"


def build_qr_url(firma_id: Any, documento_id: Any, extra_payload: dict[str, Any] | None = None) -> str | None:
    raw_base_url = get_qr_base_url()
    if not raw_base_url:
        return None

    base_url = raw_base_url.rstrip("/")
    token = build_qr_token(firma_id, documento_id, extra_payload)
    if not base_url or not token:
        return None

    url_parts = urlsplit(base_url)
    query_params = dict(parse_qsl(url_parts.query, keep_blank_values=True))
    query_params["token"] = token
    return urlunsplit((
        url_parts.scheme,
        url_parts.netloc,
        url_parts.path,
        urlencode(query_params),
        url_parts.fragment,
    ))


def validate_qr_token(token: str) -> dict[str, Any]:
    if "." in token:
        header_segment, encrypted_payload = token.split(".", 1)
        try:
            header = _decode_header(header_segment)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid QR token header") from exc

        kid = str(header.get("kid", "")).strip()
        if not kid:
            raise ValueError("Incomplete QR token header")

        secret_material = get_secret_material_by_kid(kid)
        fernet = _build_fernet(secret_material.value)
        raw_token = encrypted_payload
    else:
        # Legacy support for tokens emitted before kid/versioned secrets.
        fernet = _build_fernet(_legacy_secret())
        raw_token = token

    if not fernet:
        raise ValueError("QR secure flow is disabled")

    try:
        payload = json.loads(fernet.decrypt(raw_token.encode("utf-8")).decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise ValueError("Invalid QR token") from exc

    if "firma_id" not in payload or "documento_id" not in payload:
        raise ValueError("Incomplete QR token")

    if "." in token and payload.get("kid") != kid:
        raise ValueError("QR token kid mismatch")

    payload["firma_id"] = str(payload["firma_id"])
    payload["documento_id"] = str(payload["documento_id"])
    return payload

from dataclasses import dataclass

from conf.conf import (
    get_qr_secret_active_version,
    get_qr_secret_arn,
    get_qr_secret_name,
    get_qr_secret_provider,
    get_qr_secret_versions,
    get_qr_signing_secret,
)


@dataclass(frozen=True)
class SecretMaterial:
    secret_name: str
    version: str
    value: str

    @property
    def kid(self) -> str:
        return build_kid(self.secret_name, self.version)


KID_SEPARATOR = "#"


def build_kid(secret_name: str, version: str) -> str:
    return f"{secret_name}{KID_SEPARATOR}{version}"


def parse_kid(kid: str) -> tuple[str, str]:
    secret_name, version = kid.rsplit(KID_SEPARATOR, 1)
    return secret_name, version


def get_active_secret_material() -> SecretMaterial:
    provider = get_qr_secret_provider()
    if provider == "env":
        return _get_env_active_secret_material()
    if provider == "aws":
        return _get_aws_active_secret_material()
    raise NotImplementedError(
        f"QR secret provider '{provider}' is not implemented yet; integrate the official SDK here"
    )


def get_secret_material_by_kid(kid: str) -> SecretMaterial:
    provider = get_qr_secret_provider()
    secret_name, version = parse_kid(kid)
    if provider == "env":
        return _get_env_secret_material(secret_name, version)
    if provider == "aws":
        return _get_aws_secret_material(secret_name, version)
    raise NotImplementedError(
        f"QR secret provider '{provider}' is not implemented yet; integrate the official SDK here"
    )


def _get_env_active_secret_material() -> SecretMaterial:
    secret_name = get_qr_secret_name()
    version = get_qr_secret_active_version()
    if not version:
        raise ValueError("QR_SECRET_ACTIVE_VERSION is required when QR_SECRET_PROVIDER=env")
    return _get_env_secret_material(secret_name, version)


def _get_env_secret_material(secret_name: str, version: str) -> SecretMaterial:
    versions = get_qr_secret_versions()
    value = ""

    if isinstance(versions, dict):
        value = str(versions.get(version, "")).strip()

    # Local fallback while the real Secret Manager SDK is integrated.
    if not value:
        value = get_qr_signing_secret()

    if not value:
        raise ValueError(
            f"No QR secret value available for secret '{secret_name}' version '{version}'"
        )

    return SecretMaterial(secret_name=secret_name, version=version, value=value)


def _get_aws_client():
    import boto3

    return boto3.client("secretsmanager")


def _get_aws_secret_id() -> str:
    return get_qr_secret_arn() or get_qr_secret_name()


def _secret_value_from_response(response: dict) -> str:
    if "SecretString" in response and response["SecretString"] is not None:
        return str(response["SecretString"]).strip()
    if "SecretBinary" in response and response["SecretBinary"] is not None:
        binary_value = response["SecretBinary"]
        if isinstance(binary_value, bytes):
            return binary_value.decode("utf-8").strip()
        return str(binary_value).strip()
    raise ValueError("AWS Secrets Manager returned an empty secret value")


def _get_aws_active_secret_material() -> SecretMaterial:
    client = _get_aws_client()
    secret_id = _get_aws_secret_id()
    response = client.get_secret_value(SecretId=secret_id, VersionStage="AWSCURRENT")
    return SecretMaterial(
        secret_name=response.get("ARN") or response.get("Name") or secret_id,
        version=str(response["VersionId"]).strip(),
        value=_secret_value_from_response(response),
    )


def _get_aws_secret_material(secret_name: str, version: str) -> SecretMaterial:
    client = _get_aws_client()
    response = client.get_secret_value(SecretId=secret_name, VersionId=version)
    return SecretMaterial(
        secret_name=response.get("ARN") or response.get("Name") or secret_name,
        version=str(response["VersionId"]).strip(),
        value=_secret_value_from_response(response),
    )


def describe_secret_backend() -> dict[str, str]:
    provider = get_qr_secret_provider()
    return {
        "provider": provider,
        "secret_name": get_qr_secret_arn() or get_qr_secret_name(),
        "active_version": get_qr_secret_active_version() if provider == "env" else "AWSCURRENT",
    }

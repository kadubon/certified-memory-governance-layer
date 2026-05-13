from __future__ import annotations

import base64
from typing import Any

from cmgl.canonical import canonical_json
from cmgl.exceptions import OptionalDependencyError
from cmgl.ledger import LedgerRecord


def _crypto() -> tuple[Any, Any, type[BaseException]]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise OptionalDependencyError("cryptography", "signing") from exc
    return ed25519, serialization, InvalidSignature


def generate_private_key_pem() -> str:
    ed25519, serialization, _ = _crypto()
    private_key = ed25519.Ed25519PrivateKey.generate()
    pem: bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("ascii")


def public_key_pem_from_private_key(private_key_pem: str) -> str:
    ed25519, serialization, _ = _crypto()
    private_key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("expected Ed25519 private key")
    public_key = private_key.public_key()
    pem: bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def sign_text(text: str, private_key_pem: str) -> str:
    ed25519, serialization, _ = _crypto()
    private_key = serialization.load_pem_private_key(private_key_pem.encode("ascii"), password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("expected Ed25519 private key")
    signature = private_key.sign(text.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def verify_text(text: str, signature_b64: str, public_key_pem: str) -> bool:
    ed25519, serialization, invalid_signature = _crypto()
    public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        raise ValueError("expected Ed25519 public key")
    try:
        public_key.verify(base64.b64decode(signature_b64), text.encode("utf-8"))
    except invalid_signature:
        return False
    return True


def sign_record(record: LedgerRecord, private_key_pem: str) -> str:
    """Sign the canonical ledger record body with an optional Ed25519 key."""

    return sign_text(canonical_json(record), private_key_pem)


def verify_record_signature(
    record: LedgerRecord,
    signature_b64: str,
    public_key_pem: str,
) -> bool:
    return verify_text(canonical_json(record), signature_b64, public_key_pem)

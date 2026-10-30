from __future__ import annotations

import keyring
from keyring.errors import KeyringError

from app.config import SECRET_SERVICE, SECRET_USERNAME


class SecretStoreError(RuntimeError):
    pass


def get_pdf_password() -> str | None:
    try:
        return keyring.get_password(SECRET_SERVICE, SECRET_USERNAME)
    except KeyringError as exc:
        raise SecretStoreError("O cofre de credenciais do sistema não está disponível.") from exc


def set_pdf_password(password: str) -> None:
    if not password.strip():
        raise ValueError("Informe uma senha.")
    try:
        keyring.set_password(SECRET_SERVICE, SECRET_USERNAME, password)
    except KeyringError as exc:
        raise SecretStoreError("Não foi possível salvar a senha no cofre de credenciais do sistema.") from exc


def delete_pdf_password() -> None:
    try:
        existing = keyring.get_password(SECRET_SERVICE, SECRET_USERNAME)
        if existing is not None:
            keyring.delete_password(SECRET_SERVICE, SECRET_USERNAME)
    except KeyringError as exc:
        raise SecretStoreError("Não foi possível remover a senha do cofre de credenciais do sistema.") from exc


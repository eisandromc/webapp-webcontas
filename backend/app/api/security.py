"""Proteções para um servidor sem login exposto na rede de casa."""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DEV_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def client_of(request: Request) -> str:
    return request.client.host if request.client else ""


def require_localhost(request: Request) -> None:
    if client_of(request) not in LOCAL_CLIENTS:
        raise HTTPException(403, "Esta operação só pode ser feita no computador servidor.")


def _allowed_hostnames() -> set[str]:
    machine = socket.gethostname().lower()
    extra = {item.strip().lower() for item in os.getenv("DIVISAO_ALLOWED_HOSTS", "").split(",") if item.strip()}
    return {"localhost", "testserver", machine, f"{machine}.local"} | extra


def is_allowed_host(host_header: str) -> bool:
    """Aceita IPs, localhost e o nome desta máquina; recusa domínios externos (DNS rebinding)."""
    hostname = urlsplit(f"//{host_header}").hostname
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return hostname in _allowed_hostnames()


def is_same_origin(request: Request) -> bool:
    """Gravações só podem vir das páginas do próprio app (bloqueia formulários de outros sites)."""
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True
    if origin in DEV_ORIGINS:
        return True
    return urlsplit(origin).netloc.lower() == request.headers.get("host", "").lower()


async def request_guard(request: Request, call_next):
    if not is_allowed_host(request.headers.get("host", "")):
        return JSONResponse({"detail": "Endereço não permitido."}, status_code=400)
    if request.method not in SAFE_METHODS and not is_same_origin(request):
        return JSONResponse({"detail": "Requisição de outro site recusada."}, status_code=403)
    return await call_next(request)

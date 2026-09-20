"""Proveedor HTTP para una instancia Ollama exclusivamente local."""

from __future__ import annotations

import ipaddress
import http.client
import json
import math
import os
import socket
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from kwiaty.providers.contracts import ProviderResponse, ProviderStatus


class OllamaConfigurationError(ValueError):
    """La configuración de Ollama no cumple los límites locales de Kwiaty."""


class _Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout: float,
    ) -> bytes: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _UrllibTransport:
    def __init__(self):
        self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def request(
        self,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout: float,
    ) -> bytes:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url=url, data=data, headers=headers, method=method)
        with self._opener.open(request, timeout=timeout) as response:
            return response.read()


class _OllamaRequestError(RuntimeError):
    pass


class OllamaProvider:
    """Cliente de Ollama limitado a direcciones de loopback."""

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        transport: _Transport | None = None,
    ):
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError as exc:
            raise OllamaConfigurationError("La URL de Ollama no es válida.") from exc

        if parsed.scheme != "http":
            raise OllamaConfigurationError("Ollama debe usar HTTP local.")
        if parsed.username is not None or parsed.password is not None:
            raise OllamaConfigurationError("La URL de Ollama no admite credenciales.")
        if not parsed.hostname or not self._is_loopback_host(parsed.hostname):
            raise OllamaConfigurationError("Ollama debe estar en localhost o loopback.")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise OllamaConfigurationError("La URL de Ollama no admite ruta, query o fragmento.")
        if not model.strip():
            raise OllamaConfigurationError("Debe configurar un modelo de Ollama.")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise OllamaConfigurationError("El timeout de Ollama debe ser positivo.")

        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        netloc = f"{host}:{port}" if port is not None else host
        self.base_url = f"http://{netloc}"
        self.model = model.strip()
        self.timeout = float(timeout)
        self._transport = transport or _UrllibTransport()

    @classmethod
    def from_env(cls, transport: _Transport | None = None) -> "OllamaProvider":
        base_url = os.environ.get("KWIATY_OLLAMA_URL", "http://127.0.0.1:11434")
        model = os.environ.get("KWIATY_OLLAMA_MODEL", "")
        timeout_text = os.environ.get("KWIATY_OLLAMA_TIMEOUT", "30")
        try:
            timeout = float(timeout_text)
        except ValueError as exc:
            raise OllamaConfigurationError(
                "KWIATY_OLLAMA_TIMEOUT debe ser un número positivo."
            ) from exc
        return cls(base_url, model, timeout, transport=transport)

    def status(self) -> ProviderStatus:
        try:
            payload = self._request_json("GET", "/api/tags", None)
        except _OllamaRequestError as exc:
            return ProviderStatus(False, False, str(exc))

        models = payload.get("models")
        if not isinstance(models, list):
            return ProviderStatus(
                True,
                False,
                "Ollama devolvió una lista de modelos inválida.",
            )

        installed_names = {
            value
            for item in models
            if isinstance(item, dict)
            for value in (item.get("name"), item.get("model"))
            if isinstance(value, str)
        }
        if self.model not in installed_names:
            return ProviderStatus(
                True,
                False,
                f"El modelo configurado '{self.model}' no está instalado en Ollama.",
            )
        return ProviderStatus(True, True, "")

    def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> ProviderResponse:
        try:
            full_prompt = self._compose_prompt(prompt, context)
            payload = self._request_json(
                "POST",
                "/api/generate",
                {"model": self.model, "prompt": full_prompt, "stream": False},
            )
        except _OllamaRequestError as exc:
            return ProviderResponse(False, "", self.provider_name, str(exc))

        response_text = payload.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            error = "Ollama devolvió una respuesta de texto inválida."
            return ProviderResponse(False, "", self.provider_name, error)
        return ProviderResponse(True, response_text, self.provider_name)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            raw = self._transport.request(
                method,
                f"{self.base_url}{path}",
                payload,
                self.timeout,
            )
            parsed = json.loads(raw.decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise _OllamaRequestError(
                "Se agotó el tiempo de espera al contactar Ollama."
            ) from exc
        except HTTPError as exc:
            raise _OllamaRequestError(
                f"Ollama respondió con error HTTP {exc.code}."
            ) from exc
        except URLError as exc:
            raise _OllamaRequestError("No se pudo conectar con Ollama local.") from exc
        except (http.client.HTTPException, OSError) as exc:
            raise _OllamaRequestError(
                "La conexión con Ollama se interrumpió durante la respuesta."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise _OllamaRequestError(
                "Ollama devolvió una respuesta JSON inválida."
            ) from exc

        if not isinstance(parsed, dict):
            raise _OllamaRequestError("Ollama devolvió una respuesta JSON inválida.")
        return parsed

    @staticmethod
    def _compose_prompt(
        prompt: str,
        context: Mapping[str, Any] | None,
    ) -> str:
        if not context:
            return prompt
        try:
            serialized_context = json.dumps(
                dict(context),
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise _OllamaRequestError("El contexto del modelo no es serializable.") from exc
        return f"Contexto JSON:\n{serialized_context}\n\nConsulta:\n{prompt}"

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        if host.casefold() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

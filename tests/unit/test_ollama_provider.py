"""Pruebas del proveedor local Ollama."""

import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from kwiaty.providers.contracts import ProviderResponse, ProviderStatus
from kwiaty.providers.ollama import OllamaConfigurationError, OllamaProvider


class FakeTransport:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def request(self, method, url, payload, timeout):
        self.requests.append((method, url, payload, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if isinstance(self.outcome, bytes):
            return self.outcome
        return json.dumps(self.outcome).encode("utf-8")


def make_provider(outcome):
    return OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen2.5:7b",
        timeout=5,
        transport=FakeTransport(outcome),
    )


class TestOllamaConfiguration(unittest.TestCase):
    def test_accepts_loopback_defaults(self):
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="qwen2.5:7b",
            timeout=5,
        )

        self.assertEqual(provider.provider_name, "ollama")

    def test_rejects_non_local_or_credentialed_urls(self):
        urls = (
            "https://example.com",
            "http://192.168.1.10:11434",
            "http://user:pass@localhost:11434",
        )

        for url in urls:
            with self.subTest(url=url), self.assertRaises(OllamaConfigurationError):
                OllamaProvider(base_url=url, model="qwen2.5:7b", timeout=5)

    def test_requires_non_empty_model_and_positive_timeout(self):
        with self.assertRaises(OllamaConfigurationError):
            OllamaProvider(
                base_url="http://localhost:11434",
                model="",
                timeout=5,
            )

        with self.assertRaises(OllamaConfigurationError):
            OllamaProvider(
                base_url="http://localhost:11434",
                model="qwen2.5:7b",
                timeout=0,
            )

    def test_from_env_reads_explicit_local_configuration(self):
        values = {
            "KWIATY_OLLAMA_URL": "http://[::1]:11434",
            "KWIATY_OLLAMA_MODEL": "qwen2.5:7b",
            "KWIATY_OLLAMA_TIMEOUT": "2.5",
        }

        with patch.dict(os.environ, values, clear=True):
            provider = OllamaProvider.from_env(transport=FakeTransport({}))

        self.assertEqual(provider.base_url, "http://[::1]:11434")
        self.assertEqual(provider.model, "qwen2.5:7b")
        self.assertEqual(provider.timeout, 2.5)


class TestOllamaTransport(unittest.TestCase):
    def test_status_distinguishes_server_and_exact_model(self):
        provider = make_provider(
            {"models": [{"name": "qwen2.5:7b", "model": "qwen2.5:7b"}]}
        )

        self.assertEqual(provider.status(), ProviderStatus(True, True, ""))

    def test_status_reports_missing_model(self):
        status = make_provider({"models": [{"name": "llama3:8b"}]}).status()

        self.assertTrue(status.server_available)
        self.assertFalse(status.model_available)
        self.assertIn("qwen2.5:7b", status.detail)

    def test_generate_returns_only_response_text(self):
        transport = FakeTransport({"response": "respuesta local"})
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="qwen2.5:7b",
            timeout=5,
            transport=transport,
        )

        response = provider.generate("hola", {"session_id": "s1"})

        self.assertEqual(
            response,
            ProviderResponse(True, "respuesta local", "ollama", None),
        )
        method, url, payload, timeout = transport.requests[0]
        self.assertEqual((method, url, timeout), ("POST", "http://127.0.0.1:11434/api/generate", 5.0))
        self.assertEqual(payload["model"], "qwen2.5:7b")
        self.assertFalse(payload["stream"])
        self.assertIn('"session_id": "s1"', payload["prompt"])

    def test_transport_failures_are_normalized(self):
        failures = (
            TimeoutError(),
            URLError("offline"),
            HTTPError("http://127.0.0.1:11434", 500, "error", {}, None),
        )

        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                response = make_provider(failure).generate("hola")
                self.assertFalse(response.success)
                self.assertEqual(response.provider_name, "ollama")
                self.assertTrue(response.error)

    def test_invalid_json_is_normalized(self):
        response = make_provider(b"not-json").generate("hola")

        self.assertFalse(response.success)
        self.assertIn("inválida", response.error)

    def test_empty_or_non_text_response_is_rejected(self):
        for payload in ({}, {"response": 4}, {"response": ""}):
            with self.subTest(payload=payload):
                self.assertFalse(make_provider(payload).generate("hola").success)

    def test_status_transport_failure_marks_server_unavailable(self):
        status = make_provider(URLError("offline")).status()

        self.assertFalse(status.server_available)
        self.assertFalse(status.model_available)
        self.assertTrue(status.detail)


if __name__ == "__main__":
    unittest.main()

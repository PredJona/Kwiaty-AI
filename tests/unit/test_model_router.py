"""Pruebas del enrutamiento desacoplado de modelos."""

import unittest

from kwiaty.core.model_router import ModelRouter
from kwiaty.providers.contracts import ProviderResponse, ProviderStatus


class FakeProvider:
    provider_name = "ollama"

    def __init__(self, status, response=None):
        self._status = status
        self._response = response or ProviderResponse(
            True,
            "hola local",
            self.provider_name,
        )
        self.generate_count = 0

    def status(self):
        return self._status

    def generate(self, prompt, context=None):
        self.generate_count += 1
        return self._response


class TestModelRouter(unittest.TestCase):
    def test_available_provider_generates_response(self):
        provider = FakeProvider(ProviderStatus(True, True))
        router = ModelRouter(provider)

        response = router.generate("hola", {"session_id": "s1"})

        self.assertTrue(response.success)
        self.assertEqual(response.content, "hola local")
        self.assertEqual(response.provider_name, "ollama")
        self.assertEqual(provider.generate_count, 1)

    def test_unavailable_server_does_not_call_generate(self):
        provider = FakeProvider(
            ProviderStatus(False, False, "Ollama no está disponible")
        )

        response = ModelRouter(provider).generate("hola")

        self.assertFalse(response.success)
        self.assertTrue(response.is_offline_notice)
        self.assertEqual(response.error, "Ollama no está disponible")
        self.assertEqual(provider.generate_count, 0)

    def test_missing_model_does_not_call_generate(self):
        provider = FakeProvider(ProviderStatus(True, False, "Modelo no instalado"))

        response = ModelRouter(provider).generate("hola")

        self.assertFalse(response.success)
        self.assertTrue(response.is_offline_notice)
        self.assertEqual(response.error, "Modelo no instalado")
        self.assertEqual(provider.generate_count, 0)

    def test_provider_generation_failure_is_preserved(self):
        provider = FakeProvider(
            ProviderStatus(True, True),
            ProviderResponse(False, "", "ollama", "timeout"),
        )

        response = ModelRouter(provider).generate("hola")

        self.assertFalse(response.success)
        self.assertEqual(response.error, "timeout")
        self.assertEqual(response.provider_name, "ollama")


if __name__ == "__main__":
    unittest.main()

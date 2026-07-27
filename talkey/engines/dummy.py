'''
DummyTTS: a no-op engine that logs instead of speaking, useful for testing
and for guaranteeing Talkey always has at least one available engine.
'''
from __future__ import annotations

from typing import Any

from talkey.base import AbstractTTSEngine, DETECTABLE_LANGS


class DummyTTS(AbstractTTSEngine):
    """
    Dummy TTS engine that logs phrases with INFO level instead of synthesizing
    speech.
    """

    SLUG = "dummy"

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'enabled': {
                'description': 'Is enabled?',
                'type': 'bool',
                'default': False,
            },
        }

    def _is_available(self) -> bool:
        return True

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        return dict([
            (lang, {'default': lang, 'voices': {lang: {}}})
            for lang in DETECTABLE_LANGS
        ])

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        self._logger.info('%s: %s', language, phrase)

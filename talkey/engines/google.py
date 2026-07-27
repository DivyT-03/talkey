'''
GoogleTTS: wraps the gTTS package to use Google Translate's TTS endpoint.
'''
from __future__ import annotations

import os
import tempfile
from typing import Any

try:
    import gtts
    import gtts.lang
except ImportError:  # pragma: no cover
    pass

from talkey.base import AbstractTTSEngine, register
from talkey.utils import check_network_connection, check_python_import, voice_codes_to_lang_tree


@register
class GoogleTTS(AbstractTTSEngine):
    """
    Uses the Google TTS online translator.

    Requires module ``gTTS`` to be available.
    """

    SLUG = "google"

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
        return (
            check_python_import('gtts')
            and check_network_connection('translate.google.com', 80)
        )

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        return voice_codes_to_lang_tree(gtts.lang.tts_langs().keys())

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        tts = gtts.gTTS(text=phrase, lang=voice)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmpfile = f.name
        tts.save(tmpfile)
        self.play(tmpfile, translate=True)
        os.remove(tmpfile)

'''
PicoTTS: wraps SVOX Pico's pico2wave command-line synthesizer.
'''
from __future__ import annotations

import os
import re
import tempfile
from typing import Any

from talkey.base import AbstractTTSEngine, subprocess, register, run_quietly
from talkey.utils import check_executable, quote, voice_codes_to_lang_tree


@register
class PicoTTS(AbstractTTSEngine):
    """
    Uses the svox-pico-tts speech synthesizer.

    Requires ``pico2wave`` to be available.
    """

    SLUG = "pico"

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'pico2wave': {
                'description': 'pico2wave executable path',
                'type': 'str',
                'default': 'pico2wave'
            },
        }

    def _is_available(self) -> bool:
        return check_executable(self.ioptions['pico2wave'])

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        cmd = [self.ioptions['pico2wave'], '-l', 'NULL', '-w', os.devnull]
        with tempfile.SpooledTemporaryFile() as f:
            subprocess.call(cmd, stderr=f)
            f.seek(0)
            output = f.read().decode('utf-8')
        pattern = re.compile(r'Unknown language: NULL\nValid languages:\n((?:[a-z]{2}-[A-Z]{2}\n)+)')
        matchobj = pattern.match(output)
        assert matchobj is not None  # guaranteed by pico2wave's error output format
        voices = matchobj.group(1).split()
        return voice_codes_to_lang_tree(voices)

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd = [self.ioptions['pico2wave'], '-l', voice, '-w', fname, phrase]
        self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
        run_quietly(cmd, self.ioptions['quiet'])
        self.play(fname)
        os.remove(fname)

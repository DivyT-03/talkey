'''
FliteTTS: wraps the Flite (festival-lite) command-line synthesizer.
'''
from __future__ import annotations

import os
import tempfile
from typing import Any

from talkey.base import AbstractTTSEngine, subprocess, register, run_quietly
from talkey.utils import check_executable, quote


@register
class FliteTTS(AbstractTTSEngine):
    """
    Uses the flite speech synthesizer.

    Requires ``flite`` to be available.
    """

    SLUG = 'flite'

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'flite': {
                'description': 'FLite executable path',
                'type': 'str',
                'default': 'flite'
            },
        }

    def _is_available(self) -> bool:
        return check_executable(self.ioptions['flite'])

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        output = subprocess.check_output([self.ioptions['flite'], '-lv'], universal_newlines=True)
        voices = output[output.find(':') + 1:].split()
        return {
            'en': {
                'default': 'kal',
                'voices': dict([(voice, {}) for voice in voices])
            }
        }

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        cmd = [
            self.ioptions['flite'],
            '-voice', voice,
            '-t', phrase
        ]
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        cmd.append(fname)
        self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
        run_quietly(cmd, self.ioptions['quiet'])
        self.play(fname)
        os.remove(fname)

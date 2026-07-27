'''
FestivalTTS: wraps the Festival speech synthesizer's --pipe/Scheme interface.
'''
from __future__ import annotations

import os
import tempfile
from typing import Any

from talkey.base import AbstractTTSEngine, subprocess, register, run_quietly
from talkey.utils import check_executable, quote


@register
class FestivalTTS(AbstractTTSEngine):
    """
    Uses the festival speech synthesizer.

    Requires ``festival`` to be available.
    """

    SLUG = 'festival'

    SAY_TEMPLATE = """(Parameter.set 'Audio_Required_Format 'riff)
(Parameter.set 'Audio_Command "mv $FILE {outfilename}")
(Parameter.set 'Audio_Method 'Audio_Command)
(SayText "{phrase}")
"""

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'festival': {
                'description': 'Festival executable path',
                'type': 'str',
                'default': 'festival'
            },
        }

    def _is_available(self) -> bool:
        if check_executable(self.ioptions['festival']):
            cmd = [self.ioptions['festival'], '--pipe']
            with tempfile.SpooledTemporaryFile() as in_f:
                self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
                output = subprocess.check_output(cmd, stdin=in_f, stderr=subprocess.STDOUT, universal_newlines=True).strip()
                return 'No default voice found' not in output
        return False  # pragma: no cover

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        return {
            'en': {'default': 'en', 'voices': {'en': {}}}
        }

    @staticmethod
    def _escape_phrase(phrase: str) -> str:
        '''
        Escape a phrase for embedding in a double-quoted Scheme string literal.

        :param phrase: raw phrase text
        :returns: phrase with backslashes and double quotes escaped
        '''
        return phrase.replace('\\', '\\\\').replace('"', '\\"')

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        cmd = [self.ioptions['festival'], '--pipe']
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        with tempfile.SpooledTemporaryFile() as in_f:
            in_f.write(self.SAY_TEMPLATE.format(outfilename=fname, phrase=self._escape_phrase(phrase)).encode('utf-8'))
            in_f.seek(0)
            self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
            run_quietly(cmd, self.ioptions['quiet'], stdin=in_f)
        self.play(fname)
        os.remove(fname)

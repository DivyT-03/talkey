'''
SayTTS: wraps the macOS built-in `say` command-line synthesizer.
'''
from __future__ import annotations

import platform
from typing import Any

from talkey.base import AbstractTTSEngine, subprocess, register, run_quietly
from talkey.utils import quote


@register
class SayTTS(AbstractTTSEngine):
    """
    Uses the built-in TTS engine `say` on macOS.
    """

    SLUG = 'say'

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'say': {
                'description': 'Say executable path',
                'type': 'str',
                'default': r'say'
            },
        }

    def sound_available(self) -> bool:
        """
        We must override this function since the winsound module and the aplay
        executable do not exist on macOS.
        """
        return platform.system() == 'Darwin'

    def _is_available(self) -> bool:
        return platform.system() == 'Darwin'

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        """
        Parses the output of `say -v '?'`
        """
        lines = subprocess.check_output([self.ioptions['say'], '-v', '?'], universal_newlines=True).split("\n")
        langs: dict[str, dict[str, Any]] = {}
        for line in lines:
            voice = line.split()
            if len(voice) < 2:
                continue
            if voice[1][:2] not in langs:
                langs[voice[1][:2]] = {
                    'default': voice[0],
                    'voices': {}}
            langs[voice[1][:2]]['voices'][voice[0]] = {}
        return langs

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        cmd = [
            self.ioptions['say'],
            phrase
        ]
        self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
        run_quietly(cmd, self.ioptions['quiet'])

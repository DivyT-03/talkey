'''
MaryTTS: wraps a MaryTTS HTTP server's REST API.
'''
from __future__ import annotations

import os
import tempfile
from typing import Any

import requests

try:
    # pylint: disable=E0611
    from urlparse import urlunsplit
    from urllib import urlencode  # type: ignore[attr-defined]
except ImportError:
    # pylint: disable=E0611
    from urllib.parse import urlunsplit, urlencode

from talkey.base import AbstractTTSEngine, register
from talkey.utils import check_network_connection


@register
class MaryTTS(AbstractTTSEngine):
    """
    Uses the MARY Text-to-Speech System (MaryTTS)
    MaryTTS is an open-source, multilingual Text-to-Speech Synthesis platform
    written in Java.
    Please specify your own server instead of using the demonstration server
    (http://mary.dfki.de:59125/) to save bandwidth and to protect your privacy.
    """

    SLUG = "mary"

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'enabled': {
                'description': 'Is enabled?',
                'type': 'bool',
                'default': False,
            },
            'scheme': {
                'description': 'HTTP schema',
                'type': 'enum',
                'default': 'http',
                'values': ['http', 'https'],
            },
            'host': {
                'description': 'Mary server address',
                'type': 'str',
                'default': '127.0.0.1',
            },
            'port': {
                'description': 'Mary server port',
                'type': 'int',
                'default': 59125,
                'min': 1,
                'max': 65535,
            }
        }

    def _makeurl(self, path: str, query: dict[str, Any] | None = None) -> str:
        '''
        :param path: server path to request (e.g. "voices")
        :param query: optional query-string parameters
        :returns: the full URL to request, built from this engine's scheme/host/port
        '''
        query_s = urlencode(query or {})
        urlparts = (self.ioptions['scheme'], self.ioptions['host'] + ':' + str(self.ioptions['port']), path, query_s, '')
        return urlunsplit(urlparts)

    def _is_available(self) -> bool:
        return check_network_connection(self.ioptions['host'], self.ioptions['port'])

    def _get_options(self) -> dict[str, dict[str, Any]]:
        return {}

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        res = requests.get(self._makeurl('voices'), timeout=5).text
        langs: dict[str, dict[str, Any]] = {}
        for voice in [row.split() for row in res.split('\n') if row]:
            lang = voice[1].split('_')[0]
            langs.setdefault(lang, {'default': voice[0], 'voices': {}})
            langs[lang]['voices'][voice[0]] = {
                'gender': voice[2],
                'locale': voice[1]
            }
        return langs

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        query = {'OUTPUT_TYPE': 'AUDIO',
                 'AUDIO': 'WAVE_FILE',
                 'INPUT_TYPE': 'TEXT',
                 'INPUT_TEXT': phrase,
                 'LOCALE': voiceinfo['locale'],
                 'VOICE': voice}

        res = requests.get(self._makeurl('/process', query=query), timeout=5)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(res.content)
            tmpfile = f.name
        self.play(tmpfile)
        os.remove(tmpfile)

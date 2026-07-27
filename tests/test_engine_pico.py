from unittest import mock

import pytest

from talkey.engines.pico import PicoTTS

from tests._base import BaseTTSTest


class PicoTTSTest(BaseTTSTest):
    __test__ = True
    CLS = PicoTTS
    SLUG = 'pico'
    INIT_ATTRS = ['enabled', 'quiet', 'pico2wave']


@pytest.mark.mocked
class PicoExecutablePathTest:
    '''
    Regression test: PicoTTS used to hardcode 'pico2wave' as the literal
    command name in _get_languages()/_say(), ignoring the configured
    executable path.
    '''

    FAKE_OUTPUT = (
        'Unknown language: NULL\n'
        'Valid languages:\n'
        'en-US\n'
        'af-ZA\n'
    ).encode('utf-8')

    def _fake_call(self, cmd, stderr=None):
        self._last_cmd = cmd
        if stderr is not None:
            stderr.write(self.FAKE_OUTPUT)
        return 0

    @mock.patch('talkey.engines.pico.check_executable', return_value=True)
    def test_get_languages_uses_configured_path(self, mock_check_executable):
        with mock.patch('talkey.engines.pico.subprocess.call', side_effect=self._fake_call):
            obj = PicoTTS(pico2wave='/custom/path/pico2wave')
            obj.get_languages()
        assert self._last_cmd[0] == '/custom/path/pico2wave'

    @mock.patch('talkey.engines.pico.check_executable', return_value=True)
    @mock.patch.object(PicoTTS, 'play')
    def test_say_uses_configured_path(self, mock_play, mock_check_executable):
        with mock.patch('talkey.engines.pico.subprocess.call', side_effect=self._fake_call):
            obj = PicoTTS(pico2wave='/custom/path/pico2wave')
            obj.say('hello')
        assert self._last_cmd[0] == '/custom/path/pico2wave'

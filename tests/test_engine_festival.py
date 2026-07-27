from unittest import mock

import pytest

from talkey.engines.festival import FestivalTTS

from tests._base import BaseTTSTest


class FestivalTTSTest(BaseTTSTest):
    __test__ = True
    CLS = FestivalTTS
    SLUG = 'festival'
    INIT_ATTRS = ['enabled', 'quiet', 'festival']


@pytest.mark.mocked
class FestivalEscapingTest:
    '''
    Regression test: FestivalTTS._say() used to build
    phrase.replace('\\\\', '\\\\\\\\"').replace('"', '\\\\"'), which inserted a
    spurious '"' for every backslash instead of doubling it.
    '''

    def test_escapes_quotes_and_backslashes(self):
        phrase = 'He said "hi" and used C:\\path\\to\\file'
        escaped = FestivalTTS._escape_phrase(phrase)
        assert escaped == 'He said \\"hi\\" and used C:\\\\path\\\\to\\\\file'

    def test_plain_phrase_unaffected(self):
        assert FestivalTTS._escape_phrase('Cows go moo') == 'Cows go moo'


@pytest.mark.mocked
class FestivalExecutablePathTest:
    '''
    Regression test: FestivalTTS used to hardcode 'festival' as the literal
    command name in _is_available()/_say(), ignoring the configured
    executable path option entirely.
    '''

    @mock.patch('talkey.engines.festival.check_executable', return_value=True)
    @mock.patch('talkey.engines.festival.subprocess.check_output', return_value='ok')
    def test_is_available_uses_configured_path(self, mock_check_output, mock_check_executable):
        obj = FestivalTTS(festival='/custom/path/festival')
        obj._is_available()
        cmd = mock_check_output.call_args[0][0]
        assert cmd[0] == '/custom/path/festival'

    @mock.patch('talkey.engines.festival.check_executable', return_value=True)
    @mock.patch('talkey.engines.festival.subprocess.check_output', return_value='ok')
    @mock.patch('talkey.engines.festival.subprocess.call')
    @mock.patch.object(FestivalTTS, 'play')
    def test_say_uses_configured_path(self, mock_play, mock_call, mock_check_output, mock_check_executable):
        obj = FestivalTTS(festival='/custom/path/festival')
        obj.say('hello')
        cmd = mock_call.call_args[0][0]
        assert cmd[0] == '/custom/path/festival'

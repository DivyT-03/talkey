from unittest import mock

import pytest

from talkey.engines.flite import FliteTTS

from tests._base import BaseTTSTest


class FliteTTSTest(BaseTTSTest):
    __test__ = True
    CLS = FliteTTS
    SLUG = 'flite'
    INIT_ATTRS = ['enabled', 'quiet', 'flite']


@pytest.mark.mocked
class FliteExecutablePathTest:
    '''
    Regression test: FliteTTS used to hardcode 'flite' as the literal command
    name in _get_languages()/_say(), ignoring the configured executable path.
    '''

    @mock.patch('talkey.engines.flite.check_executable', return_value=True)
    @mock.patch('talkey.engines.flite.subprocess.check_output', return_value='Voices available: kal')
    def test_get_languages_uses_configured_path(self, mock_check_output, mock_check_executable):
        obj = FliteTTS(flite='/custom/path/flite')
        obj.get_languages()
        cmd = mock_check_output.call_args[0][0]
        assert cmd[0] == '/custom/path/flite'

    @mock.patch('talkey.engines.flite.check_executable', return_value=True)
    @mock.patch('talkey.engines.flite.subprocess.check_output', return_value='Voices available: kal')
    @mock.patch('talkey.engines.flite.subprocess.call')
    @mock.patch.object(FliteTTS, 'play')
    def test_say_uses_configured_path(self, mock_play, mock_call, mock_check_output, mock_check_executable):
        obj = FliteTTS(flite='/custom/path/flite')
        obj.say('hello')
        cmd = mock_call.call_args[0][0]
        assert cmd[0] == '/custom/path/flite'

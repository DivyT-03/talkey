from unittest import mock

import pytest

from talkey.engines.say import SayTTS

from tests._base import BaseTTSTest


class SayTTSTest(BaseTTSTest):
    __test__ = True
    CLS = SayTTS
    SLUG = 'say'
    EVAL_PLAY = False
    INIT_ATTRS = ['enabled', 'quiet', 'say']
    CONF = {'enabled': True}


@pytest.mark.mocked
class SayExecutablePathTest:
    '''
    Regression test: SayTTS._say() used to hardcode 'say' as the literal
    command name (unlike _get_languages(), which already used
    self.ioptions['say']), ignoring the configured executable path.
    '''

    @mock.patch('talkey.engines.say.platform.system', return_value='Darwin')
    @mock.patch('talkey.engines.say.subprocess.check_output', return_value='Alex en_US # comment\n')
    @mock.patch('talkey.engines.say.subprocess.call')
    def test_say_uses_configured_path(self, mock_call, mock_check_output, mock_platform):
        obj = SayTTS(say='/custom/path/say')
        obj.say('hello')
        cmd = mock_call.call_args[0][0]
        assert cmd[0] == '/custom/path/say'
        assert cmd[1] == 'hello'

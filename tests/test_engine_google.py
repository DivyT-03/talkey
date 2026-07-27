from unittest import mock

import pytest

from talkey.engines.google import GoogleTTS

from tests._base import BaseTTSTest


class GoogleTTSTest(BaseTTSTest):
    __test__ = True
    CLS = GoogleTTS
    SLUG = 'google'
    CONF = {'enabled': True}
    FILE_TYPE = 'MPEG ADTS, layer III'


@pytest.mark.mocked
class GoogleLanguagesTest:
    '''
    Regression test: GoogleTTS._get_languages() used to read
    gtts.gTTS.LANGUAGES, a class attribute removed from current gTTS in
    favor of the gtts.lang.tts_langs() function. Verified against gtts==2.5.4
    that this attribute no longer exists and tts_langs() is the replacement.
    '''

    @mock.patch('talkey.engines.google.check_network_connection', return_value=True)
    @mock.patch('talkey.engines.google.check_python_import', return_value=True)
    @mock.patch('talkey.engines.google.gtts.lang.tts_langs')
    def test_get_languages_uses_tts_langs(self, mock_tts_langs, mock_check_import, mock_check_network):
        mock_tts_langs.return_value = {'en': 'English', 'af': 'Afrikaans'}
        obj = GoogleTTS(enabled=True)
        langs = obj.get_languages()
        assert langs == {
            'en': {'default': 'en', 'voices': {'en': {}}},
            'af': {'default': 'af', 'voices': {'af': {}}},
        }

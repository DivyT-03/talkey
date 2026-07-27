from unittest import mock

import pytest

from talkey.engines.mary import MaryTTS

from tests._base import BaseTTSTest


class MaryTTSTest(BaseTTSTest):
    __test__ = True
    CLS = MaryTTS
    SLUG = 'mary'
    INIT_ATTRS = ['enabled', 'quiet', 'host', 'port', 'scheme']
    CONF = {'enabled': True, 'host': 'mary.dfki.de'}
    EVAL_PLAY = True


@pytest.mark.mocked
class MaryLogicTest:
    '''
    MaryTTS's only public demo server (mary.dfki.de, used by the integration
    test above) no longer resolves in DNS - it appears to have been taken
    down. These mocked tests cover the engine's own request-building and
    response-parsing logic (which a real server would otherwise validate)
    so that logic still gets exercised on every run, network or not.
    '''

    VOICES_RESPONSE_TEXT = (
        'cmu-slt-hsmm en_US female\n'
        'dfki-pavoque-neutral de_DE male\n'
    )

    def _make_engine(self):
        # AbstractTTSEngine.__init__ eagerly calls _get_languages(), so the
        # requests.get mock must already be active *during construction*,
        # not just around whichever call the test wants to inspect.
        fake_voices_response = mock.Mock()
        fake_voices_response.text = self.VOICES_RESPONSE_TEXT
        with mock.patch('talkey.engines.mary.check_network_connection', return_value=True), \
                mock.patch('talkey.engines.mary.requests.get', return_value=fake_voices_response):
            return MaryTTS(enabled=True, host='127.0.0.1', port=59125)

    def test_makeurl_builds_expected_url(self):
        engine = self._make_engine()
        assert engine._makeurl('voices') == 'http://127.0.0.1:59125/voices'

    def test_get_languages_parses_voices_response(self):
        engine = self._make_engine()
        assert engine.languages == {
            'en': {'default': 'cmu-slt-hsmm', 'voices': {'cmu-slt-hsmm': {'gender': 'female', 'locale': 'en_US'}}},
            'de': {'default': 'dfki-pavoque-neutral', 'voices': {'dfki-pavoque-neutral': {'gender': 'male', 'locale': 'de_DE'}}},
        }

    def test_say_sends_expected_query_and_plays_result(self):
        engine = self._make_engine()
        fake_process_response = mock.Mock()
        fake_process_response.content = b'RIFF....WAVEfmt fake-wav-bytes'
        played = {}

        def fake_play(self_, filename, translate=False):
            with open(filename, 'rb') as f:
                played['content'] = f.read()

        with mock.patch('talkey.engines.mary.requests.get', return_value=fake_process_response) as mock_get, \
                mock.patch.object(MaryTTS, 'play', side_effect=fake_play, autospec=True):
            engine._say('hello', 'en', 'cmu-slt-hsmm', {'locale': 'en_US'}, {})

        requested_url = mock_get.call_args[0][0]
        assert 'VOICE=cmu-slt-hsmm' in requested_url
        assert 'LOCALE=en_US' in requested_url
        assert 'INPUT_TEXT=hello' in requested_url
        assert played['content'] == fake_process_response.content

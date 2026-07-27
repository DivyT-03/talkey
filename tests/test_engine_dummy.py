import pytest

from talkey.base import TTSError
from talkey.engines.dummy import DummyTTS

from tests._base import BaseTTSTest


class DummyTTSTest(BaseTTSTest):
    __test__ = True
    CLS = DummyTTS
    SLUG = 'dummy'
    CONF = {'enabled': True}
    EVAL_PLAY = False

    @pytest.mark.mocked
    def test_configure_bad_language(self):
        with self.assertRaisesRegex(TTSError, 'Bad language'):
            self.CLS(enabled=True).configure(language='bad')

    @pytest.mark.mocked
    def test_configure_bad_voice(self):
        with self.assertRaisesRegex(TTSError, 'Bad voice'):
            self.CLS(enabled=True).configure(voice='bad')

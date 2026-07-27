'''
Tests for talkey.tts: Talkey orchestration, engine creation, and
enumerate_engines().
'''
from os.path import isfile

import pytest

try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest

from talkey.base import TTSError
from talkey.engines.espeak import EspeakTTS
from talkey.engines.pico import PicoTTS
from talkey.tts import create_engine, enumerate_engines, Talkey

from tests.conftest import LAST_PLAY


@pytest.mark.mocked
class EnumerateEnginesTest(unittest.TestCase):
    '''
    Regression test: enumerate_engines() used to return the live internal
    _ENGINE_ORDER list rather than a copy, so a caller mutating the returned
    list would corrupt engine order process-wide.
    '''

    def test_returns_independent_copy(self):
        first = enumerate_engines()
        first.append('bogus')
        first.pop(0)
        second = enumerate_engines()
        self.assertNotIn('bogus', second)
        self.assertEqual(second, enumerate_engines())


@pytest.mark.mocked
class CreateEngineTest(unittest.TestCase):

    def test_create_engine(self):
        eng = create_engine('dummy', options={'enabled': True})
        self.assertEqual(eng.SLUG, 'dummy')
        self.assertTrue(eng.available)
        assert eng.languages

    def test_create_engine_bad(self):
        with self.assertRaisesRegex(TTSError, 'Unknown engine'):
            create_engine('baddy')


class TalkeyTest(unittest.TestCase):
    TXTS = [
        # Actual, Unweighted, Text
        ('en', 'pl', 'Cows go moo'),
        ('en', 'en', 'Old McDonald had a farm'),
        ('af', 'nl', "Ou boer McDonald het 'n plaas gehad"),
    ]

    def setUp(self):
        LAST_PLAY.clear()

    @pytest.mark.integration
    def test_create_basic(self):
        tts = Talkey()
        for txt in self.TXTS:
            self.assertEqual(txt[1], tts.classify(txt[2]))

        self.assertEqual(tts.get_engine_for_lang('en').SLUG, 'espeak')

        tts.say('Old McDonald had a farm')
        self.assertIn('WAVE audio', LAST_PLAY['output'])
        self.assertEqual(LAST_PLAY['inst'], tts.engines[0])
        self.assertFalse(isfile(LAST_PLAY['filename']), 'Tempfile not deleted')

    @pytest.mark.mocked
    def test_create_weighted(self):
        tts = Talkey(preferred_languages=['en', 'af'])
        for txt in self.TXTS:
            self.assertEqual(txt[0], tts.classify(txt[2]))

        tts = Talkey(preferred_languages=['en', 'af'], preferred_factor=2.0)
        self.assertEqual(self.TXTS[2][1], tts.classify(self.TXTS[2][2]))

    @pytest.mark.mocked
    def test_create_empty(self):
        with self.assertRaisesRegex(TTSError, 'No supported languages'):
            Talkey(
                espeak={'options': {'enabled': False}},
                festival={'options': {'enabled': False}},
                pico={'options': {'enabled': False}},
                flite={'options': {'enabled': False}},
                say={'options': {'enabled': False}},
            )

    @pytest.mark.integration
    def test_create_language_config(self):
        espeak_eng = EspeakTTS()
        if not (espeak_eng.is_available() and espeak_eng.has_mbrola()):
            raise unittest.SkipTest('espeak+mbrola not available in this environment')

        tts = Talkey(
            espeak={
                'languages': {
                    'en': {
                        'voice': 'english-mb-en1',
                        'words_per_minute': 130
                    },
                }
            },
        )
        eng = tts.engines[0]
        self.assertEqual(eng.languages_options['en'][0], 'english-mb-en1')
        self.assertEqual(eng.languages_options['en'][1]['words_per_minute'], 130)

    @pytest.mark.integration
    def test_get_engine_for_lang(self):
        if not PicoTTS().is_available():
            raise unittest.SkipTest('pico not available in this environment')

        tts = Talkey(
            espeak={'options': {'enabled': False}},
        )
        self.assertEqual(tts.get_engine_for_lang('fr').SLUG, 'pico')
        with self.assertRaisesRegex(TTSError, 'Could not match language'):
            tts.get_engine_for_lang('af')

    @pytest.mark.integration
    def test_engine_preference(self):
        if not PicoTTS().is_available():
            raise unittest.SkipTest('pico not available in this environment')

        tts = Talkey(engine_preference=['pico'])

        self.assertEqual(tts.engines[0].SLUG, 'pico')
        self.assertEqual(tts.engines[1].SLUG, 'espeak')


class _FakeEngine:
    'Minimal stand-in for an AbstractTTSEngine, for pure dispatch-logic tests.'

    def __init__(self, slug, langs):
        self.SLUG = slug
        self.languages = {lang: {} for lang in langs}


@pytest.mark.mocked
class TalkeyOrchestrationMockedTest(unittest.TestCase):
    '''
    test_get_engine_for_lang/test_engine_preference/test_create_language_config
    above are integration tests requiring real Pico/mbrola (no official
    Windows package for either), so they skip on this machine. These mocked
    equivalents exercise the exact same Talkey *dispatch logic* -
    get_engine_for_lang()'s matching, engine_preference ordering, and
    per-language config application - against fake/dummy engines that need
    no external binary, so the logic itself is always verified.
    '''

    def test_get_engine_for_lang_matches_first_supporting_engine(self):
        tts = Talkey.__new__(Talkey)  # bypass __init__/real engine construction
        tts.engines = [_FakeEngine('first', ['en']), _FakeEngine('second', ['fr'])]

        self.assertEqual(tts.get_engine_for_lang('fr').SLUG, 'second')

    def test_get_engine_for_lang_raises_when_unmatched(self):
        tts = Talkey.__new__(Talkey)
        tts.engines = [_FakeEngine('first', ['en'])]

        with self.assertRaisesRegex(TTSError, 'Could not match language'):
            tts.get_engine_for_lang('af')

    def test_engine_preference_ordering(self):
        # 'dummy' needs no binary/network, so this is portable everywhere,
        # unlike the real test_engine_preference above (needs Pico).
        tts = Talkey(engine_preference=['dummy'], dummy={'options': {'enabled': True}})
        self.assertEqual(tts.engines[0].SLUG, 'dummy')

    def test_per_language_config_applied_through_talkey(self):
        tts = Talkey(
            dummy={
                'options': {'enabled': True},
                'languages': {'af': {'voice': 'af'}},
            },
        )
        eng = next(e for e in tts.engines if e.SLUG == 'dummy')
        self.assertEqual(eng.languages_options['af'][0], 'af')

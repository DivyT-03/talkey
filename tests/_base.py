'''
Shared base class for per-engine integration-style tests.
'''
from os.path import isfile

import pytest

try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest

from talkey.base import TTSError

from tests.conftest import LAST_PLAY


class BaseTTSTest(unittest.TestCase):
    '''
    Tests talkey basic functionality
    '''
    # pylint: disable=E1102
    # Not a real test on its own - only concrete per-engine subclasses (which
    # set __test__ = True) should be collected; otherwise pytest's unittest
    # integration picks up this imported base class in every module that
    # imports it and reports it as a spurious skip.
    __test__ = False
    CLS = None
    SLUG = None
    INIT_ATTRS = ['enabled', 'quiet']
    CONF = {}
    OBJ_ATTRS = []
    EVAL_PLAY = True
    SKIP_IF_NOT_AVAILABLE = True
    FILE_TYPE = 'WAVE audio'

    @classmethod
    def setUpClass(cls):
        if not cls.CLS:
            raise unittest.SkipTest()

    def setUp(self):
        LAST_PLAY.clear()

        # Stupid py2.6, Grrr
        if not self.CLS:
            raise unittest.SkipTest()

    def skip_not_available(self):
        if self.SKIP_IF_NOT_AVAILABLE and not self.CLS(**self.CONF).is_available():
            # Skip networked/local engines if not available to prevent spurious failures
            raise unittest.SkipTest('%s not available in this environment' % self.SLUG)  # pragma: no cover

    @pytest.mark.mocked
    def test_class_init_options(self):
        cls = self.CLS
        self.assertEqual(cls.SLUG, self.SLUG)
        self.assertEqual(sorted(cls.get_init_options().keys()), sorted(self.INIT_ATTRS))

    @pytest.mark.mocked
    def test_configure_not_enabled(self):
        with self.assertRaisesRegex(TTSError, 'Not enabled'):
            self.CLS(enabled=False).configure()

    @pytest.mark.integration
    def test_class_instantiation(self):
        self.skip_not_available()
        obj = self.CLS(**self.CONF)
        self.assertEqual(obj.SLUG, self.SLUG)
        self.assertEqual(obj.is_available(), True)
        self.assertEqual(sorted(obj.get_options().keys()), sorted(self.OBJ_ATTRS))

    @pytest.mark.integration
    def test_class_configure(self):
        self.skip_not_available()
        obj = self.CLS(**self.CONF)
        language, voice, voiceinfo, options = obj._configure()
        self.assertEqual(language, 'en')
        self.assertIsNotNone(voice)
        self.assertEqual(voice, obj.get_languages()['en']['default'])
        self.assertEqual(sorted(options.keys()), sorted(self.OBJ_ATTRS))

    @pytest.mark.integration
    def test_class_say(self):
        self.skip_not_available()
        obj = self.CLS(**self.CONF)
        obj.say('Cows go moo')
        if self.EVAL_PLAY:
            self.assertIn(self.FILE_TYPE, LAST_PLAY['output'])
            self.assertEqual(LAST_PLAY['inst'], obj)
            self.assertFalse(isfile(LAST_PLAY['filename']), 'Tempfile not deleted')

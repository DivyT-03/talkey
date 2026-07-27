from unittest import mock

import pytest

from talkey.base import TTSError
from talkey.engines.espeak import EspeakTTS

from tests._base import BaseTTSTest, unittest
from tests.conftest import LAST_PLAY


class EspeakTTSTest(BaseTTSTest):
    __test__ = True
    CLS = EspeakTTS
    SLUG = 'espeak'
    INIT_ATTRS = ['enabled', 'quiet', 'espeak', 'mbrola', 'mbrola_voices', 'passable_only']
    OBJ_ATTRS = ['words_per_minute', 'pitch_adjustment', 'variant']
    EVAL_PLAY = True

    @pytest.mark.integration
    def test_get_languages_options(self):
        self.skip_not_available()
        pat = self.CLS(passable_only=True).get_languages()
        paf = self.CLS(passable_only=False).get_languages()
        assert len(paf.keys()) > len(pat.keys())

    @pytest.mark.integration
    def test_mbrola_language(self):
        self.skip_not_available()
        obj = self.CLS(**self.CONF)
        if not obj.has_mbrola():
            raise unittest.SkipTest('mbrola not available in this environment')
        obj.say('Cows go moo', voice='english-mb-en1')
        self.assertIn(self.FILE_TYPE, LAST_PLAY['output'])
        self.assertEqual(LAST_PLAY['inst'], obj)
        from os.path import isfile
        self.assertFalse(isfile(LAST_PLAY['filename']), 'Tempfile not deleted')

    @pytest.mark.mocked
    def test_enabled_not_available(self):
        # Deliberately bad executable - doesn't need a real espeak install.
        with self.assertRaisesRegex(TTSError, 'Not available'):
            self.CLS(enabled=True, espeak='badexec').configure()

    @pytest.mark.integration
    def test_no_mbrola(self):
        self.skip_not_available()
        obj = self.CLS(enabled=True)
        if not obj.has_mbrola():
            raise unittest.SkipTest('mbrola not available in this environment')
        assert 'english-mb-en1' in obj.languages['en']['voices'].keys()

        obj = self.CLS(enabled=True, mbrola='badexec')
        assert 'english-mb-en1' not in obj.languages['en']['voices'].keys()


@pytest.mark.mocked
class EspeakDefaultExecutableCandidatesTest:
    '''
    Regression test for GH #6: on Windows, modern installs are eSpeak NG
    (espeak-ng.exe under 'eSpeak NG'), not classic eSpeak - the default
    candidate list must include those, not just 'espeak' and the old
    'eSpeak\\command_line\\espeak.exe' path.
    '''

    def test_candidates_include_espeak_ng(self):
        candidates = EspeakTTS._get_init_options()['espeak']['default']
        assert 'espeak' in candidates
        assert 'espeak-ng' in candidates
        assert any('eSpeak NG' in c for c in candidates)


@pytest.mark.mocked
class EspeakVoiceParsingTest:
    '''
    Regression tests for GH #6 parsing bugs found once eSpeak NG was
    actually installed and exercised on Windows:

    - eSpeak NG's --voices output uses CRLF line endings; splitting on a bare
      '\\n' left a stray '\\r' stuck to the last field of every row.
    - eSpeak NG always emits a combined "age/gender" token (e.g. "--/M")
      instead of a bare gender letter, which the original gender-missing
      workaround misidentified as the classic eSpeak 1.46 bug and corrupted
      every row.
    - eSpeak NG's '-v' flag does not resolve most VoiceName values directly;
      only the language code or the voice's underlying file identifier
      resolve reliably, so _get_languages() must capture that file
      identifier and _say() must use it instead of the display name.
    '''

    HEADER = 'Pty Language       Age/Gender VoiceName          File                 Other Languages'
    VOICES_OUTPUT = (
        HEADER + '\r\n'
        ' 2  en-us           --/M      English_(America)  gmw\\en-US            (en 3)\r\n'
        ' 5  en-gb-scotland  --/F      English_(Scotland) gmw\\en-GB-scotland   (en 4)\r\n'
    )
    VARIANT_OUTPUT = (
        HEADER + '\r\n'
        ' 5  variant         --/M      Adam               !v\\adam              \r\n'
        # 'm3' is EspeakTTS._get_options()'s hardcoded default variant -
        # it must be present in the parsed variant list or configure_default()
        # fails validation during construction.
        ' 5  variant         --/M      m3                 !v\\m3                \r\n'
    )
    MBROLA_OUTPUT = HEADER + '\r\n'

    def _make_engine(self):
        def fake_check_output(cmd, **kwargs):
            if '--voices=variant' in cmd:
                return self.VARIANT_OUTPUT
            if '--voices=mbrola' in cmd:
                return self.MBROLA_OUTPUT
            return self.VOICES_OUTPUT

        with mock.patch('talkey.engines.espeak.subprocess.check_output', side_effect=fake_check_output), \
                mock.patch('talkey.utils.find_executable', side_effect=lambda exe: None if 'not_a_real' in exe else exe):
            return EspeakTTS(espeak='espeak-ng', mbrola='definitely_not_a_real_executable_xyz')

    def test_crlf_does_not_corrupt_fields(self):
        engine = self._make_engine()
        en_us = engine.languages['en']['voices']['English_(America)']
        assert en_us['gender'] == 'M'
        assert en_us['file'] == 'gmw/en-US'

    def test_gender_field_normalized_from_combined_token(self):
        engine = self._make_engine()
        scotland = engine.languages['en']['voices']['English_(Scotland)']
        assert scotland['gender'] == 'F'

    def test_voiceinfo_carries_file_identifier_for_say(self):
        engine = self._make_engine()
        default_voice = engine.languages['en']['default']
        assert 'file' in engine.languages['en']['voices'][default_voice]


@pytest.mark.mocked
class EspeakMbrolaMergeTest:
    '''
    Mocked coverage for the --voices=mbrola merge path (has_mbrola() gating,
    row parsing, and the mbrola-voice-file existence check), and for _say()
    selecting an mbrola voice - standing in for test_mbrola_language/
    test_no_mbrola above where a real mbrola install isn't available
    (no official Windows package exists for it).
    '''

    HEADER = EspeakVoiceParsingTest.HEADER
    VOICES_OUTPUT = EspeakVoiceParsingTest.VOICES_OUTPUT
    VARIANT_OUTPUT = EspeakVoiceParsingTest.VARIANT_OUTPUT
    MBROLA_OUTPUT = (
        HEADER + '\r\n'
        ' 3  en-uk           --/M      english-mb-en1     mb\\mb-en1            (en-gb 3)(en 2)\r\n'
    )

    def _make_engine(self, mbrola_available=True):
        def fake_check_output(cmd, **kwargs):
            if '--voices=variant' in cmd:
                return self.VARIANT_OUTPUT
            if '--voices=mbrola' in cmd:
                return self.MBROLA_OUTPUT
            return self.VOICES_OUTPUT

        mbrola_option = 'mbrola' if mbrola_available else 'definitely_not_a_real_executable_xyz'
        with mock.patch('talkey.engines.espeak.subprocess.check_output', side_effect=fake_check_output), \
                mock.patch('talkey.engines.espeak.os.path.isfile', return_value=True), \
                mock.patch('talkey.utils.find_executable', side_effect=lambda exe: None if 'not_a_real' in exe else exe):
            return EspeakTTS(espeak='espeak-ng', mbrola=mbrola_option)

    def test_mbrola_voice_merged_when_available(self):
        engine = self._make_engine(mbrola_available=True)
        assert engine.has_mbrola()
        voice = engine.languages['en']['voices']['english-mb-en1']
        assert voice['type'] == 'mbrola'
        assert voice['file'] == 'mb/mb-en1'

    def test_mbrola_voice_absent_when_mbrola_unavailable(self):
        engine = self._make_engine(mbrola_available=False)
        assert not engine.has_mbrola()
        assert 'english-mb-en1' not in engine.languages['en']['voices']

    def test_say_uses_file_identifier_for_mbrola_voice(self):
        engine = self._make_engine(mbrola_available=True)
        voiceinfo = engine.languages['en']['voices']['english-mb-en1']
        options = {'variant': '', 'pitch_adjustment': 50, 'words_per_minute': 150}
        with mock.patch('talkey.engines.espeak.run_quietly') as mock_run_quietly, \
                mock.patch.object(EspeakTTS, 'play'):
            engine._say('hello', 'en', 'english-mb-en1', voiceinfo, options)
        cmd = mock_run_quietly.call_args[0][0]
        assert cmd[cmd.index('-v') + 1] == 'mb/mb-en1'

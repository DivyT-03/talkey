'''
EspeakTTS: wraps the eSpeak / eSpeak NG command-line synthesizer, with
optional mbrola voice support.
'''
from __future__ import annotations

import os
import tempfile
from typing import Any

from talkey.base import AbstractTTSEngine, subprocess, register, run_quietly
from talkey.utils import quote


@register
class EspeakTTS(AbstractTTSEngine):
    """
    Uses the eSpeak speech synthesizer.

    Requires ``espeak`` and optionally ``mbrola`` to be available.
    """

    SLUG = "espeak"
    # http://espeak.sourceforge.net/languages.html
    QUALITY_LANGS = [
        'en', 'af', 'bs', 'ca', 'cs', 'da', 'de', 'el', 'eo', 'es',
        'fi', 'fr', 'hr', 'hu', 'it', 'kn', 'ku', 'lv', 'nl', 'pl',
        'pt', 'ro', 'sk', 'sr', 'sv', 'sw', 'ta', 'tr', 'zh'
    ]

    @classmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        return {
            'espeak': {
                'description': 'eSpeak executable path',
                'type': 'exec',
                'default': [
                    'espeak',
                    'espeak-ng',
                    r'C:\Program Files\eSpeak NG\espeak-ng.exe',
                    r'C:\Program Files (x86)\eSpeak NG\espeak-ng.exe',
                    r'c:\Program Files\eSpeak\command_line\espeak.exe',
                ]
            },
            'mbrola': {
                'description': 'mbrola executable path',
                'type': 'exec',
                'default': 'mbrola'
            },
            'mbrola_voices': {
                'description': 'mbrola voices path',
                'type': 'str',
                'default': '/usr/share/mbrola'
            },
            'passable_only': {
                'description': 'Only allow languages of passable quality, as per http://espeak.sourceforge.net/languages.html',
                'type': 'bool',
                'default': True
            }
        }

    def _is_available(self) -> bool:
        return self.ioptions['espeak'] is not None

    def has_mbrola(self) -> bool:
        '''
        :returns: True if an mbrola executable was found/configured
        '''
        return self.ioptions['mbrola'] is not None

    def _get_options(self) -> dict[str, dict[str, Any]]:
        output = subprocess.check_output([self.ioptions['espeak'], '--voices=variant'], encoding='utf-8', errors='replace')
        variants = [row[row.find('!v') + 3:].strip() for row in output.splitlines()[1:] if row]
        return {
            'variant': {
                'type': 'enum',
                'values': sorted([''] + variants),
                'default': 'm3',
            },
            'pitch_adjustment': {
                'type': 'int',
                'min': 0,
                'max': 99,
                'default': 50,
            },
            'words_per_minute': {
                'type': 'int',
                'min': 80,
                'max': 450,
                'default': 150,
            },
        }

    def _get_languages(self) -> dict[str, dict[str, Any]]:
        'Get all working voices and languages for eSpeak'

        def fix_voice(voice: list[str]) -> list[str]:
            '''
            Normalize the Age/Gender column to a bare gender char (M/F/-).

            Classic eSpeak occasionally omits the gender field entirely (a bug
            in eSpeak 1.46), shifting every later column left by one - detect
            and undo that shift. eSpeak NG instead always emits the field, but
            as a combined "age/gender" token (e.g. "--/M") rather than a bare
            letter - collapse that down to just the gender char.

            :param voice: whitespace-split fields of one --voices output row
            :returns: voice, with the Age/Gender field normalized to index 2
            '''
            gender = voice[2]
            if '/' in gender:
                gender = gender.rsplit('/', 1)[1]
            if gender not in ['M', 'F', '-']:
                return voice[:2] + ['-'] + voice[2:]  # pragma: no cover
            return voice[:2] + [gender] + voice[3:]

        def parse_voice(row: str) -> list[str]:
            '''
            :param row: one raw line of --voices/--voices=variant/--voices=mbrola output
            :returns: [pty, lang, gender, name, file] for that row
            '''
            return fix_voice(row.split())[:5]

        output = subprocess.check_output([self.ioptions['espeak'], '--voices'], encoding='utf-8', errors='replace')
        voices = []
        for row in output.splitlines()[1:]:
            if not row:
                continue
            parsed = parse_voice(row)
            is_mbrola = parsed[4].startswith('mb')
            if is_mbrola and not self.has_mbrola():
                # eSpeak NG lists mbrola-backed voices here even when mbrola
                # itself isn't configured/available - don't advertise them.
                continue
            voices.append((['mbrola'] if is_mbrola else ['espeak']) + parsed)

        if self.has_mbrola():
            output = subprocess.check_output([self.ioptions['espeak'], '--voices=mbrola'], encoding='utf-8', errors='replace')
            mvoices = [parse_voice(row) for row in output.splitlines()[1:] if row]
            for mvoice in mvoices:
                mbfile = mvoice[4].split('-')[1]
                mbfile = os.path.join(self.ioptions['mbrola_voices'], mbfile, mbfile)
                if os.path.isfile(mbfile):
                    voices.append(['mbrola'] + mvoice)

        langs_set = set(voice[2].split('-')[0] for voice in voices)
        langs = [lang for lang in langs_set if not self.ioptions['passable_only'] or lang in self.QUALITY_LANGS]
        tree: dict[str, dict[str, Any]] = {lang: {'voices': {}} for lang in langs}
        for voice in voices:
            lang = voice[2].split('-')[0]
            if lang in langs:
                # voice: [type, pty, lang, gender, name, file]
                tree[lang]['voices'][voice[4]] = {
                    'gender': voice[3],
                    'pty': int(voice[1]),
                    'type': voice[0],
                    'file': voice[5].replace('\\', '/'),
                }
        for lang in langs:
            # Try to find sane default voice, score by pty, then take shortest (for determinism)
            vcs = tree[lang]['voices']
            pty = min(v['pty'] for v in vcs.values())
            tree[lang]['default'] = sorted([k for k, v in vcs.items() if v['pty'] == pty])[0]
        return tree

    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            fname = f.name
        # Use the voice's underlying file identifier rather than its display
        # name for '-v': eSpeak NG's '-v' does not resolve most VoiceName
        # values directly (only the language code or file identifier).
        vce = voiceinfo['file']
        if voiceinfo['type'] == 'espeak' and options['variant']:
            vce += '+' + options['variant']
        cmd = [
            self.ioptions['espeak'],
            '-v', vce,
            '-p', options['pitch_adjustment'],
            '-s', options['words_per_minute'],
            '-w', fname,
            phrase
        ]
        cmd = [str(x) for x in cmd]
        self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
        run_quietly(cmd, self.ioptions['quiet'])
        self.play(fname)
        os.remove(fname)

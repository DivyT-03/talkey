'''
Talkey: the multi-lingual, multi-engine TTS orchestrator, plus the engine
registry lookup functions it's built on.
'''
from __future__ import annotations

from typing import Any

import langid

from .base import AbstractTTSEngine, TTSError
from .engines import _ENGINE_MAP, _ENGINE_ORDER


def enumerate_engines() -> list[str]:
    '''
    Returns list of engine SLUGs in order of preference.

    :returns: a fresh copy of the default engine order - mutating it does
        not affect future calls
    '''
    return list(_ENGINE_ORDER)


def create_engine(
    engine: str,
    options: dict[str, Any] | None = None,
    defaults: dict[str, Any] | None = None,
) -> AbstractTTSEngine:
    '''
    Creates an instance of an engine.
    There is a two-stage instantiation process with engines.

    1. ``options``:
        The keyword options to instantiate the engine class
    2. ``defaults``:
        The default configuration for the engine (options often depends on instantiated TTS engine)

    :param engine: engine SLUG (e.g. "espeak")
    :param options: init options passed to the engine's constructor
    :param defaults: default voice configuration passed to configure_default()
    :returns: the constructed, default-configured engine instance
    :raises TTSError: if engine is not a registered SLUG, or if
        configure_default() fails (e.g. the engine is unavailable)
    '''
    if engine not in _ENGINE_MAP.keys():
        raise TTSError('Unknown engine %s' % engine)

    options = options or {}
    defaults = defaults or {}
    einst = _ENGINE_MAP[engine](**options)
    einst.configure_default(**defaults)
    return einst


class Talkey:
    '''
    Manages engines and allows multi-lingual say()

    ``preferred_languages``
        A list of languages that are weighted in preference. This is a weighting to assist the detection of language by classify().
    ``preferred_factor``
        The weighting factor to prefer the ``preferred_languages`` list. Higher number skews towards preference.
    ``engine_preference``
        Specify preferred engines in order of preference.
    ``**config``
        Engine-specfic configuration, e.g.:

        .. code-block:: python

            # Key is the engine SLUG, in this case ``espeak``
            espeak={
                # Specify the engine options:
                'options': {
                    'enabled': True,
                },

                # Specify some default voice options
                'defaults': {
                        'words_per_minute': 150,
                        'variant': 'f4',
                },

                # Here you specify language-specific voice options
                # e.g. for english we prefer the mbrola en1 voice
                'languages': {
                    'en': {
                        'voice': 'english-mb-en1',
                        'words_per_minute': 130
                    },
                }
            }
    '''

    def __init__(
        self,
        preferred_languages: list[str] | None = None,
        preferred_factor: float = 80.0,
        engine_preference: list[str] | None = None,
        **config: Any,
    ) -> None:
        '''
        :raises TTSError: if no configured engine supports any language
            (typically because no TTS engine is installed/reachable)
        '''
        self.preferred_languages: list[str] = preferred_languages or []
        self.preferred_factor: float = preferred_factor
        engine_preference = engine_preference or enumerate_engines()
        for ename in enumerate_engines():
            if ename not in engine_preference:
                engine_preference.append(ename)

        self.engines: list[AbstractTTSEngine] = []
        self.languages: set[str] = set()

        for ename in engine_preference:
            try:
                options = config.get(ename, {}).get('options', {})
                defaults = config.get(ename, {}).get('defaults', {})
                eng = create_engine(ename, options=options, defaults=defaults)
                self.engines.append(eng)

                languages = config.get(ename, {}).get('languages', {})
                for lang, conf in languages.items():
                    eng.configure(language=lang, **conf)
            except TTSError:
                pass

        for eng in self.engines:
            assert eng.languages is not None  # guaranteed for engines in self.engines
            self.languages.update(eng.languages.keys())

        langid.set_languages(list(self.languages))

        if not self.languages:
            raise TTSError('No supported languages')

    def classify(self, txt: str) -> str:
        '''
        Classifies text by language. Uses preferred_languages weighting.

        :param txt: text to classify
        :returns: the detected language code
        '''
        ranks = []
        for lang, score in langid.rank(txt):
            if lang in self.preferred_languages:
                score += self.preferred_factor
            ranks.append((lang, score))
        ranks.sort(key=lambda x: x[1], reverse=True)
        return ranks[0][0]

    def get_engine_for_lang(self, lang: str) -> AbstractTTSEngine:
        '''
        Determines the preferred engine/voice for a language.

        :param lang: language code to find an engine for
        :returns: the first configured engine (in preference order) supporting lang
        :raises TTSError: if no configured engine supports lang
        '''
        for eng in self.engines:
            assert eng.languages is not None  # guaranteed for engines in self.engines
            if lang in eng.languages.keys():
                return eng
        raise TTSError('Could not match language')

    def say(self, txt: str, lang: str | None = None) -> None:
        '''
        Says the text.

        if ``lang`` is ``None``, then uses ``classify()`` to detect language.

        :param txt: text to say
        :param lang: language to say it in, or None to auto-detect via classify()
        '''
        lang = lang or self.classify(txt)
        self.get_engine_for_lang(lang).say(txt, language=lang)

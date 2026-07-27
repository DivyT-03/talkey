'''
Base classes shared by every talkey TTS engine: the AbstractTTSEngine
contract engines implement, the TTSError exception type, synchronous and
asynchronous playback helpers, and the option-doc-generating @register
decorator.
'''
from __future__ import annotations

import os
import logging
import subprocess
import tempfile
import threading
from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Type

try:
    import winsound
except ImportError:
    winsound = None  # type: ignore[assignment]

from talkey.utils import process_options, check_executable, quote

import langid
import contextlib
import audioread
import wave

# Get the list of identifiable languages
DETECTABLE_LANGS: list[str] = sorted([a[0] for a in langid.rank('')])


def genrst(label: str, opt: dict[str, dict[str, Any]], txt: str, indent: str = '    ') -> str:
    '''
    Appends a reST-formatted description of an option-spec dict to txt (used
    by @register to build engine docstrings from _get_init_options()).

    :param label: section heading (e.g. "Initialization options")
    :param opt: option-spec dict as returned by _get_init_options()
    :param txt: existing docstring text to append to
    :param indent: indentation to use for the generated reST
    :returns: txt with the generated reST section appended
    '''
    txt += '\n%s%s:\n\n' % (indent, label)
    for key in sorted(opt.keys()):
        val = opt[key]
        txt += indent + '``%s``\n' % key
        txt += indent + '    %s\n\n' % val.get('description', '%s option' % key)
        txt += indent + '    :type: %s\n' % val['type']
        txt += indent + '    :default: %s\n' % val['default']
        if 'min' in val.keys():
            txt += indent + '    :min: %s\n' % val['min']
        if 'max' in val.keys():
            txt += indent + '    :max: %s\n' % val['max']
        if 'values' in val.keys():
            txt += indent + '    :values: %s\n' % ', '.join(val['values'])
    return txt


def register(cls: Type[AbstractTTSEngine]) -> Type[AbstractTTSEngine]:
    '''
    Class decorator applied to every concrete engine: appends a reST
    description of the engine's init options (from _get_init_options()) to
    its docstring.

    :param cls: the AbstractTTSEngine subclass to decorate
    :returns: the same class, with its docstring extended
    '''
    cls.__doc__ = genrst('Initialization options', cls.get_init_options(), cls.__doc__ or '')
    return cls


def _quiet_kwargs(quiet: bool, kwargs: dict[str, Any]) -> dict[str, Any]:
    '''
    Adds stdout/stderr=DEVNULL to kwargs (if not already set) when quiet is
    True; used by run_quietly()/_popen_quietly() to share the same logic.

    :param quiet: whether to silence stdout/stderr
    :param kwargs: keyword arguments to augment (mutated and returned)
    :returns: kwargs, with stdout/stderr set to DEVNULL if quiet is True
    '''
    if quiet:
        kwargs.setdefault('stdout', subprocess.DEVNULL)
        kwargs.setdefault('stderr', subprocess.DEVNULL)
    return kwargs


def run_quietly(cmd: list[str], quiet: bool, **kwargs: Any) -> int:
    '''
    Runs cmd via subprocess.call, optionally silencing the child process's
    stdout/stderr chatter (e.g. eSpeak/Festival/aplay debug output).

    :param cmd: command and arguments to run
    :param quiet: whether to silence the child process's stdout/stderr
    :param kwargs: additional keyword arguments passed through to subprocess.call
    :returns: the child process's exit code
    '''
    return subprocess.call(cmd, **_quiet_kwargs(quiet, kwargs))


def _popen_quietly(cmd: list[str], quiet: bool, **kwargs: Any) -> Any:
    '''
    Like run_quietly(), but non-blocking - returns the Popen object.

    :param cmd: command and arguments to run
    :param quiet: whether to silence the child process's stdout/stderr
    :param kwargs: additional keyword arguments passed through to subprocess.Popen
    :returns: the started subprocess.Popen instance
    '''
    return subprocess.Popen(cmd, **_quiet_kwargs(quiet, kwargs))


class PlaybackHandle:
    '''
    Handle to an in-progress asynchronous playback, returned by
    :meth:`AbstractTTSEngine.play_async` / :meth:`AbstractTTSEngine.say_async`.

    ``on_done`` may be assigned (a zero-argument callable) any time before
    playback finishes, to be notified on completion instead of/in addition
    to calling :meth:`wait`. There is a small race if assigned after
    playback has already finished - it simply won't be called.
    '''

    def __init__(self, engine: AbstractTTSEngine) -> None:
        '''
        :param engine: the engine instance this handle's playback belongs to
        '''
        self._engine = engine
        self._done_event = threading.Event()
        self.on_done: Callable[[], None] | None = None

    def wait(self, timeout: float | None = None) -> bool:
        '''
        Blocks until playback finishes (or timeout elapses).

        :param timeout: maximum time in seconds to wait, or None to wait indefinitely
        :returns: True if playback finished, False if the timeout elapsed first
        '''
        return self._done_event.wait(timeout)

    def is_done(self) -> bool:
        '''
        :returns: True if playback has finished
        '''
        return self._done_event.is_set()

    def stop(self) -> None:
        '''
        Best-effort interruption of the in-progress playback.

        On POSIX this terminates the underlying player process. On Windows,
        winsound exposes no per-sound handle or stop primitive, only a
        process-wide purge of whatever it's currently playing - this is only
        correct if a single talkey sound is playing at a time, which matches
        today's synchronous, one-at-a-time usage.
        '''
        if winsound:
            winsound.PlaySound(None, winsound.SND_PURGE)
        else:
            proc = getattr(self._engine, '_last_playback_proc', None)
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    proc.kill()

    def _mark_done(self) -> None:
        'Marks playback as finished and fires on_done, if set.'
        self._done_event.set()
        if self.on_done:
            self.on_done()


class TTSError(Exception):
    '''
    The exception that Talkey will throw if any error occurs.
    '''

    def __init__(self, error: str, valid_set: Any = None) -> None:  # pylint: disable=W0231
        '''
        :param error: human-readable error message
        :param valid_set: optional collection of valid values, included in str(self)
        '''
        self.error = error
        self.valid_set = valid_set

    def __str__(self) -> str:
        if self.valid_set:
            return '%s\nValid set: %s' % (self.error, self.valid_set)
        else:
            return self.error


class AbstractTTSEngine(metaclass=ABCMeta):
    """
    Generic parent class for all speakers
    """
    SLUG: str | None = None
    'The SLUG is used to identify the engine as text'

    # Define these in your engine
    @classmethod
    @abstractmethod
    def _get_init_options(cls) -> dict[str, dict[str, Any]]:
        'AbstractMethod: Returns dict of engine options'

    @abstractmethod
    def _is_available(self) -> bool:
        'AbstractMethod: Boolean on if engine is available'

    @abstractmethod
    def _get_options(self) -> dict[str, dict[str, Any]]:
        'AbstractMethod: Returns dict of voice options'

    @abstractmethod
    def _get_languages(self) -> dict[str, dict[str, Any]]:
        'AbstractMethod: Returns dict of supported languages and voices'

    @abstractmethod
    def _say(
        self,
        phrase: str,
        language: str,
        voice: str,
        voiceinfo: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        '''
        AbstractMethod: Let engin actually says the phrase

        :phrase: The text phrase to say
        :language: The requested language
        :voice: The requested voice
        :voiceinfo: Data about the requested voice
        :options: Extra options
        '''

    @classmethod
    def get_init_options(cls) -> dict[str, dict[str, Any]]:
        '''
        Returns a dict describing the engine options.

        Uses cls._get_init_options()
        '''
        options = {
            'enabled': {
                'description': 'Is enabled?',
                'type': 'bool',
                'default': True
            },
            'quiet': {
                'description': 'Suppress the underlying engine/player subprocess stdout/stderr chatter?',
                'type': 'bool',
                'default': False
            },
        }
        options.update(cls._get_init_options())
        return options

    # Base class continues here
    def __init__(self, **_options: Any) -> None:
        '''
        :param _options: engine init options, validated against get_init_options()
        '''
        self._logger = logging.getLogger(__name__)
        self.ioptions: dict[str, Any] = process_options(self.__class__.get_init_options(), _options, TTSError)

        # Pre-caching potentially slow results
        self.default_language: str = 'en'
        self.languages_options: dict[str, tuple[str, dict[str, Any]]] = {}
        self.default_options: dict[str, Any] = {}
        self.optionspec: dict[str, dict[str, Any]] | None = None
        # Set by play() on the POSIX (Popen-based) branch; read by
        # PlaybackHandle.stop() to terminate an in-progress playback.
        self._last_playback_proc: Any = None
        self.languages: dict[str, dict[str, Any]] | None = None
        self.available: bool = self.is_available()
        if self.available:
            self.optionspec = self.get_options()
            self.languages = self.get_languages()
            self.configure_default()

    def sound_available(self) -> bool:
        '''
        :returns: True if a local audio output mechanism (winsound or aplay) is available
        '''
        return bool(winsound) or check_executable('aplay')

    def is_available(self) -> bool:
        '''
        Boolean on if engine available.

        Checks if enabled, can output audio and self._is_available()
        '''
        return (
            self.ioptions['enabled']
            and self.sound_available()
            and self._is_available()
        )

    def _assert_available(self) -> None:
        '''
        :raises TTSError: if the engine is disabled or unavailable
        '''
        if not self.ioptions['enabled']:
            raise TTSError('Not enabled')
        if not self.available:
            raise TTSError('Not available')

    def get_options(self) -> dict[str, dict[str, Any]]:
        '''
        Returns dict of voice options.

        Raises TTSError if not available.
        '''
        self._assert_available()
        return self._get_options()

    def get_languages(self) -> dict[str, dict[str, Any]]:
        '''
        Returns dict of supported languages and voices.

        Raises TTSError if not available.
        '''
        self._assert_available()
        return self._get_languages()

    def _get_language_options(self, language: str) -> tuple[str | None, dict[str, Any]]:
        '''
        :param language: language code to look up
        :returns: (voice, options) previously configured for language, or (None, {})
        '''
        if language in self.languages_options.keys():
            return self.languages_options[language]
        return None, {}

    def _configure(
        self,
        language: str | None = None,
        voice: str | None = None,
        **_options: Any,
    ) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
        '''
        Resolves and validates the effective (language, voice, voiceinfo,
        options) for a call to say()/configure()/configure_default(),
        falling back to defaults/previously configured values as needed.

        :raises TTSError: if the engine is unavailable, or language/voice is invalid
        '''
        self._assert_available()
        # Guaranteed non-None by _assert_available() (both are populated
        # together in __init__ whenever self.available is True).
        assert self.languages is not None
        assert self.optionspec is not None

        language = language or self.default_language
        lang_voice, lang_options = self._get_language_options(language)
        voice = voice or lang_voice

        if language not in self.languages.keys():
            raise TTSError('Bad language: %s' % language, self.languages.keys())

        voice = voice if voice else self.languages[language]['default']
        if voice not in self.languages[language]['voices'].keys():
            raise TTSError('Bad voice: %s' % voice, self.languages[language]['voices'].keys())
        voiceinfo = self.languages[language]['voices'][voice]

        lang_options.update(_options)
        options = process_options(self.optionspec, lang_options, TTSError)
        return language, voice, voiceinfo, options

    def configure_default(self, **_options: Any) -> None:
        '''
        Sets default configuration.

        Raises TTSError on error.
        '''
        language, voice, _, options = self._configure(**_options)
        self.languages_options[language] = (voice, options)
        self.default_language = language
        self.default_options = options

    def configure(self, **_options: Any) -> None:
        '''
        Sets language-specific configuration.

        Raises TTSError on error.
        '''
        language, voice, _, options = self._configure(**_options)
        self.languages_options[language] = (voice, options)

    def say(self, phrase: str, **_options: Any) -> None:
        '''
        Says the phrase, optionally allows to select/override any voice options.

        Blocks until playback finishes. See :meth:`say_async` for a
        non-blocking equivalent that supports stopping playback early and
        completion notification.
        '''
        language, voice, voiceinfo, options = self._configure(**_options)
        self._logger.debug("Saying '%s' with '%s'", phrase, self.SLUG)
        self._say(phrase, language, voice, voiceinfo, options)

    def _run_async(
        self,
        target: Callable[[], None],
        on_done: Callable[[], None] | None = None,
    ) -> PlaybackHandle:
        '''
        Runs target() (a zero-argument callable) in a background daemon
        thread, returning a PlaybackHandle that completes when it returns or
        raises. Shared by say_async()/play_async().

        :param target: zero-argument callable to run in the background
        :param on_done: optional callback fired (with no arguments) on completion
        :returns: a PlaybackHandle tracking target()'s completion
        '''
        handle = PlaybackHandle(self)
        if on_done:
            handle.on_done = on_done

        def _run() -> None:
            try:
                target()
            finally:
                handle._mark_done()

        threading.Thread(target=_run, daemon=True).start()
        return handle

    def say_async(
        self,
        phrase: str,
        on_done: Callable[[], None] | None = None,
        **_options: Any,
    ) -> PlaybackHandle:
        '''
        Like :meth:`say`, but returns immediately with a
        :class:`PlaybackHandle` instead of blocking until speech finishes.

        ``on_done``, if given, is called (with no arguments) once playback
        finishes.
        '''
        return self._run_async(lambda: self.say(phrase, **_options), on_done=on_done)

    def play(self, filename: str, translate: bool = False) -> None:  # pragma: no cover
        '''
        Plays the sounds.

        :filename: The input file name
        :translate: If True, it runs it through audioread which will translate from common compression formats to raw WAV.
        '''
        if translate:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                fname = f.name
            with audioread.audio_open(filename) as f:
                with contextlib.closing(wave.open(fname, 'w')) as of:
                    of.setnchannels(f.channels)
                    of.setframerate(f.samplerate)
                    of.setsampwidth(2)
                    for buf in f:
                        of.writeframes(buf)
            filename = fname

        if winsound:
            winsound.PlaySound(str(filename), winsound.SND_FILENAME)
        else:
            cmd = ['aplay', str(filename)]
            self._logger.debug('Executing %s', ' '.join([quote(arg) for arg in cmd]))
            proc = _popen_quietly(cmd, self.ioptions['quiet'])
            self._last_playback_proc = proc
            proc.wait()

        if translate:
            os.remove(fname)

    def play_async(
        self,
        filename: str,
        translate: bool = False,
        on_done: Callable[[], None] | None = None,
    ) -> PlaybackHandle:
        '''
        Like :meth:`play`, but returns immediately with a
        :class:`PlaybackHandle` instead of blocking until playback finishes.
        '''
        return self._run_async(lambda: self.play(filename, translate=translate), on_done=on_done)

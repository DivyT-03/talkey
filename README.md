# talkey

Simple Text-To-Speech (TTS) interface library with multi-language and multi-engine support.

[![CI](https://github.com/DivyT-03/talkey/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/DivyT-03/talkey/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/DivyT-03/talkey/branch/master/graph/badge.svg)](https://codecov.io/gh/DivyT-03/talkey)

Documentation: <http://talkey.readthedocs.org/>

## Rationale

I was really intrigued by the concept of jasper, a voice-controlled interface. I needed it to be
multi-lingual like me, so this library is my attempt to make having the TTS engines multi-lingual.
A lot of this code is inspired by the Jasper project.

## System Requirements

- Python 3.9 or later (CI-tested on 3.9-3.13)
- An installed TTS engine (see [Installing TTS engines](#installing-tts-engines) below), or network
  access to a MaryTTS server / Google Translate
- macOS, Linux (Ubuntu/Debian), Windows

## Basic Usage

Install from PyPI:

```shell
pip install talkey
```

At its simplest use case:

```python
import talkey
tts = talkey.Talkey()
tts.say('Old McDonald had a farm')
```

If you get a `talkey.base.TTSError: No supported languages` error, it means that you don't have a
supported TTS engine installed. Please see [Installing TTS engines](#installing-tts-engines) below.

By default it will try to locate and use the local instances of the following TTS engines:

- Flite
- SVOX Pico
- Festival
- eSpeak / eSpeak NG
- mbrola via eSpeak

Installing one or more of those engines should allow the library to function and generate speech.

It also supports the following networked TTS engines (disabled by default - opt in via
`options.enabled` as shown below):

- MaryTTS (needs a reachable server - note: the old public demo server `mary.dfki.de` is no longer
  online, so you'll need to self-host one or point at a different instance)
- Google TTS (cloud hosted; requires the `gtts` package - `pip install gtts`)

For best results you should configure it:

```python
import talkey
tts = talkey.Talkey(
    # These languages are given better scoring by the language detector
    # to minimise the chance of it detecting a short string completely incorrectly.
    # Order is not important here
    preferred_languages=['en', 'af', 'el', 'fr'],

    # The factor by which preferred_languages gets their score increased, defaults to 80.0
    preferred_factor=80.0,

    # The order of preference of using a TTS engine for a given language.
    # Note that networked engines (Google, Mary) are disabled by default, and so is dummy
    # default: ['google', 'mary', 'espeak', 'festival', 'pico', 'flite', 'dummy']
    # This sets eSpeak as the preferred engine, the other engines may still be used
    # if eSpeak doesn't support a requested language.
    engine_preference=['espeak'],

    # Here you segment the configuration by engine
    # Key is the engine SLUG, in this case `espeak`
    espeak={
        # Specify the engine options:
        'options': {
            'enabled': True,
            'quiet': True,  # suppress eSpeak/aplay console chatter
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
                'words_per_minute': 130,
            },
        },
    },
)
tts.say('Old McDonald had a farm')
```

### Suppressing console output

Every engine accepts a `quiet` option (default `False`, opt-in) that redirects the underlying
engine/player subprocess's stdout/stderr so it doesn't clutter your console:

```python
tts = talkey.Talkey(espeak={'options': {'quiet': True}})
```

### Non-blocking playback: stop and completion notification

`say()`/`Talkey.say()` block until speech finishes, same as always. For a non-blocking equivalent
that lets you stop playback early or get notified when it finishes, use `say_async()` on an
individual engine:

```python
from talkey.engines.espeak import EspeakTTS

engine = EspeakTTS()
handle = engine.say_async('This is a longer sentence...', on_done=lambda: print('done speaking'))

# ... do other work ...

handle.stop()          # best-effort: interrupts playback early
handle.wait(timeout=5)  # or just block until it finishes
print(handle.is_done())
```

`stop()` is a best-effort interruption: on POSIX it terminates the underlying player process; on
Windows, `winsound` has no per-sound handle, so it purges whatever sound is currently playing
system-wide (fine for talkey's normal one-sound-at-a-time usage, but not a per-handle guarantee if
you have multiple engines/handles active concurrently).

## Installing TTS engines

### Ubuntu/Debian

```shell
# Festival
sudo apt-get install festival

# Flite
sudo apt-get install flite

# SVOX Pico
sudo apt-get install libttspico-utils

# eSpeak
sudo apt-get install espeak

# mbrola and the en1 voice
sudo apt-get install mbrola-en1
```

### Windows

**eSpeak NG** (recommended - modern eSpeak NG is what you'll get from any current installer;
classic eSpeak is effectively unmaintained):

```powershell
winget install --id eSpeak-NG.eSpeak-NG
```

talkey looks for `espeak-ng`/`espeak` on PATH as well as the default eSpeak NG install locations
(`C:\Program Files\eSpeak NG\espeak-ng.exe` and the `(x86)` variant), so a default winget install
is found automatically without any extra configuration.

**Festival, Flite, SVOX Pico, mbrola**: none of these currently have an official Windows package
(checked via `winget`/`choco` - nothing available). They work great on Linux/macOS; on Windows,
your options are running talkey inside WSL, or sourcing/building an unofficial Windows port
yourself. Everything else in talkey works fine without them - `Talkey()` only uses whichever
engines are actually available.

**Google TTS**:

```shell
pip install gtts
```

Google TTS returns audio as MP3, which talkey transcodes via the `audioread` package (already a
dependency) before playback - no separate ffmpeg install is required on modern versions of talkey.

## Development / running the tests

```shell
pip install -e ".[dev]"
pytest -q                     # full suite
pytest -q -m mocked           # fast, no external engine/network dependency - runs anywhere
pytest -q -m integration      # needs real engine binaries/network; skips cleanly if unavailable
mypy talkey                   # type checking (every function is type-hinted)
pylint talkey                 # linting
```

See [CLAUDE.md](CLAUDE.md) for architecture notes, the engine plugin contract for adding a new
engine, and known environment caveats.

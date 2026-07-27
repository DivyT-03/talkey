# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`talkey` is a Python library that provides a unified interface over several Text-To-Speech (TTS)
engines (eSpeak/eSpeak NG, Festival, Flite, SVOX Pico, MaryTTS, Google TTS, macOS `say`, plus a
no-op `dummy` engine), with automatic language detection so `Talkey().say(text)` picks a matching
installed engine/voice for whatever language the text is in. It was originally written (~2015-2017)
against Python 2.7/early 3.x and had gone essentially unmaintained since; this repository has since
been revived: real breaks fixed, test coverage added, requested features implemented, and the whole
codebase brought up to modern standards (type hints, docstrings, mypy/pylint-checked).

## Functionalities

- **Multi-engine TTS** via a common `AbstractTTSEngine` interface - see "Engine plugin pattern"
  below. `Talkey` picks the first available, language-matching engine from a configurable
  preference order.
- **Automatic language detection** (`langid`), with `preferred_languages`/`preferred_factor`
  weighting to bias short/ambiguous text toward expected languages.
- **Per-engine, per-language voice configuration**: global defaults, per-engine defaults, and
  per-(engine, language) voice/option overrides, all validated through a shared option-spec schema.
- **Synchronous playback**: `say()`/`play()` block until speech finishes (the original, unchanged
  behavior).
- **Asynchronous playback with stop/completion notification**: `say_async()`/`play_async()` return
  a `PlaybackHandle` (`.wait()`, `.stop()`, `.is_done()`, `.on_done` callback) without blocking -
  added to address GH issues #4 ("stop" feature request) and #7 ("knowing when tts finished
  speaking").
- **Quiet mode**: a `quiet` init option (default `False`) suppresses the underlying engine/player
  subprocess's stdout/stderr chatter - added to address GH issue #3.
- **eSpeak NG support on Windows**: auto-detects eSpeak NG's default install location/binary name,
  correctly parses its CRLF/Unicode/combined-age-gender-field output format, and resolves voices by
  their underlying file identifier rather than display name (eSpeak NG's `-v` doesn't reliably
  resolve most display names) - added to address GH issue #6.

## Tech stack

- **Language**: Python. **Requires Python 3.9+** - the codebase now uses `from __future__ import
  annotations` plus PEP 585 lowercase generic type hints (`dict[str, Any]`, `list[str]`, `X | None`)
  throughout, which formally ends Python 2.7 compatibility (see "Python 2.7 is fully gone" under
  Caveats - this is a real, deliberate change from an earlier phase of this project's revival where
  Python 2.7 *syntax* compatibility was still being preserved).
- **Runtime dependencies**: `langid` (language detection), `requests` (MaryTTS HTTP calls),
  `audioread` (decodes compressed audio for playback transcoding). `gtts` is required only for the
  optional Google TTS engine (checked per-engine at runtime via `check_python_import`, not a hard
  package dependency).
- **Dev/test/type-check dependencies**: `pytest`, `pytest-cov`, `pylint`, `mypy` (install via
  `pip install -e ".[dev]"`).
- **Type checking**: every function/method in `talkey/` has type hints and a docstring; `mypy talkey`
  runs clean (see `[tool.mypy]` in `pyproject.toml` - `ignore_missing_imports = true` since
  `langid`/`gtts`/`audioread` ship no type stubs).
- **Packaging**: `pyproject.toml` (PEP 621 + setuptools backend); `setup.py` is a 2-line shim kept
  only for tools that still expect one. `README.md` (Markdown, not the original `README.rst`) is
  the packaging-level readme.
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) - a `lint` job (mypy + `pylint --fail-under=9.0`),
  a Linux test matrix (py3.9-3.13) that apt-installs `festival flite espeak libttspico-utils
  mbrola-en1` so integration tests run for real, and a Windows job running `pytest -m mocked` only.
- **External engines** (not Python packages, installed separately, entirely optional - `Talkey()`
  works with whatever subset is present): eSpeak/eSpeak NG, Festival, Flite, SVOX Pico, mbrola
  (voice add-on for eSpeak), a local `aplay`/`winsound`-capable audio setup. MaryTTS and Google TTS
  are network services instead of local binaries.

## Commands

Install with dev/test extras (editable):

```shell
pip install -e ".[dev]"
```

Run the full test suite:

```shell
pytest -q
```

Run only the fast, dependency-free tests (no TTS engine binaries/network needed - meaningful
signal on any machine, e.g. a fresh Windows checkout with nothing installed):

```shell
pytest -q -m mocked
```

Run only the integration-style tests (need a real engine binary or network service; skip cleanly
via `unittest.SkipTest` when unavailable rather than failing):

```shell
pytest -q -m integration
```

Run a single test file, class, or method:

```shell
pytest tests/test_engine_espeak.py
pytest tests/test_engine_espeak.py::EspeakTTSTest
pytest tests/test_engine_espeak.py::EspeakTTSTest::test_mbrola_language
```

With coverage:

```shell
pytest -q --cov=talkey --cov-report=term-missing
```

Type-check:

```shell
mypy talkey
```

Lint (full default ruleset; CI gates on `--fail-under=9.0`, not a perfect score - see Caveats):

```shell
pylint talkey
```

Across Python versions via tox (mirrors the GitHub Actions matrix):

```shell
tox
```

Docs are Sphinx-based under `docs/` (`docs/getting_started.rst`, `docs/usage.rst`,
`docs/engines.rst`); built via the standard `docs/Makefile`.

## Code architecture

### Engine plugin pattern

Every engine lives in `talkey/engines/<name>.py`, subclasses `AbstractTTSEngine` (`talkey/base.py`),
and is registered in the `_ENGINE_MAP` dict and `_ENGINE_ORDER` list in `talkey/engines/__init__.py`.
`enumerate_engines()` (`talkey/tts.py`) returns a *copy* of `_ENGINE_ORDER` - the default
engine-preference order used by `Talkey` (currently `google, mary, espeak, festival, pico, flite,
say, dummy` - networked engines and `dummy` are opt-in via config, not auto-selected, since they
default to `enabled: False`).

A new engine must implement 5 abstract methods; `AbstractTTSEngine` uses `metaclass=ABCMeta`, so
subclasses missing any of them raise `TypeError` at instantiation, not at first use:

- `_get_init_options() -> dict[str, dict[str, Any]]` (classmethod) - declares constructor options
  (executable paths, hosts, etc.), each a dict with `type` (`int`/`float`/`str`/`enum`/`bool`/`exec`),
  `default`, and optionally `min`/`max`/`values`. Validated centrally by `process_options()` in
  `talkey/utils.py`. Every engine automatically also gets `enabled` and `quiet` merged in via the
  base class's `get_init_options()` - no need to declare them yourself.
- `_is_available() -> bool` - whether the engine's dependency (binary/network service) is actually
  usable right now.
- `_get_options() -> dict[str, dict[str, Any]]` - declares per-utterance voice options (e.g.
  `words_per_minute`, `pitch_adjustment`), same option-spec format as above.
- `_get_languages() -> dict[str, dict[str, Any]]` - returns `{lang: {'default': voice_key, 'voices':
  {voice_key: {...}}}}` describing what the engine can currently speak. Whatever extra keys you put
  in a voice's info dict (e.g. eSpeak's `file` identifier) are passed through to `_say()` as
  `voiceinfo`.
- `_say(phrase, language, voice, voiceinfo, options) -> None` - actually synthesizes and plays the
  phrase. Use `talkey.base.run_quietly(cmd, self.ioptions['quiet'])` in place of
  `subprocess.call(cmd)` so the `quiet` option works, and use `self.ioptions[<exec option name>]`
  (never a hardcoded literal) when building the command.

Decorate the class with `@register` (from `talkey/base.py`) to auto-generate reST option docs into
the class docstring from `_get_init_options()`.

`AbstractTTSEngine.__init__` eagerly calls `is_available()`, and if available, caches
`get_options()` and `get_languages()` and calls `configure_default()` - so availability/capability
probing (e.g. shelling out to `espeak-ng --voices`) happens at construction time, not lazily.

### Option validation flow

All option dicts (init options and voice options) are validated through `process_options()` in
`talkey/utils.py`, which type-coerces and range/enum-checks values, raising `TTSError` (the
library's single exception type, `talkey/base.py`) on anything invalid. The `exec` type resolves
an executable name (or **list** of candidate names/paths, tried in order) to a full path via
`find_executable`/`check_executable` - this is how `espeak.py` handles both classic eSpeak and
eSpeak NG's different default install locations/binary names across platforms.

### Talkey orchestration (`talkey/tts.py`)

`Talkey.__init__` instantiates every engine in `engine_preference` order (defaulting to
`enumerate_engines()`), skipping any that raise `TTSError` during construction (this is also why
`self.engines` only ever contains *available* engines - `create_engine()` calls
`configure_default()` unconditionally, which raises for an unavailable engine before it's
appended), then unions all their supported languages and feeds that set to `langid.set_languages()`
so language detection is constrained to what's actually speakable. `classify()` uses `langid` with
a `preferred_languages`/`preferred_factor` score boost to bias short/ambiguous text toward expected
languages. `say()` classifies (unless `lang` is given), finds the first configured engine
supporting that language via `get_engine_for_lang()`, and calls `.say()` on it - so engine order in
`engine_preference` is a priority list, not a fallback-on-failure list.

### Audio playback: synchronous and async

`AbstractTTSEngine.play()`/`say()` (in `talkey/base.py`) remain fully synchronous/blocking,
unchanged in external behavior: `play()` uses `winsound` on Windows, else shells out to `aplay` via
`Popen`+`.wait()` (the `Popen` handle is stashed on `self._last_playback_proc` for `stop()` to find).
Engines write synthesized audio to a `NamedTemporaryFile`, call `self.play(fname)`, then delete the
file - this pattern is duplicated per-engine in each `_say()`, not centralized.

`play_async()`/`say_async()` are additive, non-blocking counterparts that return a
`PlaybackHandle` (`.wait(timeout=None)`, `.stop()`, `.is_done()`, settable `.on_done` callback).
Both are implemented via a single shared `AbstractTTSEngine._run_async(target, on_done)` helper
that runs the existing synchronous `play()`/`say()` in a background thread - no per-engine code
needed, every engine gets async support for free. `.stop()` is best-effort: on POSIX it terminates
the `aplay` `Popen` handle; on Windows, `winsound` has no per-sound handle, so it calls the global
`winsound.PlaySound(None, SND_PURGE)`, which only makes sense given today's one-sound-at-a-time
usage pattern.

### Test suite structure (`tests/`)

Split by concern: `tests/test_utils.py`, `tests/test_base.py`, `tests/test_tts.py`, and one
`tests/test_engine_<name>.py` per engine. `tests/_base.py` holds the shared `BaseTTSTest` mixin
(parameterized by class attributes `CLS`, `SLUG`, `INIT_ATTRS`, `CONF`, `OBJ_ATTRS`, `EVAL_PLAY`,
`FILE_TYPE`); it sets `__test__ = False` so pytest doesn't also collect it directly wherever it's
imported - concrete per-engine `*TTSTest` subclasses set `__test__ = True`. `tests/conftest.py`
monkey-patches `AbstractTTSEngine.play` to record the last-played file/args into the `LAST_PLAY`
dict instead of actually playing audio, identifying the produced format (`WAVE audio` /
`MPEG ADTS, layer III`) via a small stdlib-only sniffer (`wave.open()` + a raw MPEG-frame/ID3 magic
byte check) - **not** an external `file` command (see Caveats). `conftest.py` also exposes
`REAL_PLAY` (the pre-patch implementation) for the handful of tests that specifically need to
exercise `play()`'s own internals.

Every test is marked `@pytest.mark.mocked` (no external dependency, always runs) or
`@pytest.mark.integration` (needs a real engine binary/service; calls `self.skip_not_available()`
or an equivalent `unittest.SkipTest` guard and skips cleanly when the dependency is missing, rather
than failing). **Important pytest config note**: `pyproject.toml` sets
`python_classes = ["Test*", "*Test"]` - every test class in this suite is named `<Thing>Test`
(ending in, not starting with, "Test"), which pytest's default `python_classes = "Test*"` pattern
does **not** match for plain (non-`unittest.TestCase`) classes. Without this setting, such classes
are silently never collected at all (not even shown as skipped) - this bit us for real once (see
Caveats) - **always add new mocked test classes as either `unittest.TestCase` subclasses, or
confirm they show up in `pytest --collect-only` before trusting a green run.**

When adding a test for engine-specific parsing/escaping/option logic, prefer a mocked test (patch
`subprocess.call`/`check_output`/the relevant SDK call, mocking *before* constructing the engine
since `AbstractTTSEngine.__init__` eagerly calls `_get_languages()`) so it gives real signal on any
machine - reserve integration tests for actually exercising the real binary/service end-to-end.

## Logic notes / non-obvious behavior

- **eSpeak NG voice selection**: `_get_languages()` captures each voice's underlying `file`
  identifier (e.g. `gmw/en-US`, from the `--voices` output's File column) in `voiceinfo['file']`,
  and `_say()` passes that (not the display `VoiceName`) as `-v`'s argument - eSpeak NG's `-v` does
  not reliably resolve most display names, only language codes or file identifiers.
- **mbrola voice gating**: eSpeak NG lists mbrola-backed voices in the *plain* `--voices` output
  even when mbrola itself isn't configured/available (unlike classic eSpeak). `_get_languages()`
  explicitly drops any voice whose file starts with `mb` when `has_mbrola()` is `False`, so
  `mbrola='badexec'` (or a genuinely absent mbrola install) correctly removes mbrola voices from
  `.languages` rather than just having them fail at synthesis time.
- **Gender/age field normalization**: eSpeak NG always emits a combined `age/gender` token (e.g.
  `--/M`) in the column that classic eSpeak's parser expected to be a bare `M`/`F`/`-` (with a
  workaround for a rare 1.46 bug where it was sometimes omitted entirely, shifting columns).
  `fix_voice()` in `espeak.py` normalizes both cases to a bare gender char before anything else
  reads that column.
- **Voice priority (`pty`) scoring**: each language's `default` voice is chosen by lowest `pty`
  (eSpeak's own quality/priority ranking), tie-broken by shortest voice name for determinism.
- **`quiet` default is `False`**: opt-in silence, so upgrading doesn't change existing callers'
  console output by default.
- **`enumerate_engines()` returns a copy**: mutating the returned list must not corrupt the shared
  `_ENGINE_ORDER` global used by every future `Talkey()` construction.
- **`_configure()`'s `assert self.languages is not None` / `assert self.optionspec is not None`**:
  these aren't defensive/runtime-necessary - they exist purely to help mypy narrow the `Optional`
  types set in `__init__`, since `_assert_available()` already guarantees both are populated
  (they're set together, only when `self.available` is `True`).

## Caveats

- **Python 2.7 is fully gone, for real this time**: an earlier phase of this project's revival
  deliberately kept code *syntactically* valid on Python 2.7 (e.g. reverting a `metaclass=ABCMeta`
  class-definition that's a `SyntaxError` on 2.7, in favor of the `ABCMeta('_ABCBase', (object,),
  {})` construction-call idiom). Adding type hints via `from __future__ import annotations` changed
  that calculus completely: that `__future__` feature does not exist in Python 2.7's `__future__`
  module at all, so it's a hard `SyntaxError` on import, immediately, in every single file in
  `talkey/`. There is no partial/soft version of this - Python 2.7 cannot import this package at
  all anymore. Given that, the now-pointless Python-2-only fallback code paths were removed as dead
  weight: `subprocess32` (only needed pre-3.2), the `distutils.spawn`/`pipes.quote` version-guarded
  fallbacks in `utils.py` (both were 2.7 fallbacks; `shutil.which`/`shlex.quote` are unconditional
  now), and the `ABCMeta('_ABCBase', ...)` construction-call idiom itself (reverted to plain
  `class AbstractTTSEngine(metaclass=ABCMeta):`). `requires-python` in `pyproject.toml` was bumped
  to `>=3.9` to match reality (PEP 585 lowercase generics like `dict[str, Any]` need 3.9+ even
  under `from __future__ import annotations`, which only defers *evaluation*, not the parser's
  understanding of what a valid subscript target is at runtime if something ever does force
  evaluation, e.g. `typing.get_type_hints()`).
- **Windows engine availability**: Festival, Flite, SVOX Pico, and mbrola have no official Windows
  package (checked via `winget search` - nothing found); macOS `say` cannot run on any non-Darwin
  platform, full stop. On a Windows dev machine, only eSpeak/eSpeak NG (installed via
  `winget install --id eSpeak-NG.eSpeak-NG`), Google TTS, and (network permitting) MaryTTS can ever
  be real integration-tested locally - the rest necessarily skip there and get real coverage only
  in the Linux CI job (which apt-installs all of them). Mocked-logic tests exist for all of these
  engines' parsing/request-building logic specifically so *something* real still runs everywhere
  regardless of what's locally installed.
- **MaryTTS's public demo server is gone**: `mary.dfki.de` (referenced in the README/tests as the
  well-known public demo instance) no longer resolves in DNS at all - not a firewall/reachability
  issue, the hostname itself is gone. The integration test against it will skip indefinitely unless
  you point `host=`/`port=` at a self-hosted MaryTTS server. Mocked tests cover Mary's own
  URL-building and response-parsing logic independent of this.
- **The `file`-command bug (fixed)**: the test suite used to shell out to the external `file`
  command (via `tests/conftest.py`'s play-recording patch, and directly in
  `test_check_executable_found`) to identify produced audio format/verify `check_executable()`.
  `file` ships with Git for Windows but is **not** on PATH in a plain PowerShell/cmd session - this
  caused `test_class_say`, `test_create_basic`, and `test_check_executable_found` to fail whenever
  pytest was invoked outside Git Bash, even though the underlying code was fine. Fixed by replacing
  the format check with a pure-stdlib sniffer (`wave` module + magic bytes) and switching the
  executable-lookup test to check `sys.executable` instead of `'file'`.
- **The pytest collection blind spot (fixed)**: pytest's default `python_classes = "Test*"` only
  matches class names that *start* with "Test". Roughly 17 plain (non-`unittest.TestCase`) mocked
  test classes in this suite - all named `<Thing>Test`, ending in rather than starting with "Test" -
  were silently never collected at all for one full session (not even shown as skipped), giving
  false confidence in a reported "all passing" result. Fixed via
  `python_classes = ["Test*", "*Test"]` in `pyproject.toml`; once actually running, 2 of those
  hidden test files had real bugs that are now fixed. Lesson: after writing any new plain test
  class, confirm it appears in `pytest --collect-only`, don't just trust a green summary line.
- **Pylint reality check**: plain `pylint talkey` currently scores **~9.1/10** (CI gates at
  `--fail-under=9.0`, a regression floor, not a demand for perfection). What's still flagged is
  overwhelmingly `consider-using-f-string` (pre-existing `%`-style formatting, left alone - fixing
  it project-wide wasn't asked for and is unrelated churn) plus a handful of pre-existing style
  nits (import order, line length over pylint's 100-char default, one small duplicated `enabled:
  False` dict literal across 3 engines judged not worth abstracting per "three similar lines beats
  a premature abstraction"). None of it is a functional issue. Earlier in this project's revival,
  pylint was at points run with narrow `--disable=all --enable=<one-check>` invocations that
  reported misleadingly high scores (only measuring the one enabled check) - that history is why
  this note exists; always trust plain `pylint talkey` (or the CI job), not a filtered invocation.
- **Mypy passes clean** (`mypy talkey` → 0 issues across 13 files) but required a few targeted
  `# type: ignore` comments for patterns mypy can't model perfectly: the `winsound = None` fallback
  assignment (`type: ignore[assignment]`), and the Python-2-only `from urllib import urlencode`
  branch retained in `mary.py`'s try/except (dead on Python 3, but mypy still type-checks it;
  `type: ignore[attr-defined]`) - both are documented inline at the ignore site.

## Future scope / not done here

- **Mozilla/Coqui neural TTS engine** (GH issue #10): explicitly out of scope - a fundamentally
  different architecture (ML model + inference runtime) than every other engine here's thin
  CLI/HTTP wrapper, and a much larger, separate effort.
- **GH issue #9** ("module 'talkey' has no attribute 'Talkey'"): no reproducible code bug found;
  most likely a stale/broken old install or a local file/module named `talkey` shadowing the real
  package. Packaging fixes in this work remove one plausible partial-import-failure vector
  (the `pipes` `ImportError` on Python 3.13, GH #11) but this specific report couldn't be confirmed
  or directly fixed.
- **Full Windows integration coverage for Festival/Flite/Pico/mbrola**: would require either
  building/sourcing unofficial Windows binaries from each project's original (non-package-manager)
  site, or running everything inside WSL/a Linux container on the Windows box. Not pursued.
- **`winsound`'s per-sound stop/completion limitations**: if Windows ever needs *real* per-sound
  stop (not a global purge) or push-based completion notification (not thread-polling), that
  requires a different Windows audio API entirely (e.g. `pyaudio`/`sounddevice`), which was
  judged out of scope for this pass given the existing single-sound-at-a-time usage pattern.
- **Chasing a perfect pylint score / converting `%`-formatting to f-strings project-wide**: not
  done - see the Pylint reality check above. Would be a reasonable follow-up if wanted, but is
  cosmetic churn orthogonal to correctness/testing/type-safety.

# talkey examples

Runnable scripts demonstrating talkey's features. Install talkey first (from the repo root):

```shell
pip install -e .
```

Then run any script directly - they'll produce **audible speech** through your default audio
device using whatever TTS engine(s) are installed:

```shell
python examples/01_basic_usage.py
python examples/02_configured_usage.py
python examples/03_list_engines_and_voices.py   # no audio - just prints a diagnostic report
python examples/04_async_playback.py
python examples/05_multi_language.py
```

| Script | Demonstrates |
| --- | --- |
| `01_basic_usage.py` | The simplest possible use: `Talkey()` + `say()` |
| `02_configured_usage.py` | `preferred_languages`, `engine_preference`, per-engine options/defaults, `quiet` |
| `03_list_engines_and_voices.py` | Inspecting which engines are available and what languages/voices each found - run this first if `Talkey()` raises `No supported languages` |
| `04_async_playback.py` | `say_async()`, `.stop()`, `.wait()`, `.is_done()`, `on_done` |
| `05_multi_language.py` | Automatic per-phrase language detection via `classify()` |

If `01_basic_usage.py` raises `talkey.base.TTSError: No supported languages`, you don't have a
supported TTS engine installed/reachable - see the main [README](../README.md#installing-tts-engines)
for install instructions, then run `03_list_engines_and_voices.py` to confirm what talkey sees.

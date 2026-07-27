'''
The simplest possible use of talkey: construct a Talkey with defaults (it
auto-detects whatever TTS engines are installed) and say a phrase.

Run:
    python examples/01_basic_usage.py
'''
import talkey


def main() -> None:
    tts = talkey.Talkey()
    print('Available languages:', sorted(tts.languages))
    tts.say('Old McDonald had a farm')


if __name__ == '__main__':
    main()

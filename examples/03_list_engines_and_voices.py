'''
Diagnostic script: shows every registered engine, whether it's available on
this machine, and (if available) what languages/voices it found. Useful for
figuring out why `talkey.Talkey()` raised "No supported languages", or which
engine a given language will be routed to.

Run:
    python examples/03_list_engines_and_voices.py
'''
import talkey


def main() -> None:
    for slug in talkey.enumerate_engines():
        try:
            # Networked/opt-in engines (google, mary, dummy) default to
            # enabled=False - force them on here just to probe availability.
            # create_engine() raises TTSError if the engine turns out to be
            # unavailable (e.g. binary/network not found), which is the
            # common case here, not an error in this script.
            engine = talkey.create_engine(slug, options={'enabled': True})
        except talkey.TTSError:
            print(f'{slug:10s} not available on this machine')
            continue

        assert engine.languages is not None
        langs = sorted(engine.languages.keys())
        print(f'{slug:10s} available - {len(langs)} language(s): {langs}')
        for lang in langs[:3]:  # just a sample, some engines have 50+ languages
            voices = sorted(engine.languages[lang]['voices'].keys())
            default = engine.languages[lang]['default']
            print(f'             {lang}: default={default!r}, voices={voices}')


if __name__ == '__main__':
    main()

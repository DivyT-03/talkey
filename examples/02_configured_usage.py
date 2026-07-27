'''
Configuring talkey: engine preference order, preferred languages for more
reliable detection on short text, and per-engine options/voice defaults.

Run:
    python examples/02_configured_usage.py
'''
import talkey


def main() -> None:
    tts = talkey.Talkey(
        # These languages get a scoring boost from the language detector, to
        # reduce the chance of it misdetecting a short/ambiguous string.
        preferred_languages=['en', 'af', 'el', 'fr'],
        preferred_factor=80.0,

        # Prefer eSpeak; other engines are still used as a fallback for
        # languages eSpeak doesn't support.
        engine_preference=['espeak'],

        espeak={
            'options': {
                'enabled': True,
                'quiet': True,  # suppress eSpeak/aplay console chatter
            },
            'defaults': {
                'words_per_minute': 150,
                'variant': 'f4',
            },
        },
    )

    print('Engines available on this machine:', [e.SLUG for e in tts.engines])
    tts.say('Old McDonald had a farm')


if __name__ == '__main__':
    main()

'''
Automatic language detection: classify() picks a language for you, and
say() routes each phrase to whichever configured engine supports it.

Run:
    python examples/05_multi_language.py
'''
import talkey


def main() -> None:
    tts = talkey.Talkey(preferred_languages=['en', 'af', 'fr', 'de'])

    phrases = [
        'Old McDonald had a farm',
        "Ou boer McDonald het 'n plaas gehad",  # Afrikaans
        'Le renard brun rapide saute par-dessus le chien paresseux',  # French
    ]

    for phrase in phrases:
        lang = tts.classify(phrase)
        try:
            engine = tts.get_engine_for_lang(lang)
            print(f'{phrase!r} -> detected {lang!r}, speaking via {engine.SLUG!r}')
            tts.say(phrase, lang=lang)
        except talkey.TTSError as exc:
            print(f'{phrase!r} -> detected {lang!r}, but no engine supports it ({exc})')


if __name__ == '__main__':
    main()

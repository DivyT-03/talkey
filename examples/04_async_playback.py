'''
Non-blocking playback: say_async() returns immediately with a handle that
supports stop(), wait(), is_done(), and an on_done completion callback.

Run:
    python examples/04_async_playback.py
'''
import time

from talkey.tts import create_engine


def main() -> None:
    # Talking to a single engine directly here (rather than via Talkey) since
    # say_async()/stop()/wait() live on AbstractTTSEngine.
    engine = create_engine('espeak', options={'enabled': True, 'quiet': True})
    if not engine.is_available():
        print("eSpeak isn't available on this machine - install it and re-run.")
        return

    print('Starting a long sentence asynchronously...')
    done = {'called': False}
    handle = engine.say_async(
        'This is a fairly long sentence, so we have time to demonstrate stopping it early.',
        on_done=lambda: done.update(called=True),
    )

    print('...doing other work while it speaks...')
    time.sleep(1)

    print('Stopping playback early.')
    handle.stop()

    finished = handle.wait(timeout=5)
    print(f'wait() returned {finished}, is_done()={handle.is_done()}, on_done fired={done["called"]}')

    # A second call that's allowed to finish naturally, to show on_done
    # firing without an explicit stop().
    print('\nSaying a short phrase and waiting for the on_done callback...')
    handle2 = engine.say_async('All done.', on_done=lambda: print('  -> on_done fired!'))
    handle2.wait()


if __name__ == '__main__':
    main()

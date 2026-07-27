'''
Shared pytest fixtures/monkeypatches for the talkey test suite.
'''
import wave

from talkey.base import AbstractTTSEngine

# Records the most recent call to AbstractTTSEngine.play(), instead of
# actually playing audio. A dict (not a rebound module global) so every test
# module can `from tests.conftest import LAST_PLAY` once and always see the
# current contents via key access.
LAST_PLAY = {}

# Saved before monkeypatching below, so tests that specifically want to
# exercise the real play() implementation (e.g. its async/Popen internals)
# can temporarily restore it.
REAL_PLAY = AbstractTTSEngine.play


def _sniff_audio_format(filename):
    '''
    Identifies a produced audio file as 'WAVE audio' or 'MPEG ADTS, layer III'
    (the two formats talkey's engines ever produce), using only the stdlib -
    no dependency on an external `file` command, which isn't reliably on
    PATH on Windows outside a Git Bash shell (previously caused
    test_class_say/test_create_basic to fail whenever pytest was invoked
    from a plain PowerShell/cmd session).
    '''
    try:
        with wave.open(filename, 'rb'):
            return 'WAVE audio'
    except wave.Error:
        pass

    with open(filename, 'rb') as f:
        header = f.read(4)
    # gTTS output is a raw MPEG frame (11 set sync bits), optionally preceded
    # by an ID3v2 tag on some gTTS/ffmpeg versions.
    if header[:3] == b'ID3' or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
        return 'MPEG ADTS, layer III'
    return 'unknown'


def _fakeplay(self, filename, translate=False):
    output = _sniff_audio_format(filename)
    LAST_PLAY.clear()
    LAST_PLAY.update(inst=self, filename=filename, output=output)


# Patch AbstractTTSEngine.play to record its params instead of playing audio.
# Really need to make this loosely connected.
AbstractTTSEngine.play = _fakeplay

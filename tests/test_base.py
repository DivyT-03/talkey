'''
Tests for talkey.base: abstract-method enforcement, the 'quiet' subprocess
option (GH #3), and async playback/stop/completion notification (GH #4/#7).
'''
import subprocess
from unittest import mock

import pytest

try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest

from talkey.base import AbstractTTSEngine, run_quietly
from talkey.engines.dummy import DummyTTS

from tests.conftest import REAL_PLAY


@pytest.mark.mocked
class AbstractMethodEnforcementTest(unittest.TestCase):
    '''
    Regression test: AbstractTTSEngine used the Python-2-only
    `__metaclass__ = ABCMeta` spelling, which is inert in Python 3 - subclasses
    missing required methods used to instantiate fine. Locks in that
    `metaclass=ABCMeta` actually enforces the abstract methods now.
    '''

    def test_incomplete_subclass_cannot_instantiate(self):
        class Incomplete(AbstractTTSEngine):
            @classmethod
            def _get_init_options(cls):
                return {}

            def _is_available(self):
                return True

            def _get_options(self):
                return {}

            def _get_languages(self):
                return {}
            # _say deliberately not implemented

        with self.assertRaises(TypeError):
            Incomplete()

    def test_complete_subclass_instantiates(self):
        # DummyTTS implements all 5 abstract methods - must be unaffected.
        self.assertTrue(DummyTTS(enabled=True).SLUG, 'dummy')


@pytest.mark.mocked
class RunQuietlyTest(unittest.TestCase):

    @mock.patch('talkey.base.subprocess.call')
    def test_quiet_true_silences_output(self, mock_call):
        run_quietly(['echo', 'hi'], True)
        _, kwargs = mock_call.call_args
        self.assertEqual(kwargs.get('stdout'), subprocess.DEVNULL)
        self.assertEqual(kwargs.get('stderr'), subprocess.DEVNULL)

    @mock.patch('talkey.base.subprocess.call')
    def test_quiet_false_leaves_output_alone(self, mock_call):
        run_quietly(['echo', 'hi'], False)
        _, kwargs = mock_call.call_args
        self.assertNotIn('stdout', kwargs)
        self.assertNotIn('stderr', kwargs)


@pytest.mark.mocked
class AsyncPlaybackTest(unittest.TestCase):
    '''
    say_async()/play_async() reuse the existing synchronous say()/play() in a
    background thread, so they work uniformly across every engine (tested
    here against DummyTTS, which needs no real audio backend) with no
    per-engine code changes.
    '''

    def test_say_async_returns_handle_and_completes(self):
        obj = DummyTTS(enabled=True)
        handle = obj.say_async('hello from async test')
        self.assertTrue(handle.wait(timeout=2), 'playback did not finish in time')
        self.assertTrue(handle.is_done())

    def test_say_async_on_done_callback_fires(self):
        obj = DummyTTS(enabled=True)
        done = {'called': False}
        handle = obj.say_async('hello', on_done=lambda: done.update(called=True))
        handle.wait(timeout=2)
        self.assertTrue(done['called'])

    def test_say_is_still_blocking(self):
        # say() must remain synchronous/behavior-neutral.
        obj = DummyTTS(enabled=True)
        result = obj.say('hello')
        self.assertIsNone(result)

    @mock.patch.object(AbstractTTSEngine, 'play', REAL_PLAY)
    @mock.patch('talkey.base.winsound', None)
    @mock.patch('talkey.base._popen_quietly')
    def test_play_async_posix_stop_terminates_process(self, mock_popen):
        # AbstractTTSEngine.play is globally monkeypatched by conftest for
        # the rest of the suite (to avoid real playback) - restore the real
        # implementation just for this test, since it's specifically testing
        # play()'s own Popen-based internals.
        mock_proc = mock.Mock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        obj = DummyTTS(enabled=True)
        handle = obj.play_async(__file__)  # any existing path; playback itself is mocked
        # Wait for play_async's background thread to reach proc.wait() (and
        # so definitely have assigned _last_playback_proc) before calling
        # stop(), instead of racing the thread - proc.poll() stays mocked to
        # 'still running' regardless, so stop() still exercises terminate().
        handle.wait(timeout=2)
        handle.stop()
        mock_proc.terminate.assert_called_once()

    @mock.patch('talkey.base.winsound')
    def test_stop_on_windows_purges_globally(self, mock_winsound):
        obj = DummyTTS(enabled=True)
        handle = obj.say_async('hello')
        handle.wait(timeout=2)
        handle.stop()
        mock_winsound.PlaySound.assert_called_with(None, mock_winsound.SND_PURGE)

'''
Tests for talkey.utils: option validation, executable lookup, and the
shlex/pipes quote() compatibility shim.
'''
import shlex
import sys

import pytest

try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest

from talkey.base import TTSError
from talkey.utils import check_executable, process_options, quote


@pytest.mark.mocked
class CheckExecutableTest(unittest.TestCase):

    def test_check_executable_found(self):
        # sys.executable is guaranteed to exist and be executable in any
        # Python environment, unlike the external 'file' command this test
        # used to depend on (not on PATH outside a Git Bash shell on
        # Windows, which caused spurious failures under plain PowerShell/cmd).
        self.assertTrue(check_executable(sys.executable))

    def test_check_executable_not_found(self):
        self.assertFalse(check_executable('aieaoauu_not-findable_lfsdauybqwer'))


@pytest.mark.mocked
class QuoteShimTest(unittest.TestCase):
    '''
    Regression test for GH #11: 'pipes' was removed in Python 3.13. Locks in
    that talkey.utils.quote() behaves like shlex.quote() regardless of
    whether it's actually backed by shlex or the pipes fallback.
    '''

    def test_quote_matches_shlex(self):
        for value in ['plain', 'has space', 'has"quote', "has'quote", '', 'a&b|c']:
            self.assertEqual(quote(value), shlex.quote(value))


@pytest.mark.mocked
class ProcessOptionsTest(unittest.TestCase):

    def test_process_options_unknown_param(self):
        with self.assertRaisesRegex(TTSError, 'Unknown options'):
            process_options({}, {'test': 'fail'}, TTSError)

    def test_process_options_bad_type(self):
        with self.assertRaisesRegex(TTSError, 'Bad type: garbage'):
            process_options({'test': {'type': 'garbage'}}, {'test': 'fail'}, TTSError)

    def test_process_options_default_none(self):
        spec = {'test': {'type': 'str'}}
        ret = process_options(spec, {}, TTSError)
        self.assertEqual(ret, {'test': None})

    def test_process_options_default_provided(self):
        spec = {'test': {'type': 'str', 'default': 'moo'}}
        ret = process_options(spec, {}, TTSError)
        self.assertEqual(ret, {'test': 'moo'})

    def test_process_options_bool(self):
        spec = {'test': {'type': 'bool'}}
        ret = process_options(spec, {}, TTSError)
        self.assertEqual(ret, {'test': False})
        ret = process_options(spec, {'test': 'yEs'}, TTSError)
        self.assertEqual(ret, {'test': True})

    def test_process_options_int(self):
        spec = {'test': {'type': 'int', 'min': 5, 'max': 8}}
        with self.assertRaises(TypeError):
            process_options(spec, {}, TTSError)
        ret = process_options(spec, {'test': '6'}, TTSError)
        self.assertEqual(ret, {'test': 6})
        ret = process_options(spec, {'test': '6.2'}, TTSError)
        self.assertEqual(ret, {'test': 6})
        ret = process_options(spec, {'test': 6}, TTSError)
        self.assertEqual(ret, {'test': 6})
        ret = process_options(spec, {'test': 6.1}, TTSError)
        self.assertEqual(ret, {'test': 6})

    def test_process_options_int_min(self):
        with self.assertRaisesRegex(TTSError, 'Min is 5'):
            process_options({'test': {'type': 'int', 'min': 5}}, {'test': 3}, TTSError)
        process_options({'test': {'type': 'int'}}, {'test': 3}, TTSError)

    def test_process_options_int_max(self):
        with self.assertRaisesRegex(TTSError, 'Max is 8'):
            process_options({'test': {'type': 'int', 'max': 8}}, {'test': 10}, TTSError)
        process_options({'test': {'type': 'int'}}, {'test': 10}, TTSError)

    def test_process_options_float(self):
        spec = {'test': {'type': 'float', 'min': 5.2, 'max': 8.9}}
        with self.assertRaises(TypeError):
            process_options(spec, {}, TTSError)
        ret = process_options(spec, {'test': '6'}, TTSError)
        self.assertEqual(ret, {'test': 6.0})
        ret = process_options(spec, {'test': '6.2'}, TTSError)
        self.assertEqual(ret, {'test': 6.2})
        ret = process_options(spec, {'test': 6}, TTSError)
        self.assertEqual(ret, {'test': 6.0})
        ret = process_options(spec, {'test': 6.1}, TTSError)
        self.assertEqual(ret, {'test': 6.1})

    def test_process_options_float_min(self):
        with self.assertRaisesRegex(TTSError, 'Min is 5.2'):
            process_options({'test': {'type': 'float', 'min': 5.2}}, {'test': 3}, TTSError)
        process_options({'test': {'type': 'float'}}, {'test': 3}, TTSError)

    def test_process_options_float_max(self):
        with self.assertRaisesRegex(TTSError, 'Max is 8.9'):
            process_options({'test': {'type': 'float', 'max': 8.9}}, {'test': 10}, TTSError)
        process_options({'test': {'type': 'float'}}, {'test': 10}, TTSError)

    def test_process_options_enum(self):
        spec = {'test': {'type': 'enum', 'values': ['one', 'two', 'four']}}
        with self.assertRaisesRegex(TTSError, 'Bad test value: None'):
            process_options(spec, {}, TTSError)
        with self.assertRaisesRegex(TTSError, 'Bad test value: three'):
            process_options(spec, {'test': 'three'}, TTSError)
        ret = process_options(spec, {'test': 'two'}, TTSError)
        self.assertEqual(ret, {'test': 'two'})

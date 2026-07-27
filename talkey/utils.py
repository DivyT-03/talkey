# -*- coding: utf-8-*-
'''
Small standalone helpers used across talkey: executable/network/import
probing, and the option-spec validation engines rely on for their init and
voice options.
'''
from __future__ import annotations

import logging
import socket
import importlib.util
from shlex import quote  # noqa: F401  pylint: disable=unused-import
from shutil import which as _find_executable
from typing import Any, Iterable, Type

# quote() is re-exported for other modules (base.py, engines/*.py) to import
# from here - it looks unused in this file itself.


def find_executable(executable: str) -> str | None:
    '''
    Finds an executable in PATH (or resolves it directly if given an
    absolute path).

    :param executable: the executable name (e.g. "espeak") or path to look up
    :returns: the resolved path, or None if it couldn't be found
    '''
    logger = logging.getLogger(__name__)
    logger.debug("Checking executable '%s'...", executable)
    executable_path = _find_executable(executable)
    found = executable_path is not None
    if found:
        logger.debug("Executable '%s' found: '%s'", executable, executable_path)
    else:
        logger.debug("Executable '%s' not found", executable)
    return executable_path


def check_executable(executable: str) -> bool:
    '''
    Checks if an executable exists in $PATH.

    :param executable: the name of the executable (e.g. "echo")
    :returns: True if found, False otherwise
    '''
    return find_executable(executable) is not None


def check_network_connection(server: str, port: int) -> bool:
    '''
    Checks whether a TCP connection can be established to server:port.

    :param server: hostname or IP address to connect to
    :param port: TCP port to connect to
    :returns: True if a connection could be established, False otherwise
    '''
    logger = logging.getLogger(__name__)
    logger.debug("Checking network connection to server '%s'...", server)
    try:
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(server)
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection((host, port), 2)
        sock.close()
    except Exception:  # pragma: no cover  pylint: disable=broad-exception-caught
        logger.debug("Network connection not working")
        return False
    logger.debug("Network connection working")
    return True


def check_python_import(package_or_module: str) -> bool:
    '''
    Checks if a python package or module is importable, without actually
    importing it.

    :param package_or_module: the package or module name to check
    :returns: True if importable, False otherwise
    '''
    logger = logging.getLogger(__name__)
    logger.debug("Checking python import '%s'...", package_or_module)
    try:
        found = importlib.util.find_spec(package_or_module) is not None
    except (ImportError, ValueError):  # pragma: no cover
        found = False
    if found:
        logger.debug("Python import '%s' found", package_or_module)
    else:  # pragma: no cover
        logger.debug("Python import '%s' not found", package_or_module)
    return found


def voice_codes_to_lang_tree(voice_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
    '''
    Builds a _get_languages()-style {lang: {'default':, 'voices': {}}} tree
    from a flat iterable of voice codes whose first 2 characters are the
    language code (e.g. 'en', 'en-us') - shared by engines (google, pico)
    whose voice codes double as both language and voice identifier.

    :param voice_codes: flat iterable of voice code strings
    :returns: a language tree in the shape AbstractTTSEngine._get_languages() expects
    '''
    langs: dict[str, dict[str, Any]] = {}
    for voice in voice_codes:
        lang = voice[:2]
        langs.setdefault(lang, {'default': voice, 'voices': {}})
        langs[lang]['voices'][voice] = {}
    return langs


def process_options(
    valid_options: dict[str, dict[str, Any]],
    _options: dict[str, Any],
    error: Type[Exception],
) -> dict[str, Any]:
    '''
    Validates and type-coerces a dict of options against an option-spec dict
    (as returned by an engine's _get_init_options()/_get_options()).

    :param valid_options: option-spec dict describing each allowed option's
        type/default/min/max/values
    :param _options: the raw option values to validate (missing keys fall
        back to each option's declared default)
    :param error: exception class to raise on validation failure (always
        ``talkey.base.TTSError`` in practice)
    :returns: a dict of validated, type-coerced option values
    :raises Exception: an instance of ``error`` if an option is unknown, has
        a value of the wrong type, or is out of range
    '''
    unknown_options = set(_options.keys()).difference(valid_options.keys())
    if unknown_options:
        raise error('Unknown options: %s' % ', '.join(unknown_options))

    options = dict((key, _options.get(key, val.get('default', None))) for key, val in valid_options.items())
    for option in options.keys():
        val: Any = options[option]
        data = valid_options[option]
        typ = data['type']
        if typ not in ['int', 'float', 'str', 'enum', 'bool', 'exec']:
            raise error('Bad type: %s for option %s' % (typ, option), ['int', 'float', 'str', 'enum', 'bool'])
        keys = data.keys()
        if typ == 'int':
            val = int(float(val))
        if typ == 'float':
            val = float(val)
        if typ in ['int', 'float']:
            if 'min' in keys:
                if val < data['min']:
                    raise error('Bad %s: %s' % (option, val), 'Min is %s' % data['min'])
            if 'max' in keys:
                if val > data['max']:
                    raise error('Bad %s: %s' % (option, val), 'Max is %s' % data['max'])
        if typ == 'enum':
            if val not in data['values']:
                raise error('Bad %s value: %s' % (option, val), data['values'])
        if typ == 'bool':
            val = True if str(val).lower() in ['y', '1', 'yes', 'true', 't'] else False
        if typ == 'exec':
            if isinstance(val, list):
                vals = val
                for val in vals:
                    val = find_executable(val)
                    if val:
                        break
            else:
                val = find_executable(val)
        options[option] = val
    return options

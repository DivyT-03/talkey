'''
Engine registry: maps each engine SLUG to its AbstractTTSEngine subclass, and
declares the default engine-preference order used by Talkey.
'''
from __future__ import annotations

from typing import Type

from ..base import AbstractTTSEngine
from .dummy import DummyTTS
from .espeak import EspeakTTS
from .festival import FestivalTTS
from .flite import FliteTTS
from .google import GoogleTTS
from .mary import MaryTTS
from .pico import PicoTTS
from .say import SayTTS

_ENGINE_MAP: dict[str, Type[AbstractTTSEngine]] = {
    'dummy': DummyTTS,
    'espeak': EspeakTTS,
    'flite': FliteTTS,
    'festival': FestivalTTS,
    'google': GoogleTTS,
    'mary': MaryTTS,
    'pico': PicoTTS,
    'say': SayTTS,
}

_ENGINE_ORDER: list[str] = ['google', 'mary', 'espeak', 'festival', 'pico', 'flite', 'say', 'dummy']

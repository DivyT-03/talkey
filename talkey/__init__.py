'''
Simple Text-To-Speech (TTS) interface library with multi-language and multi-engine support.
'''
from .tts import Talkey, enumerate_engines, create_engine, TTSError

__all__ = ['Talkey', 'enumerate_engines', 'create_engine', 'TTSError', '__version__']

__version__: str = '0.2.0'

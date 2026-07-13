"""
TTS (Text-to-Speech) module with Doubao (Volcano Engine) provider.
"""

from .base import BaseTTSSynthesizer, AudioSegment, AudioResult
from .doubao_provider import DoubaoTTSSynthesizer

__all__ = [
    "BaseTTSSynthesizer",
    "AudioSegment",
    "AudioResult",
    "DoubaoTTSSynthesizer",
]

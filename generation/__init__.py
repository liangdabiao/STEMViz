"""
Generation module for STEM video production.

This module contains components for:
- Script generation using Doubao multimodal video understanding
- Audio synthesis using Doubao TTS
- Video composition
"""

from .script_generator import ScriptGenerator

__all__ = ['ScriptGenerator']

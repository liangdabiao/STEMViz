# TTS Multi-Provider Usage Guide

## Overview

The STEMViz TTS system now supports multiple providers that can be swapped via configuration. Currently supported providers:

- **ElevenLabs** (default) - High-quality voice synthesis with extensive customization
- **OpenAI** - Reliable TTS with multiple voice options

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# TTS Provider Selection
TTS_PROVIDER=elevenlabs  # or "openai"

# ElevenLabs Configuration (required if using ElevenLabs)
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# OpenAI Configuration (required if using OpenAI)
OPENAI_API_KEY=your_openai_api_key

# Optional OpenAI compatible endpoint
OPENAI_ENDPOINT='........'
```

### Provider-Specific Settings

#### ElevenLabs Settings
```python
# In config.py or environment variables
elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
elevenlabs_model_id: str = "eleven_multilingual_v2"
elevenlabs_stability: float = 0.75
elevenlabs_similarity_boost: float = 0.75
elevenlabs_style: float = 0.0
elevenlabs_use_speaker_boost: bool = True
```

#### OpenAI Settings
```python
# In config.py or environment variables
openai_voice: str = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
openai_model: str = "tts-1"  # tts-1, tts-1-hd
openai_response_format: str = "mp3"
openai_speed: float = 1.0    # 0.25 to 4.0
```

## Usage Examples

### Switching Providers

#### Using ElevenLabs (Default)
```bash
# .env file
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_key_here
```

#### Using OpenAI
```bash
# .env file
TTS_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

### Programmatic Usage

```python
from config import get_settings
from generation.tts.elevenlabs_provider import ElevenLabsTTSSynthesizer
from generation.tts.openai_provider import OpenAITTSSynthesizer

settings = get_settings()

# Create provider based on configuration
if settings.tts_provider == "elevenlabs":
    synthesizer = ElevenLabsTTSSynthesizer(
        api_key=settings.elevenlabs_api_key,
        output_dir=settings.audio_dir,
        voice_id=settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_model_id
    )
elif settings.tts_provider == "openai":
    synthesizer = OpenAITTSSynthesizer(
        api_key=settings.openai_api_key,
        output_dir=settings.audio_dir,
        voice=settings.openai_voice,
        model=settings.openai_model
    )

# Generate audio
result = synthesizer.execute("script.srt", target_duration=120.0)
```

## Adding New Providers

To add a new TTS provider:

1. Create `generation/tts/newprovider_provider.py`
2. Inherit from `BaseTTSSynthesizer`
3. Implement the `execute` method
4. Add configuration options to `config.py`
5. Update pipeline `_create_tts_synthesizer` method

Example:
```python
# generation/tts/newprovider_provider.py
from .base import BaseTTSSynthesizer, AudioResult

class NewProviderTTSSynthesizer(BaseTTSSynthesizer):
    def __init__(self, api_key: str, output_dir: Path, **kwargs):
        super().__init__(api_key, output_dir, **kwargs)
        # Initialize provider-specific client

    def execute(self, script_path: str, target_duration: Optional[float] = None) -> AudioResult:
        # Implement provider-specific synthesis
        pass
```

### Debug Logging

Enable debug logging to troubleshoot issues:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

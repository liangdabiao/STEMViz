import logging
import time
import uuid
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import requests

from .base import BaseTTSSynthesizer, AudioSegment, AudioResult


class DoubaoTTSSynthesizer(BaseTTSSynthesizer):
    """Doubao (Volcano Engine) TTS provider implementation

    Supports two auth modes:
    - New console: X-Api-Key + X-Api-Resource-Id
    - Old console: X-Api-App-Id + X-Api-Access-Key + X-Api-Resource-Id
    """

    TTS_BASE_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

    def __init__(
        self,
        api_key: str = "",
        output_dir: Path = None,
        voice_id: str = "zh_female_vv_jupiter_bigtts",
        resource_id: str = "seed-tts-2.0",
        speed_ratio: float = 0.0,
        volume_ratio: float = 0.0,
        app_id: str = "",
        access_key: str = "",
        secret_key: str = "",
        auth_mode: str = "auto",  # "auto", "new", "old"
        **kwargs
    ):
        super().__init__(api_key, output_dir, **kwargs)

        # Voice settings
        self.voice_id = voice_id
        self.resource_id = resource_id
        self.speed_ratio = speed_ratio
        self.volume_ratio = volume_ratio

        # Old console credentials
        self.app_id = app_id
        self.access_key = access_key
        self.secret_key = secret_key

        # Determine auth mode
        self.auth_mode = self._determine_auth_mode(auth_mode, api_key, app_id, access_key)

        self.logger.info(f"Doubao TTS initialized")
        self.logger.info(f"  Voice: {voice_id}")
        self.logger.info(f"  Resource: {resource_id}")
        self.logger.info(f"  Auth mode: {self.auth_mode}")

    def _determine_auth_mode(self, auth_mode: str, api_key: str, app_id: str, access_key: str) -> str:
        """Determine which auth mode to use"""
        if auth_mode == "new":
            return "new"
        if auth_mode == "old":
            return "old"
        # Auto-detect
        if api_key and api_key.strip():
            return "new"
        if app_id and access_key:
            return "old"
        # Default to new mode if nothing specified (will fail later)
        return "new"

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers based on auth mode"""
        request_id = str(uuid.uuid4())
        headers = {
            "X-Api-Request-Id": request_id,
            "X-Api-Resource-Id": self.resource_id,
            "Content-Type": "application/json"
        }

        if self.auth_mode == "new":
            headers["X-Api-Key"] = self.api_key
        else:  # old mode
            headers["X-Api-App-Id"] = self.app_id
            headers["X-Api-Access-Key"] = self.access_key

        return headers

    def execute(self, script_path: str, target_duration: Optional[float] = None) -> AudioResult:
        """
        Convert SRT script to synchronized audio using Doubao TTS

        Args:
            script_path: Path to SRT script file
            target_duration: Optional target duration to match video

        Returns:
            AudioResult with generated audio file and metadata
        """
        start_time = time.time()
        self.logger.info(f"Starting Doubao audio synthesis for script: {script_path}")

        try:
            # Validate script file
            script_file = Path(script_path)
            if not script_file.exists():
                raise FileNotFoundError(f"Script file not found: {script_path}")

            # Parse SRT file
            subtitles = self._parse_srt_file(script_file)
            if not subtitles:
                raise ValueError("No subtitles found in SRT file")

            self.logger.info(f"Parsed {len(subtitles)} subtitles from script")

            # Generate audio for each subtitle
            audio_segments = self._generate_audio_segments(subtitles)

            if not audio_segments:
                raise ValueError("Failed to generate audio for any subtitles")

            # Concatenate audio segments
            final_audio_path = self._concatenate_audio_segments(audio_segments, script_file.stem)

            # Validate audio duration
            actual_duration = self._get_audio_duration(final_audio_path)
            if target_duration and actual_duration:
                # Add silence padding if needed
                if actual_duration < target_duration:
                    final_audio_path = self._add_silence_padding(
                        final_audio_path, target_duration - actual_duration
                    )
                    actual_duration = target_duration

            # Calculate file size
            file_size_mb = final_audio_path.stat().st_size / (1024 * 1024)

            generation_time = time.time() - start_time
            self.logger.info(f"Doubao audio synthesis completed in {generation_time:.2f}s")
            self.logger.info(f"Generated audio: {actual_duration:.2f}s, {file_size_mb:.2f}MB")

            return AudioResult(
                success=True,
                audio_path=str(final_audio_path),
                audio_segments=audio_segments,
                total_duration=actual_duration,
                file_size_mb=file_size_mb,
                generation_time=generation_time,
                model_used=self.resource_id,
                voice_settings={
                    "voice_id": self.voice_id,
                    "resource_id": self.resource_id,
                    "speed_ratio": self.speed_ratio,
                    "volume_ratio": self.volume_ratio,
                    "auth_mode": self.auth_mode
                }
            )

        except Exception as e:
            self.logger.error(f"Doubao audio synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            return AudioResult(
                success=False,
                error_message=str(e),
                generation_time=time.time() - start_time,
                model_used=self.resource_id
            )

    def _generate_audio_segments(self, subtitles: List[Dict[str, Any]]) -> List[AudioSegment]:
        """Generate audio for each subtitle using Doubao TTS"""

        audio_segments = []

        for subtitle in subtitles:
            self.logger.info(f"Generating Doubao audio for subtitle {subtitle['sequence']}: {subtitle['text'][:50]}...")

            for attempt in range(self.max_retries):
                try:
                    # Generate audio using Doubao TTS API
                    audio_data = self._call_tts_api(subtitle['text'])

                    # Save audio segment to temporary file
                    segment_path = self._save_audio_segment(audio_data, subtitle['sequence'])

                    # Get actual duration
                    actual_duration = self._get_audio_duration(segment_path)

                    audio_segment = AudioSegment(
                        text=subtitle['text'],
                        start_time=subtitle['start_time'],
                        end_time=subtitle['end_time'],
                        audio_path=str(segment_path),
                        duration=actual_duration,
                        file_size=segment_path.stat().st_size / (1024 * 1024)
                    )

                    audio_segments.append(audio_segment)
                    self.logger.info(f"Generated Doubao audio segment: {actual_duration:.2f}s")
                    break

                except Exception as e:
                    self.logger.warning(f"Doubao TTS failed for subtitle {subtitle['sequence']} (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        self.logger.error(f"Failed to generate Doubao audio for subtitle {subtitle['sequence']}")
                        break

        return audio_segments

    def _call_tts_api(self, text: str) -> bytes:
        """Call Doubao TTS API and return audio bytes"""

        headers = self._build_headers()

        # Request body in the correct format per API docs
        payload = {
            "user": {
                "uid": "stemviz_user"
            },
            "req_params": {
                "text": text,
                "speaker": self.voice_id,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000,
                    "speech_rate": self.speed_ratio,
                    "loudness_rate": self.volume_ratio
                }
            }
        }

        # Use stream=True to handle chunked response
        response = requests.post(
            self.TTS_BASE_URL,
            headers=headers,
            json=payload,
            timeout=self.timeout,
            stream=True
        )

        if response.status_code != 200:
            error_msg = f"TTS API returned {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f": {json.dumps(error_data, ensure_ascii=False)}"
            except Exception:
                error_msg += f": {response.text[:500]}"
            raise Exception(error_msg)

        # Collect all audio data from streaming response
        audio_bytes = b""

        for line in response.iter_lines():
            if not line:
                continue

            try:
                # Each line is a JSON object
                data = json.loads(line.decode('utf-8'))
                code = data.get("code", -1)
                message = data.get("message", "")

                if code != 0 and code != 20000000:
                    # Error or non-success code
                    self.logger.warning(f"TTS response code {code}: {message}")
                    if code >= 40000000:
                        raise Exception(f"TTS error {code}: {message}")
                    continue

                # Check for audio data
                audio_data = data.get("data")
                if audio_data:
                    # audio_data is base64 encoded
                    try:
                        audio_bytes += base64.b64decode(audio_data)
                    except Exception as e:
                        self.logger.warning(f"Failed to decode audio data: {e}")

                # Check for sentence data (timestamps)
                sentence = data.get("sentence")
                if sentence:
                    self.logger.debug(f"Sentence: {sentence.get('text', '')[:50]}")

                # Session finish
                if code == 20000000:
                    self.logger.debug("TTS session finished")
                    break

            except json.JSONDecodeError:
                # Skip non-JSON lines
                continue
            except Exception as e:
                self.logger.warning(f"Error processing TTS response line: {e}")

        if not audio_bytes:
            raise Exception("No audio data received from TTS API")

        self.logger.debug(f"Received {len(audio_bytes)} bytes of audio data")
        return audio_bytes

    def _save_audio_segment(self, audio_data: bytes, sequence: int) -> Path:
        """Save audio segment to temporary file"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"segment_{sequence:03d}_{timestamp}.mp3"
        filepath = self.output_dir / "segments" / filename

        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(audio_data)

        return filepath

    def get_synthesis_stats(self) -> Dict[str, Any]:
        """Get statistics about Doubao audio synthesis performance"""
        stats = super().get_synthesis_stats()
        stats.update({
            "provider": "doubao",
            "voice_id": self.voice_id,
            "resource_id": self.resource_id,
            "speed_ratio": self.speed_ratio,
            "volume_ratio": self.volume_ratio,
            "auth_mode": self.auth_mode
        })
        return stats

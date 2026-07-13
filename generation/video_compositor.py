"""
Video Compositor Module

Combines silent animations, synchronized audio, and subtitles into final MP4 videos.
Uses FFmpeg for robust video processing and quality optimization.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import ffmpeg

from pydantic import BaseModel, Field


class VideoCompositionResult(BaseModel):
    """Result of video composition operation"""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    input_video_path: Optional[str] = None
    input_audio_path: Optional[str] = None
    input_subtitle_path: Optional[str] = None
    output_duration: Optional[float] = None
    file_size_mb: Optional[float] = None
    resolution: Optional[Tuple[int, int]] = None
    generation_time: Optional[float] = None
    ffmpeg_command: Optional[str] = None


class VideoCompositor:
    """
    Video composition and processing using FFmpeg

    Handles merging of silent animations, audio tracks, and subtitles
    into polished final MP4 videos with optimal quality settings.
    """

    def __init__(
        self,
        output_dir: Path,
        video_codec: str = "libx264",
        video_preset: str = "medium",
        video_crf: int = 23,
        audio_codec: str = "aac",
        audio_bitrate: str = "128k",
        subtitle_burn_in: bool = True,
        subtitle_font_size: int = 24,
        subtitle_font_color: str = "white",
        subtitle_background: bool = True,
        subtitle_background_opacity: float = 0.5,
        subtitle_position: str = "bottom",
        max_retries: int = 3,
        timeout: int = 600
    ):
        """
        Initialize Video Compositor

        Args:
            output_dir: Directory for output videos
            video_codec: Video codec (default: libx264)
            video_preset: Encoding preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
            video_crf: Constant Rate Factor (0-51, lower = higher quality, 23 is default)
            audio_codec: Audio codec (default: aac)
            audio_bitrate: Audio bitrate (default: 128k)
            subtitle_burn_in: Whether to burn subtitles into video (hard subs)
            subtitle_font_size: Font size for subtitles
            subtitle_font_color: Color for subtitle text
            subtitle_background: Whether to add background to subtitles
            subtitle_background_opacity: Opacity of subtitle background (0.0-1.0)
            subtitle_position: Position of subtitles (top, center, bottom)
            max_retries: Maximum retry attempts for failed operations
            timeout: Timeout in seconds for FFmpeg operations
        """
        self.output_dir = Path(output_dir)
        self.video_codec = video_codec
        self.video_preset = video_preset
        self.video_crf = video_crf
        self.audio_codec = audio_codec
        self.audio_bitrate = audio_bitrate
        self.subtitle_burn_in = subtitle_burn_in
        self.subtitle_font_size = subtitle_font_size
        self.subtitle_font_color = subtitle_font_color
        self.subtitle_background = subtitle_background
        self.subtitle_background_opacity = subtitle_background_opacity
        self.subtitle_position = subtitle_position
        self.max_retries = max_retries
        self.timeout = timeout

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = logging.getLogger("VideoCompositor")

        # Validate FFmpeg availability
        self._validate_ffmpeg()

    def _validate_ffmpeg(self):
        """Validate that FFmpeg is available and working"""
        try:
            # Check FFmpeg availability
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError("FFmpeg not found or not working")

            self.logger.info("FFmpeg validation successful")

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"FFmpeg validation failed: {e}")

    def execute(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> VideoCompositionResult:
        """
        Execute video composition

        Args:
            video_path: Path to silent animation video
            audio_path: Path to synchronized audio
            subtitle_path: Optional path to SRT subtitle file
            output_filename: Optional custom output filename

        Returns:
            VideoCompositionResult with output video details
        """
        start_time = datetime.now()

        try:
            self.logger.info(f"Starting video composition")
            self.logger.info(f"  Video: {video_path}")
            self.logger.info(f"  Audio: {audio_path}")
            self.logger.info(f"  Subtitles: {subtitle_path}")

            # Validate inputs
            self._validate_inputs(video_path, audio_path, subtitle_path)

            # Generate output filename if not provided
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"final_video_{timestamp}.mp4"

            # Ensure .mp4 extension
            if not output_filename.endswith('.mp4'):
                output_filename += '.mp4'

            output_path = self.output_dir / output_filename

            # Get video information
            video_info = self._get_video_info(video_path)
            self.logger.info(f"  Input video: {video_info['duration']:.2f}s, {video_info['resolution']}")

            # Get audio information
            audio_info = self._get_audio_info(audio_path)
            self.logger.info(f"  Input audio: {audio_info['duration']:.2f}s")

            # Execute composition with retry logic
            for attempt in range(self.max_retries):
                try:
                    if attempt > 0:
                        self.logger.info(f"Retry attempt {attempt + 1}/{self.max_retries}")

                    success = self._compose_video(
                        video_path, audio_path, subtitle_path, str(output_path)
                    )

                    if success:
                        break

                except Exception as e:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        raise e
            else:
                raise RuntimeError("Video composition failed after all retries")

            # Validate output
            if not output_path.exists():
                raise RuntimeError("Output video file was not created")

            # Get output video information
            output_info = self._get_video_info(str(output_path))
            file_size_mb = output_path.stat().st_size / (1024 * 1024)

            generation_time = (datetime.now() - start_time).total_seconds()

            self.logger.info(f"Video composition completed successfully")
            self.logger.info(f"  Output: {output_path}")
            self.logger.info(f"  Duration: {output_info['duration']:.2f}s")
            self.logger.info(f"  Resolution: {output_info['resolution']}")
            self.logger.info(f"  File size: {file_size_mb:.2f}MB")
            self.logger.info(f"  Generation time: {generation_time:.2f}s")

            return VideoCompositionResult(
                success=True,
                output_path=str(output_path),
                input_video_path=video_path,
                input_audio_path=audio_path,
                input_subtitle_path=subtitle_path,
                output_duration=output_info['duration'],
                file_size_mb=file_size_mb,
                resolution=output_info['resolution'],
                generation_time=generation_time
            )

        except Exception as e:
            generation_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Video composition failed: {e}"
            self.logger.error(error_msg)

            return VideoCompositionResult(
                success=False,
                error_message=error_msg,
                input_video_path=video_path,
                input_audio_path=audio_path,
                input_subtitle_path=subtitle_path,
                generation_time=generation_time
            )

    def _validate_inputs(self, video_path: str, audio_path: str, subtitle_path: Optional[str] = None):
        """Validate input files"""
        # Validate video file
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not video_file.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
            raise ValueError(f"Invalid video format: {video_file.suffix}")

        # Validate audio file
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if not audio_file.suffix.lower() in ['.mp3', '.wav', '.aac', '.m4a']:
            raise ValueError(f"Invalid audio format: {audio_file.suffix}")

        # Validate subtitle file if provided
        if subtitle_path:
            subtitle_file = Path(subtitle_path)
            if not subtitle_file.exists():
                raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")
            if not subtitle_file.suffix.lower() in ['.srt', '.ass', '.vtt']:
                raise ValueError(f"Invalid subtitle format: {subtitle_file.suffix}")

        self.logger.info("All input files validated successfully")

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video information using FFprobe"""
        try:
            probe = ffmpeg.probe(video_path)

            # Video stream info
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found")

            width = int(video_stream['width'])
            height = int(video_stream['height'])

            # Duration
            duration = float(probe['format']['duration'])

            return {
                'duration': duration,
                'resolution': (width, height),
                'fps': eval(video_stream.get('r_frame_rate', '25/1'))
            }

        except Exception as e:
            raise RuntimeError(f"Failed to get video info: {e}")

    def _get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """Get audio information using FFprobe"""
        try:
            probe = ffmpeg.probe(audio_path)

            # Duration
            duration = float(probe['format']['duration'])

            return {
                'duration': duration
            }

        except Exception as e:
            raise RuntimeError(f"Failed to get audio info: {e}")

    def _compose_video(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: Optional[str],
        output_path: str
    ) -> bool:
        """
        Compose final video using FFmpeg

        Args:
            video_path: Input video file
            audio_path: Input audio file
            subtitle_path: Optional input subtitle file
            output_path: Output video file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build FFmpeg command
            input_video = ffmpeg.input(video_path)
            input_audio = ffmpeg.input(audio_path)

            # Create subtitle filter if burning in and subtitle_path provided
            if self.subtitle_burn_in and subtitle_path:
                subtitle_filter = self._create_subtitle_filter(subtitle_path)
                video = input_video.filter('subtitles', subtitle_path)
            else:
                video = input_video

            # Build output
            output = ffmpeg.output(
                video,
                input_audio,
                output_path,
                vcodec=self.video_codec,
                preset=self.video_preset,
                crf=self.video_crf,
                acodec=self.audio_codec,
                audio_bitrate=self.audio_bitrate,
                movflags='+faststart',  # Optimize for web playback
                pix_fmt='yuv420p'  # Ensure compatibility
            )

            # Run FFmpeg
            cmd = ffmpeg.compile(output)
            self.logger.info(f"FFmpeg command: {' '.join(cmd)}")

            # Execute with timeout
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            try:
                stdout, stderr = process.communicate(timeout=self.timeout)

                if process.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed with return code {process.returncode}: {stderr}")

                self.logger.info("FFmpeg processing completed successfully")
                return True

            except subprocess.TimeoutExpired:
                process.kill()
                raise RuntimeError(f"FFmpeg processing timed out after {self.timeout}s")

        except Exception as e:
            self.logger.error(f"FFmpeg processing failed: {e}")
            raise

    def _create_subtitle_filter(self, subtitle_path: str) -> str:
        """Create subtitle filter string for FFmpeg"""
        # Basic subtitle filter - can be enhanced for more styling
        return subtitle_path

    def get_supported_formats(self) -> List[str]:
        """Get list of supported input/output formats"""
        return [
            "mp4", "avi", "mov", "mkv", "webm"  # Video formats
        ]

    def estimate_output_size(
        self,
        video_duration: float,
        video_resolution: Tuple[int, int],
        audio_bitrate: str = "128k"
    ) -> float:
        """
        Estimate output file size in MB

        Args:
            video_duration: Duration in seconds
            video_resolution: Resolution as (width, height)
            audio_bitrate: Audio bitrate

        Returns:
            Estimated file size in MB
        """
        # Rough estimation based on settings
        width, height = video_resolution
        pixels = width * height

        # Video bitrate estimation (simplified)
        if pixels <= 640 * 480:  # SD
            video_bitrate_kbps = 500
        elif pixels <= 1280 * 720:  # HD
            video_bitrate_kbps = 2000
        elif pixels <= 1920 * 1080:  # Full HD
            video_bitrate_kbps = 5000
        else:  # 4K and above
            video_bitrate_kbps = 15000

        # Adjust for CRF
        video_bitrate_kbps = video_bitrate_kbps * (1 - (self.video_crf - 23) / 51)

        # Audio bitrate
        audio_bitrate_kbps = int(audio_bitrate.replace('k', ''))

        # Total bitrate
        total_bitrate_kbps = video_bitrate_kbps + audio_bitrate_kbps

        # Convert to file size (MB)
        file_size_mb = (total_bitrate_kbps * video_duration) / (8 * 1024)

        return max(file_size_mb, 0.1)  # Minimum 0.1MB
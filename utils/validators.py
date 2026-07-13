"""
Validation utilities for Phase 3-4 components
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class PipelineValidator:
    """Utility class for validating pipeline inputs and outputs"""

    @staticmethod
    def validate_concept_input(concept: str) -> str:
        """Validate user concept input"""
        if not concept or not concept.strip():
            raise ValidationError("Concept cannot be empty")

        concept = concept.strip()

        if len(concept) > 500:
            raise ValidationError("Concept description too long (max 500 characters)")

        # Check for potentially harmful content
        if re.search(r'[<>]', concept):
            raise ValidationError("Concept contains invalid characters")

        return concept

    @staticmethod
    def validate_video_file(video_path: str) -> Path:
        """Validate video file exists and is accessible"""
        video_file = Path(video_path)

        if not video_file.exists():
            raise ValidationError(f"Video file not found: {video_path}")

        if not video_file.is_file():
            raise ValidationError(f"Path is not a file: {video_path}")

        # Check file extension
        valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        if video_file.suffix.lower() not in valid_extensions:
            raise ValidationError(f"Invalid video file extension: {video_file.suffix}")

        # Check file size (should not be empty)
        if video_file.stat().st_size == 0:
            raise ValidationError(f"Video file is empty: {video_path}")

        return video_file

    @staticmethod
    def validate_srt_content(srt_content: str) -> List[Dict[str, Any]]:
        """Parse and validate SRT content"""
        if not srt_content or not srt_content.strip():
            raise ValidationError("SRT content is empty")

        subtitles = []
        lines = srt_content.strip().split('\n')

        i = 0
        sequence_numbers = set()

        while i < len(lines):
            try:
                # Skip empty lines
                if not lines[i].strip():
                    i += 1
                    continue

                # Parse sequence number
                sequence_line = lines[i].strip()
                if not sequence_line.isdigit():
                    raise ValidationError(f"Invalid sequence number at line {i+1}: {sequence_line}")

                sequence = int(sequence_line)

                # Check for duplicate sequence numbers
                if sequence in sequence_numbers:
                    raise ValidationError(f"Duplicate sequence number: {sequence}")
                sequence_numbers.add(sequence)

                i += 1
                if i >= len(lines):
                    break

                # Parse timestamp line
                timestamp_line = lines[i].strip()
                if '-->' not in timestamp_line:
                    raise ValidationError(f"Invalid timestamp format at line {i+1}: {timestamp_line}")

                try:
                    start_time_str, end_time_str = [t.strip() for t in timestamp_line.split('-->')]

                    # Validate and fix timestamp format
                    start_time_str = PipelineValidator._validate_timestamp(start_time_str)
                    end_time_str = PipelineValidator._validate_timestamp(end_time_str)

                    # Validate the normalized timestamps
                    PipelineValidator._validate_parsed_timestamp(start_time_str)
                    PipelineValidator._validate_parsed_timestamp(end_time_str)

                    # Convert to seconds for duration check
                    start_seconds = PipelineValidator._timestamp_to_seconds(start_time_str)
                    end_seconds = PipelineValidator._timestamp_to_seconds(end_time_str)

                    if end_seconds <= start_seconds:
                        raise ValidationError(f"Invalid time range: {start_time_str} --> {end_time_str}")

                except Exception as e:
                    raise ValidationError(f"Timestamp validation failed at line {i+1}: {e}")

                i += 1

                # Parse text lines
                if i >= len(lines):
                    raise ValidationError("Missing subtitle text")

                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                    i += 1

                if not text_lines:
                    raise ValidationError(f"Empty subtitle text for sequence {sequence}")

                text = ' '.join(text_lines)

                # Validate text content
                if len(text) > 200:  # Reasonable limit for subtitle length
                    raise ValidationError(f"Subtitle text too long for sequence {sequence}")

                subtitles.append({
                    'sequence': sequence,
                    'start_time': start_time_str,  # Fixed format
                    'end_time': end_time_str,      # Fixed format
                    'text': text,
                    'duration': end_seconds - start_seconds
                })

            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(f"Error parsing subtitle at line {i+1}: {e}")

        if not subtitles:
            raise ValidationError("No valid subtitles found in SRT content")

        # Check for chronological order
        for i in range(1, len(subtitles)):
            prev_end = PipelineValidator._timestamp_to_seconds(subtitles[i-1]['end_time'])
            curr_start = PipelineValidator._timestamp_to_seconds(subtitles[i]['start_time'])

            if curr_start < prev_end:
                raise ValidationError(f"Subtitles not in chronological order: sequence {subtitles[i]['sequence']}")

        return subtitles

    @staticmethod
    def _validate_timestamp(timestamp: str) -> str:
        """Validate and fix timestamp format"""

        # Common patterns and their fixes
        timestamp = timestamp.strip()

        # Pattern 1: Missing comma - convert to comma (e.g., 00:04:500 -> 00:00:04,500)
        if re.match(r'^\d{2}:\d{3}$', timestamp):
            minutes = int(timestamp[0:2])
            seconds_millis = timestamp[3:]
            if len(seconds_millis) <= 3:
                seconds = int(seconds_millis)
                milliseconds = 0
            else:
                seconds = int(seconds_millis[:-3])
                milliseconds = int(seconds_millis[-3:])
            return f"00:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        # Pattern 2: Format like 00:014:000 -> 00:01:04,000
        if re.match(r'^\d{2}:\d{3}:\d{3}$', timestamp):
            parts = timestamp.split(':')
            hours = int(parts[0])
            minutes_seconds = parts[1]
            milliseconds = parts[2]

            if len(minutes_seconds) == 3:
                minutes = int(minutes_seconds[0])
                seconds = int(minutes_seconds[1:])
            else:
                minutes = int(minutes_seconds[:-2])
                seconds = int(minutes_seconds[-2:])

            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds}"

        # Pattern 3: Format like 00:04:800 -> 00:00:04,800
        if re.match(r'^\d{2}:\d{2}:\d{3}$', timestamp):
            parts = timestamp.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_millis = parts[2]

            if len(seconds_millis) <= 3:
                seconds = int(seconds_millis)
                milliseconds = 0
            else:
                seconds = int(seconds_millis[:-3])
                milliseconds = int(seconds_millis[-3:])

            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        # Pattern 4: Format like 00:04:800 -> 00:00:04,800 (already has comma)
        if re.match(r'^\d{2}:\d{2}:\d{3},\d{3}$', timestamp):
            # This is already correct format
            return timestamp

        # Pattern 5: Try to parse standard format with potential issues
        if ':' in timestamp:
            parts = timestamp.replace(',', ':').split(':')

            # Handle different number of parts
            if len(parts) == 2:  # MM:SS or MM:SS,mss
                minutes = int(parts[0])
                seconds_millis = parts[1]
                if ',' in seconds_millis:
                    seconds, milliseconds = seconds_millis.split(',')
                else:
                    if len(seconds_millis) <= 3:
                        seconds = int(seconds_millis)
                        milliseconds = 0
                    else:
                        seconds = int(seconds_millis[:-3])
                        milliseconds = int(seconds_millis[-3:])
                return f"00:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

            elif len(parts) == 3:  # HH:MM:SS or variations
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds_millis = parts[2].replace(',', '')

                if len(seconds_millis) <= 3:
                    seconds = int(seconds_millis)
                    milliseconds = 0
                else:
                    seconds = int(seconds_millis[:-3])
                    milliseconds = int(seconds_millis[-3:])

                return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

            elif len(parts) == 4:  # HH:MM:SS,mss
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                milliseconds = int(parts[3])

                return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        # If we can't parse it, raise error
        raise ValidationError(f"Cannot parse timestamp format: {timestamp}")

    @staticmethod
    def _validate_parsed_timestamp(timestamp: str) -> None:
        """Validate a normalized timestamp format"""
        # Expected format: HH:MM:SS,mmm
        pattern = r'^\d{2}:\d{2}:\d{2},\d{3}$'
        if not re.match(pattern, timestamp):
            raise ValidationError(f"Invalid normalized timestamp format: {timestamp}")

        # Check for valid time values
        time_part = timestamp.replace(',', ':')
        parts = time_part.split(':')

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])

        if hours > 23 or minutes > 59 or seconds > 59 or milliseconds > 999:
            raise ValidationError(f"Invalid time values in timestamp: {timestamp}")

    @staticmethod
    def _timestamp_to_seconds(timestamp: str) -> float:
        """Convert timestamp to seconds"""
        timestamp = timestamp.replace(',', ':')
        parts = timestamp.split(':')

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        milliseconds = int(parts[3])

        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

    @staticmethod
    def validate_audio_file(audio_path: str) -> Path:
        """Validate audio file exists and is accessible"""
        audio_file = Path(audio_path)

        if not audio_file.exists():
            raise ValidationError(f"Audio file not found: {audio_path}")

        if not audio_file.is_file():
            raise ValidationError(f"Path is not a file: {audio_path}")

        # Check file extension
        valid_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg'}
        if audio_file.suffix.lower() not in valid_extensions:
            raise ValidationError(f"Invalid audio file extension: {audio_file.suffix}")

        # Check file size
        if audio_file.stat().st_size == 0:
            raise ValidationError(f"Audio file is empty: {audio_path}")

        return audio_file

    @staticmethod
    def validate_api_key(api_key: str, service_name: str) -> str:
        """Validate API key format"""
        if not api_key or not api_key.strip():
            raise ValidationError(f"{service_name} API key cannot be empty")

        api_key = api_key.strip()

        # Basic format validation
        if len(api_key) < 10:
            raise ValidationError(f"{service_name} API key appears to be invalid (too short)")

        return api_key

    @staticmethod
    def validate_output_directory(output_dir: Path) -> Path:
        """Validate output directory is writable"""
        if output_dir.exists() and not output_dir.is_dir():
            raise ValidationError(f"Output path exists but is not a directory: {output_dir}")

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise ValidationError(f"No permission to create output directory: {output_dir}")

        # Test write permissions
        test_file = output_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            raise ValidationError(f"No write permission for output directory: {output_dir}")

        return output_dir


def setup_phase3_logging() -> logging.Logger:
    """Setup logging for Phase 3 components"""
    logger = logging.getLogger("Phase3")

    if not logger.handlers:
        # Create handler for file logging
        file_handler = logging.FileHandler("output/phase3.log")
        file_handler.setLevel(logging.INFO)

        # Create handler for console logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)

    return logger


def setup_phase4_logging() -> logging.Logger:
    """Setup logging for Phase 4 components"""
    logger = logging.getLogger("Phase4")

    if not logger.handlers:
        # Create handler for file logging
        file_handler = logging.FileHandler("output/phase4.log")
        file_handler.setLevel(logging.INFO)

        # Create handler for console logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)

    return logger


# Add FFmpeg validation to PipelineValidator
@staticmethod
def validate_ffmpeg():
    """Validate that FFmpeg is available and working"""
    import subprocess

    try:
        # Check FFmpeg availability
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise ValidationError("FFmpeg not found or not working")

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise ValidationError(f"FFmpeg validation failed: {e}")


# Add the static method to the class
PipelineValidator.validate_ffmpeg = validate_ffmpeg
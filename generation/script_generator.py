import logging
import time
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import requests

from pydantic import BaseModel, Field


class SRTSubtitle(BaseModel):
    sequence: int
    start_time: str
    end_time: str
    text: str


class ScriptResult(BaseModel):
    success: bool
    script_path: Optional[str] = None
    srt_content: Optional[str] = None
    subtitles: List[SRTSubtitle] = Field(default_factory=list)
    total_duration: Optional[float] = None
    error_message: Optional[str] = None
    generation_time: Optional[float] = None
    video_duration: Optional[float] = None
    model_used: str = "unknown"


class ScriptGenerator:
    """
    Script Generator: Analyzes silent animations and generates timestamped narration scripts
    using Doubao (Volcano Engine Ark) video understanding API.
    """

    def __init__(
        self,
        api_key: str,
        output_dir: Path,
        model: str = "doubao-seed-2-1-pro-260628",
        temperature: float = 0.5,
        max_retries: int = 3,
        timeout: int = 300,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)

    SCRIPT_GENERATION_PROMPT = """
You are an Educational Script Generator for STEM animations.

**TASK**: Watch the provided silent animation video and create a synchronized narration script in SRT (SubRip) format.

**TARGET LANGUAGE**: {target_language}

**VIDEO DURATION**: {video_duration_minutes:.1f}:{video_duration_seconds:05.2f} (minutes:seconds)

---

## PRIMARY OBJECTIVE
Write a **succinct, student-friendly narration** that explains the concept clearly and naturally. Speak to **why** things happen, **what to notice**, and the **reasoning that connects steps**, so the narration feels complete, not merely descriptive.

---

## FOCUS & BREVITY RULES (STRICT)
- **Only narrate when it adds understanding.** If a visual is self-explanatory or decorative, **omit** it.
- **One idea per subtitle**, **one sentence** per subtitle.
- **Word cap:** Prefer **10–14 words**, never exceed **18 words** in any subtitle.
- **Define a term once**, then use it consistently without re-defining.
- **Prefer "why/what to notice"** over "what moves where."
- **Use causal links** ("because," "so," "therefore," "which means") to bridge steps.
- **Name roles, not looks.** Use function-driven labels ("velocity vector," "spring constant k"), not colors/shapes—**unless color encodes meaning**, then state the meaning.
- **Avoid**: listing colors/shapes, camera moves, minor transitions, or stating the obvious.

---

## WORKFLOW BEFORE WRITING
1) **Skim once** to identify the learning objective and main phases.
2) **List key beats** where understanding could fail (definition, setup, transformation, result, takeaway).
3) **Write to those beats only**, using the brevity rules and causal connectors.
4) **Prune** any line that merely narrates motion without adding meaning.
5) **Completeness check**: Do you cover objective → setup/assumptions → core relation → transformation → result → concise takeaway?

---

## WHAT TO SAY (CONTENT PRIORITIES)
- **Introduction**: Start with a single, clear sentence introducing the concept and goal.
- **Definitions & symbols**: Introduce each new symbol/term once; explain its role or unit.
- **Assumptions**: State critical conditions briefly (e.g., "no friction," "mass is constant").
- **Relations**: Express the governing idea (e.g., "force causes acceleration," "slope is rise over run").
- **Transformations**: When the visual changes, say **why** it changes and **what that implies**.
- **Numbers & expressions**: Explain what a number/expression represents; avoid reading it verbatim unless essential.
- **Misconceptions**: Anticipate a likely confusion and clarify it in one short line, if timing allows.
- **Final takeaway**: End with a compact conclusion that reinforces the core idea.

---

## SRT FORMAT (MANDATORY)
- **TIMESTAMP FORMAT**: exactly `HH:MM:SS,mmm` with a **comma** before milliseconds.
- **Each subtitle** is a complete sentence, 1 line, **3–6 seconds** long.
- **Pause** between subtitles: **0,5–1,0 seconds**.
- **Sequence numbers** start at 1 and increment by 1.

**CRITICAL: ALWAYS USE COMMA (,) NOT PERIOD (.) BETWEEN SECONDS AND MILLISECONDS**
- ✅ 00:00:03,500
- ❌ 00:00:03.500

**COMMON MISTAKES TO AVOID**
- Missing leading zeros (✅ 00:00:03,500)
- Not 3 digits of milliseconds (✅ 00:00:03,500)
- Durations shorter than 3 seconds
- Describing everything on screen
- Multiple sentences in one subtitle

---

## TIMING GUIDELINES
- Begin narration **slightly early**: start 0,5–1,0 s before the first key visual.
- **First subtitle must be an introduction sentence to the concept**, beginning at **00:00:00,000**.
- Keep each subtitle **3–6 s**; end slightly **before** a visual transition.
- Maintain a natural rhythm; use simple syntax and active voice.
- You always have to start with something from **00:00:00,000**.

---

## STYLE
- **Clear, conversational, {target_language}**, present tense, active voice.
- Prefer concrete verbs and simple syntax.
- Use gentle signposts sparingly ("First…", "Now…", "So…").
- When numbers/symbols appear, explain **their role or meaning**, not their appearance.

---

## OUTPUT REQUIREMENTS
- Output **ONLY** the SRT content wrapped in `<srt>` tags.
- No commentary outside the `<srt>` block.

---

## MINI EXAMPLE (brevity-focused)
<srt>
1
00:00:00,000 --> 00:00:04,000
We're exploring how slope measures a line's steepness.

2
00:00:04,800 --> 00:00:09,200
Slope equals rise over run: vertical change divided by horizontal change.

3
00:00:09,900 --> 00:00:13,500
Notice the rise marks how far the line increases vertically.

4
00:00:14,200 --> 00:00:18,200
The run shows the horizontal distance you move to compare points.

5
00:00:18,900 --> 00:00:23,000
Because the ratio stays constant, slope is identical anywhere on the line.
</srt>
"""

    def execute(self, video_path: str, target_language: str = "English") -> ScriptResult:
        start_time = time.time()
        self.logger.info(f"Starting script generation for: {video_path}")
        self.logger.info(f"Model: {self.model}")

        try:
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            video_duration = self._get_video_duration(video_file)
            self.logger.info(f"Video duration: {video_duration:.2f} seconds")

            srt_content = self._generate_script_with_doubao(video_file, target_language, video_duration)

            if srt_content:
                subtitles = self._parse_srt_content(srt_content)
                script_duration = self._calculate_script_duration(subtitles)
                script_path = self._save_script(srt_content, video_file.stem)

                generation_time = time.time() - start_time
                self.logger.info(f"Script generation completed in {generation_time:.2f}s")
                self.logger.info(f"Generated {len(subtitles)} subtitles")
                self.logger.info(f"Script duration: {script_duration:.2f}s")

                return ScriptResult(
                    success=True,
                    script_path=str(script_path),
                    srt_content=srt_content,
                    subtitles=subtitles,
                    total_duration=script_duration,
                    generation_time=generation_time,
                    video_duration=video_duration,
                    model_used=self.model
                )
            else:
                raise ValueError("Failed to generate script content")

        except Exception as e:
            self.logger.error(f"Script generation failed: {e}")
            import traceback
            traceback.print_exc()
            return ScriptResult(
                success=False,
                error_message=str(e),
                generation_time=time.time() - start_time,
                model_used=self.model
            )

    def _generate_script_with_doubao(self, video_file: Path, target_language: str, video_duration: float) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Uploading video to Doubao Files API (attempt {attempt + 1})")

                file_id = self._doubao_upload_file(video_file)
                if not file_id:
                    raise ValueError("Failed to upload video file")

                self.logger.info("Waiting for file processing...")
                self._doubao_wait_for_file(file_id)

                self.logger.info(f"Generating script with {self.model} in {target_language}")
                video_duration_minutes = int(video_duration // 60)
                video_duration_seconds = video_duration % 60
                prompt = self.SCRIPT_GENERATION_PROMPT.format(
                    target_language=target_language,
                    video_duration=video_duration,
                    video_duration_minutes=video_duration_minutes,
                    video_duration_seconds=video_duration_seconds
                )

                script_content = self._doubao_video_chat(file_id, prompt)

                if not script_content:
                    self.logger.warning("Chat API failed, trying Responses API...")
                    script_content = self._doubao_video_understanding(file_id, prompt)

                if script_content:
                    self.logger.info("Received script content from Doubao")
                    srt_content = self._extract_srt_from_response(script_content)

                    if srt_content:
                        return srt_content
                    else:
                        self.logger.warning(f"No SRT content found in response (attempt {attempt + 1})")
                        if attempt < self.max_retries - 1:
                            continue
                        else:
                            self.logger.warning("Trying to use raw response as SRT")
                            srt_content = self._extract_srt_from_response(script_content)
                            if srt_content:
                                return srt_content
                            raise ValueError("Could not extract SRT content from Doubao response")

            except Exception as e:
                self.logger.warning(f"Doubao API call failed (attempt {attempt + 1}): {e}")
                import traceback
                traceback.print_exc()
                if attempt < self.max_retries - 1:
                    # Check if rate limited (429)
                    is_rate_limit = False
                    if hasattr(e, 'response') and e.response is not None:
                        if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                            is_rate_limit = True
                    
                    if is_rate_limit:
                        wait_time = 30 * (attempt + 1)
                        self.logger.warning(f"Rate limited (429). Waiting {wait_time}s...")
                    else:
                        wait_time = min(2**attempt * 5, 60)
                    time.sleep(wait_time)
                else:
                    raise

        return None

    def _doubao_upload_file(self, video_file: Path) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        suffix = video_file.suffix.lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
        }
        mime_type = mime_types.get(suffix, 'video/mp4')

        with open(video_file, 'rb') as f:
            files = {
                'file': (video_file.name, f, mime_type)
            }
            data = {
                'purpose': 'user_data',
                'preprocess_configs': json.dumps({
                    "video": {
                        "fps": 0.5
                    }
                })
            }

            response = requests.post(
                f"{self.base_url}/files",
                headers=headers,
                files=files,
                data=data,
                timeout=self.timeout
            )

        if response.status_code != 200:
            self.logger.error(f"File upload failed: {response.status_code}")
            self.logger.error(f"Response: {response.text}")
            return None

        result = response.json()
        file_id = result.get('id')
        self.logger.info(f"File uploaded: {file_id}, status: {result.get('status', 'N/A')}")
        return file_id

    def _doubao_wait_for_file(self, file_id: str, max_wait: int = 300) -> bool:
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        waited = 0
        while waited < max_wait:
            time.sleep(5)
            waited += 5

            try:
                response = requests.get(
                    f"{self.base_url}/files/{file_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code == 200:
                    info = response.json()
                    status = info.get('status', 'N/A')
                    self.logger.debug(f"Wait {waited}s, file status: {status}")

                    if status in ('active', 'processed', 'succeeded'):
                        self.logger.info(f"File ready after {waited}s")
                        return True
                    elif status in ('failed', 'error'):
                        self.logger.error(f"File processing failed: {json.dumps(info, ensure_ascii=False)}")
                        return False
                else:
                    self.logger.warning(f"Get file info failed: {response.status_code}")
            except Exception as e:
                self.logger.warning(f"Error checking file status: {e}")

        self.logger.error(f"File processing timed out after {max_wait}s")
        return False

    def _doubao_video_understanding(self, file_id: str, prompt: str) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_video",
                            "file_id": file_id
                        },
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_output_tokens": 16384
        }

        try:
            response = requests.post(
                f"{self.base_url}/responses",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            self.logger.debug(f"Responses API status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                output = data.get('output', [])
                if output:
                    content_parts = []
                    for item in output:
                        if item.get('type') == 'message':
                            for content in item.get('content', []):
                                if content.get('type') == 'output_text':
                                    content_parts.append(content.get('text', ''))
                    if content_parts:
                        return '\n'.join(content_parts)

                if 'choices' in data:
                    return data['choices'][0]['message']['content']

                self.logger.warning(f"Could not extract content from response: {json.dumps(data, ensure_ascii=False)[:1000]}")
                return None

            else:
                self.logger.warning(f"Responses API failed: {response.status_code}")
                self.logger.warning(f"Response: {response.text[:1000]}")
                return self._doubao_video_chat(file_id, prompt)

        except Exception as e:
            self.logger.warning(f"Responses API error: {e}")
            return self._doubao_video_chat(file_id, prompt)

    def _doubao_video_chat(self, file_id: str, prompt: str) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {
                                "file_id": file_id
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 16384,
            "temperature": self.temperature
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                self.logger.error(f"Chat API failed: {response.status_code}")
                self.logger.error(f"Response: {response.text[:1000]}")
                return None

        except Exception as e:
            self.logger.error(f"Chat API error: {e}")
            return None

    def _extract_srt_from_response(self, response: str) -> Optional[str]:
        srt_pattern = r'<srt>(.*?)</srt>'
        matches = re.findall(srt_pattern, response, re.DOTALL | re.IGNORECASE)

        if matches:
            srt_content = matches[0].strip()
            self.logger.info("Extracted SRT content from <srt> tags")
            return srt_content

        srt_lines = []
        lines = response.strip().split('\n')

        current_subtitle = []
        for line in lines:
            line = line.strip()
            if not line:
                if current_subtitle:
                    srt_lines.extend(current_subtitle)
                    srt_lines.append("")
                    current_subtitle = []
                continue

            if (line.isdigit() or
                '-->' in line or
                any(char in line for char in '.!?')):
                current_subtitle.append(line)

        if current_subtitle:
            srt_lines.extend(current_subtitle)

        if srt_lines:
            srt_content = '\n'.join(srt_lines).strip()
            self.logger.info("Extracted SRT content without tags")
            return srt_content

        self.logger.warning("No SRT content found in response")
        return None

    def _parse_srt_content(self, srt_content: str) -> List[SRTSubtitle]:
        subtitles = []
        lines = srt_content.strip().split('\n')

        i = 0
        while i < len(lines):
            try:
                if not lines[i].strip():
                    i += 1
                    continue

                sequence_line = lines[i].strip()

                if '-->' in sequence_line:
                    parts = sequence_line.split('.')
                    if len(parts) >= 2 and parts[0].strip().isdigit():
                        sequence = int(parts[0].strip())
                        timestamp_line = '.'.join(parts[1:]).strip()

                        try:
                            start_time, end_time = [t.strip() for t in timestamp_line.split('-->')]
                        except ValueError:
                            self.logger.warning(f"Invalid timestamp format: {timestamp_line}")
                            i += 1
                            continue

                        i += 1

                        text_lines = []
                        while i < len(lines) and lines[i].strip() and not lines[i].strip().split('.')[0].isdigit() and '-->' not in lines[i]:
                            text_lines.append(lines[i].strip())
                            i += 1

                        if text_lines:
                            text = ' '.join(text_lines)
                            subtitle = SRTSubtitle(
                                sequence=sequence,
                                start_time=start_time,
                                end_time=end_time,
                                text=text
                            )
                            subtitles.append(subtitle)
                        continue

                if not sequence_line.isdigit():
                    self.logger.warning(f"Expected sequence number, got: {sequence_line}")
                    i += 1
                    continue

                sequence = int(sequence_line)
                i += 1

                if i >= len(lines):
                    break

                timestamp_line = lines[i].strip()
                if '-->' not in timestamp_line:
                    self.logger.warning(f"Expected timestamp line, got: {timestamp_line}")
                    i += 1
                    continue

                try:
                    start_time, end_time = [t.strip() for t in timestamp_line.split('-->')]
                except ValueError:
                    self.logger.warning(f"Invalid timestamp format: {timestamp_line}")
                    i += 1
                    continue

                i += 1

                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                    i += 1

                if text_lines:
                    text = ' '.join(text_lines)

                    subtitle = SRTSubtitle(
                        sequence=sequence,
                        start_time=start_time,
                        end_time=end_time,
                        text=text
                    )
                    subtitles.append(subtitle)

            except Exception as e:
                self.logger.warning(f"Error parsing subtitle at line {i}: {e}")
                i += 1

        self.logger.info(f"Parsed {len(subtitles)} subtitles from SRT content")
        return subtitles

    def _normalize_timestamp(self, timestamp: str) -> str:
        timestamp = timestamp.strip()
        timestamp = timestamp.replace('.', ',').replace(':', ',')
        parts = timestamp.split(',')

        if len(parts) == 3:
            minutes, seconds, milliseconds = parts
            hours = "00"
        elif len(parts) == 4:
            hours, minutes, seconds, milliseconds = parts
        else:
            raise ValueError(f"Cannot parse timestamp: {timestamp}")

        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)

        if minutes >= 60:
            hours += minutes // 60
            minutes = minutes % 60

        if seconds >= 60:
            minutes += seconds // 60
            seconds = seconds % 60

        if milliseconds >= 1000:
            seconds += milliseconds // 1000
            milliseconds = milliseconds % 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _calculate_script_duration(self, subtitles: List[SRTSubtitle]) -> float:
        if not subtitles:
            return 0.0

        try:
            last_subtitle = max(subtitles, key=lambda s: s.sequence)
            end_time_str = self._normalize_timestamp(last_subtitle.end_time)

            time_parts = end_time_str.replace(',', ':').split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            seconds = int(time_parts[2])
            milliseconds = int(time_parts[3]) if len(time_parts) > 3 else 0

            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
            return total_seconds

        except Exception as e:
            self.logger.warning(f"Error calculating script duration: {e}")
            return 0.0

    def _save_script(self, srt_content: str, video_stem: str) -> Path:
        normalized_content = self._normalize_srt_timestamps(srt_content)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{video_stem}_script_{timestamp}.srt"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(normalized_content)

        self.logger.info(f"Script saved to: {filepath}")
        return filepath

    def _normalize_srt_timestamps(self, srt_content: str) -> str:
        lines = srt_content.split('\n')
        normalized_lines = []

        for line in lines:
            if '-->' in line:
                try:
                    parts = line.split('-->')
                    if len(parts) == 2:
                        start = self._normalize_timestamp(parts[0])
                        end = self._normalize_timestamp(parts[1])
                        normalized_lines.append(f"{start} --> {end}")
                    else:
                        normalized_lines.append(line)
                except Exception as e:
                    self.logger.warning(f"Could not normalize timestamp line: {line} - {e}")
                    normalized_lines.append(line)
            else:
                normalized_lines.append(line)

        return '\n'.join(normalized_lines)

    def _get_video_duration(self, video_file: Path) -> float:
        try:
            import subprocess

            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "default=nokey=1:noprint_wrappers=1",
                "-show_entries", "format=duration",
                str(video_file)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                duration_str = result.stdout.strip()
                return float(duration_str)
            else:
                self.logger.warning(f"ffprobe failed: {result.stderr}")
                return 120.0

        except Exception as e:
            self.logger.warning(f"Could not get video duration: {e}")
            return 120.0

    def get_generation_stats(self) -> Dict[str, Any]:
        return {
            "model_used": self.model,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "output_dir": str(self.output_dir)
        }

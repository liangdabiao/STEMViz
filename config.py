import os
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from pathlib import Path
from typing import Optional, Any


class Settings(BaseSettings):
    # Doubao (Volcano Engine Ark) Configuration
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_tts_api_key: str = ""
    doubao_tts_resource_id: str = "seed-tts-1.0"

    # Doubao TTS old console auth (APP ID + Access Token) - optional
    doubao_tts_app_id: str = ""
    doubao_tts_access_key: str = ""
    doubao_tts_secret_key: str = ""
    doubao_tts_auth_mode: str = "auto"  # "auto", "new", "old"

    # Model Selection
    reasoning_model: str = "doubao-seed-2-1-pro-260628"
    multimodal_model: str = "doubao-seed-2-1-pro-260628"
    code_gen_model: str = "doubao-seed-2-1-turbo-260628"

    # Doubao TTS Settings
    doubao_tts_voice_id: str = "zh_female_shuangkuaisisi_moon_bigtts"
    doubao_tts_speed_ratio: float = 0.0
    doubao_tts_volume_ratio: float = 0.0

    # Common TTS Settings
    tts_max_retries: int = 3
    tts_timeout: int = 120  # seconds

    # Paths
    output_dir: Path = Path("output")

    @property
    def scenes_dir(self) -> Path:
        return self.output_dir / "scenes"

    @property
    def animations_dir(self) -> Path:
        return self.output_dir / "animations"

    @property
    def audio_dir(self) -> Path:
        return self.output_dir / "audio"

    @property
    def scripts_dir(self) -> Path:
        return self.output_dir / "scripts"

    @property
    def final_dir(self) -> Path:
        return self.output_dir / "final"

    @property
    def analyses_dir(self) -> Path:
        return self.output_dir / "analyses"

    @property
    def rendering_dir(self) -> Path:
        return self.output_dir / "rendering"

    @property
    def generation_dir(self) -> Path:
        return self.output_dir / "generation"

    # Manim Settings
    manim_quality: str = "p"
    manim_background_color: str = "#0f0f0f"
    manim_frame_rate: int = 60
    manim_render_timeout: int = 300
    manim_max_retries: int = 3
    manim_max_scene_duration: float = 30.0
    manim_total_video_duration_target: float = 120.0

    # Reasoning settings
    interpreter_reasoning_tokens: Optional[int] = 2048
    animation_reasoning_tokens: Optional[int] = None
    interpreter_reasoning_effort: Optional[str] = "low"
    animation_reasoning_effort: Optional[str] = None

    # Animation generation settings
    animation_temperature: float = 0.5
    animation_max_retries_per_scene: int = 3
    animation_enable_simplification: bool = True
    animation_code_gen_concurrency: int = 1

    # Script Generation Settings
    script_generation_temperature: float = 0.5
    script_generation_max_retries: int = 3
    script_generation_timeout: int = 300

    # Video Settings
    video_codec: str = "libx264"
    video_preset: str = "medium"
    video_crf: int = 23
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"

    # Subtitle Settings
    subtitle_burn_in: bool = True
    subtitle_font_size: int = 24
    subtitle_font_color: str = "white"
    subtitle_background: bool = True
    subtitle_background_opacity: float = 0.5
    subtitle_position: str = "bottom"

    # Video Composition Settings
    video_composition_max_retries: int = 3
    video_composition_timeout: int = 600

    # LLM Settings
    llm_max_retries: int = 3
    llm_timeout: int = 120

    # Language Settings
    target_language: str = "English"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    def create_directories(self):
        """Create all output directories if they don't exist"""
        for dir_path in [
            self.output_dir,
            self.scenes_dir,
            self.animations_dir,
            self.audio_dir,
            self.scripts_dir,
            self.final_dir,
            self.analyses_dir,
            self.rendering_dir,
            self.generation_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


def get_settings():
    """Get settings instance with environment variables"""
    return Settings()


settings = get_settings()
settings.create_directories()

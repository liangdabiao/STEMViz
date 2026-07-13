import logging
import time
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from config import settings
from agents.concept_interpreter import ConceptInterpreterAgent, ConceptAnalysis
from agents.manim_agent import ManimAgent
from agents.manim_models import AnimationConfig
from generation.script_generator import ScriptGenerator
from generation.tts.doubao_provider import DoubaoTTSSynthesizer
from generation.video_compositor import VideoCompositor


class Pipeline:
    """
    Main orchestration pipeline for STEM animation generation
    Uses Doubao (Volcano Engine) for all AI capabilities.
    """

    def __init__(self):
        self.config = settings
        self._setup_logging()

        llm_api_key = settings.doubao_api_key
        llm_base_url = settings.doubao_base_url

        # Initialize agents
        self.concept_interpreter = ConceptInterpreterAgent(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=settings.reasoning_model,
            reasoning_tokens=settings.interpreter_reasoning_tokens,
            reasoning_effort=settings.interpreter_reasoning_effort
        )

        # Initialize Manim Agent
        animation_config = AnimationConfig(
            quality=settings.manim_quality,
            background_color=settings.manim_background_color,
            frame_rate=settings.manim_frame_rate,
            max_scene_duration=settings.manim_max_scene_duration,
            total_video_duration_target=settings.manim_total_video_duration_target,
            temperature=settings.animation_temperature,
            max_retries_per_scene=settings.animation_max_retries_per_scene,
            enable_simplification=settings.animation_enable_simplification,
            render_timeout=settings.manim_render_timeout,
            code_gen_concurrency=settings.animation_code_gen_concurrency
        )

        self.manim_agent = ManimAgent(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=settings.code_gen_model,
            output_dir=settings.output_dir,
            config=animation_config,
            reasoning_tokens=settings.animation_reasoning_tokens,
            reasoning_effort=settings.animation_reasoning_effort
        )

        # Initialize Script Generator
        self.script_generator = ScriptGenerator(
            api_key=settings.doubao_api_key,
            output_dir=settings.scripts_dir,
            model=settings.multimodal_model,
            temperature=settings.script_generation_temperature,
            max_retries=settings.script_generation_max_retries,
            timeout=settings.script_generation_timeout,
            base_url=settings.doubao_base_url
        )

        # Initialize Audio Synthesizer (Doubao TTS)
        self.audio_synthesizer = DoubaoTTSSynthesizer(
            api_key=settings.doubao_tts_api_key,
            output_dir=settings.audio_dir,
            voice_id=settings.doubao_tts_voice_id,
            resource_id=settings.doubao_tts_resource_id,
            speed_ratio=settings.doubao_tts_speed_ratio,
            volume_ratio=settings.doubao_tts_volume_ratio,
            app_id=settings.doubao_tts_app_id,
            access_key=settings.doubao_tts_access_key,
            secret_key=settings.doubao_tts_secret_key,
            auth_mode=settings.doubao_tts_auth_mode,
            max_retries=settings.tts_max_retries,
            timeout=settings.tts_timeout
        )

        # Initialize Video Compositor
        self.video_compositor = VideoCompositor(
            output_dir=settings.final_dir,
            video_codec=settings.video_codec,
            video_preset=settings.video_preset,
            video_crf=settings.video_crf,
            audio_codec=settings.audio_codec,
            audio_bitrate=settings.audio_bitrate,
            subtitle_burn_in=settings.subtitle_burn_in,
            subtitle_font_size=settings.subtitle_font_size,
            subtitle_font_color=settings.subtitle_font_color,
            subtitle_background=settings.subtitle_background,
            subtitle_background_opacity=settings.subtitle_background_opacity,
            subtitle_position=settings.subtitle_position,
            max_retries=settings.video_composition_max_retries,
            timeout=settings.video_composition_timeout
        )

        self.logger.info("Pipeline initialized with Doubao AI")

    def _setup_logging(self):
        """Configure logging for pipeline"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.output_dir / 'pipeline.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("Pipeline")

    def run(
        self,
        concept: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        target_language: str = "English"
    ) -> Dict[str, Any]:
        """
        Execute the full pipeline.

        Args:
            concept: STEM concept to process
            progress_callback: Optional callback for progress updates (message, percentage)
            target_language: Target language for narration

        Returns:
            Dictionary with status, results, and metadata
        """

        start_time = time.time()
        self.logger.info(f"Starting pipeline for concept: {concept} in {target_language}")

        try:
            # Step 1: Concept Interpretation
            if progress_callback:
                progress_callback("正在解析概念...", 0.05)

            analysis = self._execute_concept_interpretation(concept)

            if progress_callback:
                progress_callback("概念解析完成", 0.15)

            analysis_path = self._save_analysis(analysis, concept)

            # Step 2: Animation Generation
            if progress_callback:
                progress_callback("规划动画场景...", 0.2)

            animation_result = self._execute_manim_generation(analysis)

            if progress_callback:
                progress_callback("动画生成完成", 0.55)

            # Step 3: Script Generation
            if animation_result.success and animation_result.silent_animation_path:
                if progress_callback:
                    progress_callback("生成旁白脚本...", 0.65)

                script_result = self._execute_script_generation(
                    animation_result.silent_animation_path, target_language
                )

                if progress_callback:
                    if script_result.success:
                        progress_callback("脚本生成完成", 0.75)
                    else:
                        progress_callback("脚本生成失败", 0.75)
            else:
                script_result = None

            # Step 4: Audio Synthesis
            if script_result and script_result.success:
                if progress_callback:
                    progress_callback("合成语音旁白...", 0.8)

                audio_result = self._execute_audio_synthesis(
                    script_result.script_path,
                    animation_result.total_duration if animation_result.success else None
                )

                if progress_callback:
                    if audio_result.success:
                        progress_callback("语音合成完成", 0.9)
                    else:
                        progress_callback("语音合成失败", 0.9)
            else:
                audio_result = None

            # Step 5: Video Composition
            if (animation_result and animation_result.success and
                audio_result and audio_result.success and
                script_result and script_result.success):

                if progress_callback:
                    progress_callback("合成最终视频...", 0.95)

                video_result = self._execute_video_composition(
                    animation_result.silent_animation_path,
                    audio_result.audio_path,
                    script_result.script_path
                )

                if progress_callback:
                    if video_result.success:
                        progress_callback("视频合成完成", 1.0)
                    else:
                        progress_callback("视频合成失败", 1.0)

                if video_result and video_result.success:
                    if progress_callback:
                        progress_callback("清理临时文件...", 1.0)
                    self._cleanup_temp_files(animation_result, audio_result)
            else:
                video_result = None

            # Calculate execution time
            duration = time.time() - start_time

            # Collect metadata
            steps_completed = ["concept_interpretation"]
            if animation_result.success:
                steps_completed.append("animation_generation")
            if script_result and script_result.success:
                steps_completed.append("script_generation")
            if audio_result and audio_result.success:
                steps_completed.append("audio_synthesis")
            if video_result and video_result.success:
                steps_completed.append("video_composition")

            metadata = {
                "total_duration": duration,
                "steps_completed": steps_completed,
                "timestamp": datetime.now().isoformat(),
                "token_usage": {
                    "concept_interpreter": self.concept_interpreter.get_token_usage(),
                    "manim_agent": self.manim_agent.get_token_usage()
                },
                "models_used": {
                    "reasoning": settings.reasoning_model,
                    "multimodal": settings.multimodal_model,
                    "tts": settings.doubao_tts_voice_id
                },
                "animation_stats": {
                    "scenes_planned": animation_result.scene_count,
                    "scenes_rendered": len([r for r in animation_result.render_results if r.success]),
                    "total_animation_duration": animation_result.total_duration,
                    "generation_time": animation_result.generation_time
                } if animation_result.success else None,
                "script_stats": {
                    "subtitles_generated": len(script_result.subtitles) if script_result else 0,
                    "script_duration": script_result.total_duration if script_result else None,
                    "script_generation_time": script_result.generation_time if script_result else None
                } if script_result else None,
                "audio_stats": {
                    "audio_segments": len(audio_result.audio_segments) if audio_result else 0,
                    "audio_duration": audio_result.total_duration if audio_result else None,
                    "file_size_mb": audio_result.file_size_mb if audio_result else None,
                    "audio_synthesis_time": audio_result.generation_time if audio_result else None
                } if audio_result else None,
                "video_stats": {
                    "output_duration": video_result.output_duration if video_result else None,
                    "file_size_mb": video_result.file_size_mb if video_result else None,
                    "resolution": video_result.resolution if video_result else None,
                    "video_composition_time": video_result.generation_time if video_result else None
                } if video_result else None
            }

            all_succeeded = (
                animation_result.success
                and (script_result is not None and script_result.success)
                and (audio_result is not None and audio_result.success)
                and (video_result is not None and video_result.success)
            )

            self.logger.info(
                f"Pipeline {'completed successfully' if all_succeeded else 'completed with errors'} in {duration:.2f}s"
            )

            return {
                "status": "success" if all_succeeded else "partial",
                "concept_analysis": analysis.model_dump(),
                "analysis_path": str(analysis_path),
                "animation_result": animation_result.model_dump() if animation_result.success else None,
                "script_result": script_result.model_dump() if script_result else None,
                "audio_result": audio_result.model_dump() if audio_result else None,
                "video_result": video_result.model_dump() if video_result else None,
                "metadata": metadata,
                "error": None if all_succeeded else "Some steps failed"
            }

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Pipeline failed: {e}")

            return {
                "status": "error",
                "concept_analysis": None,
                "analysis_path": None,
                "animation_result": None,
                "script_result": None,
                "audio_result": None,
                "video_result": None,
                "metadata": {
                    "total_duration": duration,
                    "steps_completed": [],
                    "timestamp": datetime.now().isoformat()
                },
                "error": str(e)
            }

    def _execute_concept_interpretation(self, concept: str) -> ConceptAnalysis:
        self.logger.info("Step 1: Concept Interpretation")
        return self.concept_interpreter.execute(concept)

    def _save_analysis(self, analysis: ConceptAnalysis, original_concept: str) -> Path:
        safe_name = "".join(c if c.isalnum() else "_" for c in original_concept.lower())
        safe_name = safe_name[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.json"
        filepath = self.config.analyses_dir / filename

        with open(filepath, 'w') as f:
            json.dump(analysis.model_dump(), f, indent=2)

        self.logger.info(f"Analysis saved to {filepath}")
        return filepath

    def _execute_manim_generation(self, analysis: ConceptAnalysis):
        self.logger.info("Step 2: Animation Generation")
        return self.manim_agent.execute(analysis)

    def _execute_script_generation(self, animation_path: str, target_language: str = "English"):
        self.logger.info(f"Step 3: Script Generation in {target_language}")
        return self.script_generator.execute(animation_path, target_language)

    def _execute_audio_synthesis(self, script_path: str, target_duration: Optional[float] = None):
        self.logger.info("Step 4: Audio Synthesis")
        return self.audio_synthesizer.execute(script_path, target_duration)

    def _execute_video_composition(self, animation_path: str, audio_path: str, subtitle_path: Optional[str] = None):
        self.logger.info("Step 5: Video Composition")

        animation_name = Path(animation_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{animation_name}_final_{timestamp}.mp4"

        return self.video_compositor.execute(
            video_path=animation_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_filename=output_filename
        )

    def _cleanup_temp_files(self, animation_result, audio_result):
        self.logger.info("Starting cleanup of temporary files")

        cleaned_items = []

        try:
            if animation_result and animation_result.render_results:
                for render_result in animation_result.render_results:
                    if render_result.video_path:
                        video_path = Path(render_result.video_path)
                        if video_path.exists():
                            video_path.unlink()
                            cleaned_items.append(f"scene video: {video_path.name}")

            if animation_result and animation_result.silent_animation_path:
                silent_path = Path(animation_result.silent_animation_path)
                if silent_path.exists():
                    silent_path.unlink()
                    cleaned_items.append(f"silent animation: {silent_path.name}")

            if audio_result and audio_result.audio_segments:
                for segment in audio_result.audio_segments:
                    if segment.audio_path:
                        segment_path = Path(segment.audio_path)
                        if segment_path.exists():
                            segment_path.unlink()
                            cleaned_items.append(f"audio segment: {segment_path.name}")

            if audio_result and audio_result.audio_path:
                audio_path = Path(audio_result.audio_path)
                padded_files = list(audio_path.parent.glob(f"{audio_path.stem}_padded_*.mp3"))
                if padded_files:
                    if audio_path.exists():
                        audio_path.unlink()
                        cleaned_items.append(f"non-padded audio: {audio_path.name}")

            segments_dir = settings.audio_dir / "segments"
            if segments_dir.exists() and not any(segments_dir.iterdir()):
                segments_dir.rmdir()
                cleaned_items.append("empty segments directory")

            scene_codes_dir = settings.output_dir / "scene_codes"
            if scene_codes_dir.exists():
                for code_file in scene_codes_dir.glob("*"):
                    if code_file.is_file() and (code_file.suffix == ".py" or code_file.name.endswith(".raw.txt")):
                        try:
                            code_file.unlink()
                            cleaned_items.append(f"scene code: {code_file.name}")
                        except Exception as e:
                            self.logger.warning(f"Could not remove {code_file}: {e}")

            media_dir = Path("media")
            if media_dir.exists():
                videos_dir = media_dir / "videos"
                if videos_dir.exists():
                    for temp_dir in videos_dir.iterdir():
                        if temp_dir.is_dir() and temp_dir.name.startswith("tmp"):
                            try:
                                shutil.rmtree(temp_dir)
                                cleaned_items.append(f"temp video dir: {temp_dir.name}")
                            except Exception as e:
                                self.logger.warning(f"Could not remove temp dir {temp_dir}: {e}")

                images_dir = media_dir / "images"
                if images_dir.exists():
                    for temp_dir in images_dir.iterdir():
                        if temp_dir.is_dir() and temp_dir.name.startswith("tmp"):
                            try:
                                shutil.rmtree(temp_dir)
                                cleaned_items.append(f"temp image dir: {temp_dir.name}")
                            except Exception as e:
                                self.logger.warning(f"Could not remove temp dir {temp_dir}: {e}")

            self.logger.info(f"Cleanup complete: removed {len(cleaned_items)} items")
            for item in cleaned_items[:10]:
                self.logger.debug(f"  - Removed {item}")
            if len(cleaned_items) > 10:
                self.logger.debug(f"  - ... and {len(cleaned_items) - 10} more items")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

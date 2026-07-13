import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from generation.script_generator import ScriptGenerator
from generation.tts import DoubaoTTSSynthesizer
from generation.video_compositor import VideoCompositor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    animation_path = r"d:\STEMViz-main\output\animations\animation_20260713_000846.mp4"
    
    if not os.path.exists(animation_path):
        print(f"ERROR: Animation file not found: {animation_path}")
        return
    
    print("=" * 60)
    print("继续执行 Pipeline: 脚本生成 → TTS → 视频合成")
    print("=" * 60)
    print(f"输入动画: {animation_path}")
    print()
    
    # Step 1: Script Generation
    print("📝 步骤 3/5: 生成旁白脚本...")
    print("-" * 60)
    
    script_generator = ScriptGenerator(
        api_key=settings.doubao_api_key,
        output_dir=settings.scripts_dir,
        model=settings.multimodal_model,
        temperature=settings.script_generation_temperature,
        max_retries=settings.script_generation_max_retries,
        timeout=settings.script_generation_timeout,
        base_url=settings.doubao_base_url
    )
    
    try:
        script_result = script_generator.execute(animation_path, "English")
        if not script_result.success:
            print(f"❌ 脚本生成失败: {script_result.error_message}")
            return
        print(f"✅ 脚本生成成功!")
        print(f"   脚本路径: {script_result.script_path}")
        print(f"   视频时长: {script_result.video_duration:.1f}s")
        print(f"   字幕条数: {len(script_result.subtitles)}")
        print()
    except Exception as e:
        print(f"❌ 脚本生成失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Audio Synthesis
    print("🎙️ 步骤 4/5: TTS 语音合成...")
    print("-" * 60)
    
    audio_synthesizer = DoubaoTTSSynthesizer(
        api_key=settings.doubao_tts_api_key,
        output_dir=settings.audio_dir,
        voice_id=settings.doubao_tts_voice_id,
        speed_ratio=settings.doubao_tts_speed_ratio,
        volume_ratio=settings.doubao_tts_volume_ratio,
        resource_id=settings.doubao_tts_resource_id,
        auth_mode=settings.doubao_tts_auth_mode,
        app_id=settings.doubao_tts_app_id,
        access_key=settings.doubao_tts_access_key,
        secret_key=settings.doubao_tts_secret_key
    )
    
    try:
        audio_result = audio_synthesizer.execute(script_result.script_path, None)
        if not audio_result.success:
            print(f"❌ TTS 语音合成失败: {audio_result.error_message}")
            return
        print(f"✅ TTS 语音合成成功!")
        print(f"   音频路径: {audio_result.audio_path}")
        print(f"   音频时长: {audio_result.total_duration:.1f}s")
        print(f"   文件大小: {audio_result.file_size_mb:.2f} MB")
        print()
    except Exception as e:
        print(f"❌ TTS 语音合成失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Video Composition
    print("🎬 步骤 5/5: 视频合成 (旁白 + 字幕)...")
    print("-" * 60)
    
    video_compositor = VideoCompositor(
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
    
    animation_name = Path(animation_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{animation_name}_final_{timestamp}.mp4"
    
    try:
        final_result = video_compositor.execute(
            video_path=animation_path,
            audio_path=audio_result.audio_path,
            subtitle_path=script_result.script_path,
            output_filename=output_filename
        )
        if not final_result.success:
            print(f"❌ 视频合成失败: {final_result.error_message}")
            return
        print(f"✅ 视频合成成功!")
        print(f"   最终视频: {final_result.output_path}")
        print(f"   视频时长: {final_result.output_duration:.1f}s")
        print(f"   文件大小: {final_result.file_size_mb:.2f} MB")
        print()
    except Exception as e:
        print(f"❌ 视频合成失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 60)
    print("🎉 全部完成!")
    print("=" * 60)
    print(f"最终视频: {final_result.output_path}")

if __name__ == "__main__":
    main()

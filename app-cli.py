#!/usr/bin/env python3
"""
STEMViz 命令行工具 - 从概念生成 STEM 动画视频

使用方法:
    python app-cli.py "讲解勾股定理"
    python app-cli.py "美国总统加菲尔德的勾股定理证明" --lang 中文
    python app-cli.py "解释冒泡排序" --lang English --output ./output
"""

import argparse
import sys
import time
from pathlib import Path

from pipeline import Pipeline


def progress_callback(message: str, percentage: float):
    """进度回调函数"""
    bar_length = 30
    filled = int(bar_length * percentage)
    bar = "█" * filled + "░" * (bar_length - filled)
    percent_str = f"{percentage * 100:5.1f}%"
    print(f"\r  [{bar}] {percent_str} {message}", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="STEMViz - 从概念生成 STEM 动画视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python app-cli.py "讲解勾股定理"
  python app-cli.py "美国总统加菲尔德的勾股定理证明" --lang 中文
  python app-cli.py "解释冒泡排序" --lang English
        """
    )

    parser.add_argument(
        "concept",
        help="要生成视频的 STEM 概念（如：讲解勾股定理）"
    )

    parser.add_argument(
        "--lang", "--language",
        dest="language",
        default="中文",
        help="目标语言（默认：中文）"
    )

    parser.add_argument(
        "--output",
        default=None,
        help="输出目录（默认使用配置文件中的设置）"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，减少输出"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  STEMViz - STEM 动画视频生成器")
    print("=" * 60)
    print(f"  概念: {args.concept}")
    print(f"  语言: {args.language}")
    print("=" * 60)
    print()

    try:
        print("🚀 正在初始化 Pipeline...")
        pipeline = Pipeline()
        print()

        print("🎬 开始生成视频...")
        print()

        start_time = time.time()

        result = pipeline.run(
            concept=args.concept,
            progress_callback=None if args.quiet else progress_callback,
            target_language=args.language
        )

        total_time = time.time() - start_time

        if not args.quiet:
            print()
            print()

        if result.get("status") == "success":
            print("=" * 60)
            print("  ✅ 视频生成成功！")
            print("=" * 60)

            video_result = result.get("video_result", {})
            if video_result:
                output_path = video_result.get("output_path", "")
                if output_path:
                    print(f"  📁 视频路径: {output_path}")

                duration = video_result.get("duration", 0)
                if duration:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    print(f"  ⏱️  视频时长: {minutes}分{seconds:.1f}秒")

                file_size = video_result.get("file_size", 0)
                if file_size:
                    size_mb = file_size / (1024 * 1024)
                    print(f"  📦 文件大小: {size_mb:.2f} MB")

            script_result = result.get("script_result", {})
            if script_result:
                subtitle_count = script_result.get("subtitle_count", 0)
                if subtitle_count:
                    print(f"  💬 字幕数量: {subtitle_count} 条")

            print(f"  ⚡ 总耗时: {total_time:.1f} 秒 ({total_time/60:.1f} 分钟)")
            print("=" * 60)

            if args.output and video_result.get("output_path"):
                src = Path(video_result["output_path"])
                dst_dir = Path(args.output)
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst = dst_dir / src.name
                import shutil
                shutil.copy2(src, dst)
                print(f"  📋 已复制到: {dst}")

            return 0
        else:
            print("=" * 60)
            print("  ❌ 生成失败")
            print("=" * 60)
            error = result.get("error", "未知错误")
            print(f"  错误信息: {error}")
            print("=" * 60)
            return 1

    except KeyboardInterrupt:
        print()
        print()
        print("⚠️  用户中断")
        return 130
    except Exception as e:
        print()
        print()
        print("=" * 60)
        print("  ❌ 发生错误")
        print("=" * 60)
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

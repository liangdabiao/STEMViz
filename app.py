#!/usr/bin/env python3
"""
STEMViz - STEM 概念动画生成器
简单界面：输入概念 -> 进度条 -> 视频播放
"""

import gradio as gr
from pipeline import Pipeline
from pathlib import Path

pipeline = Pipeline()

def generate_animation(concept: str, language: str = "中文", progress=gr.Progress()):
    """
    Gradio 主生成函数

    参数:
        concept: 用户输入的 STEM 概念
        language: 旁白语言（中文、英文、西班牙语、越南语）
        progress: Gradio 进度追踪器

    返回:
        视频文件路径或错误信息
    """
    if not concept or concept.strip() == "":
        return None, "请输入要讲解的概念"
    
    def update_progress(message: str, percentage: float):
        progress(percentage, desc=message)
    
    result = pipeline.run(concept, progress_callback=update_progress, target_language=language)
    
    if result["status"] == "success" and result.get("video_result"):
        video_path = result["video_result"]["output_path"]
        if Path(video_path).exists():
            return video_path, "✅ 生成成功！"
        else:
            return None, "❌ 视频文件未找到"
    else:
        error_msg = result.get("error", "未知错误")
        return None, f"❌ 生成失败：{error_msg}"

with gr.Blocks(title="STEMViz - STEM 概念动画生成器") as demo:
    gr.Markdown("# 🎓 STEMViz")
    gr.Markdown("将 STEM 概念转化为带旁白的教学动画视频")
    
    with gr.Row():
        with gr.Column():
            concept_input = gr.Textbox(
                label="输入 STEM 概念",
                placeholder="例如：讲解勾股定理、解释冒泡排序、什么是导数...",
                lines=2
            )
            language_dropdown = gr.Dropdown(
                choices=["中文", "English", "Spanish", "Vietnamese"],
                value="中文",
                label="旁白语言"
            )
            generate_btn = gr.Button("生成动画", variant="primary")
        
    with gr.Row():
        video_output = gr.Video(
            label="生成的动画",
            autoplay=True
        )
    
    with gr.Row():
        status_output = gr.Textbox(
            label="状态",
            interactive=False,
            lines=1
        )
    
    gr.Examples(
        examples=[
            ["讲解勾股定理"],
            ["解释冒泡排序算法"],
            ["什么是导数"]
        ],
        inputs=concept_input
    )
    
    generate_btn.click(
        fn=generate_animation,
        inputs=[concept_input, language_dropdown],
        outputs=[video_output, status_output]
    )

if __name__ == "__main__":
    demo.launch(share=False, inbrowser=True)

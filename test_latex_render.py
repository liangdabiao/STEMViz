from manim import *
import sys
import os

miktex_path = r"C:\Users\49707\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
os.environ["PATH"] = miktex_path + ";" + os.environ.get("PATH", "")

class TestLatex(Scene):
    def construct(self):
        text = MathTex(r"y = mx + b")
        self.add(text)
        self.wait(1)

if __name__ == "__main__":
    from manim import config
    config.output_file = "test_latex"
    config.media_dir = r"d:\STEMViz-main\output\test_render"
    config.quality = "low_quality"
    config.preview = False
    
    from manim.renderer import Renderer
    scene = TestLatex()
    scene.render()
    print("SUCCESS: LaTeX test passed!")

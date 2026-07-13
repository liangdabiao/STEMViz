from manim import *

class TestLatex(Scene):
    def construct(self):
        formula = MathTex(r"y = mx + b")
        self.play(Write(formula))
        self.wait(2)

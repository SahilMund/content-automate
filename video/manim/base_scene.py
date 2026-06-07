"""
Base Manim scene template for DraftPilot concept animations.
The LLM generates a subclass of ConceptScene with topic-specific visuals.
Run directly: manim -pql scene.py ConceptScene
"""
from manim import *


class ConceptScene(Scene):
    """Override build_concept() in the LLM-generated subclass."""

    TOPIC    = "Topic"
    HANDLE   = "@the.undefined.parts"
    ACCENT   = "#7C3AED"
    BG_COLOR = "#0F0F1A"

    def construct(self):
        self.camera.background_color = self.BG_COLOR
        self.play_intro()
        self.build_concept()
        self.play_outro()

    # ── Shared intro / outro ──────────────────────────────────

    def play_intro(self):
        title = Text(self.TOPIC, font_size=52, weight=BOLD, color=WHITE)
        title.set_stroke(color=self.ACCENT, width=1, background=False)
        bar = Line(LEFT * 3, RIGHT * 3, color=self.ACCENT, stroke_width=3).next_to(title, DOWN, buff=0.3)
        self.play(Write(title, run_time=1.2), Create(bar, run_time=0.8))
        self.wait(0.8)
        self.play(FadeOut(title), FadeOut(bar), run_time=0.5)

    def play_outro(self):
        handle = Text(self.HANDLE, font_size=36, color=self.ACCENT, weight=BOLD)
        tagline = Text("Follow for daily AI insights", font_size=24, color=GRAY).next_to(handle, DOWN, buff=0.2)
        self.play(FadeIn(handle, shift=UP * 0.3), FadeIn(tagline), run_time=1)
        self.wait(1.5)

    # ── Placeholder concept (LLM overrides this) ─────────────

    def build_concept(self):
        """Override this in the generated scene."""
        box = RoundedRectangle(corner_radius=0.3, width=6, height=3, color=self.ACCENT)
        label = Text("Concept animation goes here", font_size=28, color=WHITE).move_to(box)
        self.play(Create(box), Write(label))
        self.wait(2)
        self.play(FadeOut(box), FadeOut(label))

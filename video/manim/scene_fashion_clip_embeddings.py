"""
Base Manim scene template for DraftPilot concept animations.
The LLM generates a subclass of ConceptScene with topic-specific visuals.
Run directly: manim -pql scene.py ConceptScene
"""
from manim import *


class ConceptScene(Scene):
    """Override build_concept() in the LLM-generated subclass."""

    TOPIC    = "fashion clip embeddings"
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
        def build_concept(self):
            # Create a 2D space to visualize the vectors
            axes = Axes(
                x_range=[-10, 10, 2],
                y_range=[-10, 10, 2],
                x_length=10,
                y_length=6,
                axis_config={"include_tip": False},
                color=GRAY
            )
            self.play(Create(axes), run_time=1)

            # Initialize vectors
            vectors = VGroup(
                Dot(axes.coords_to_point(-5, -5), color=self.ACCENT),
                Dot(axes.coords_to_point(-3, -4), color=self.ACCENT),
                Dot(axes.coords_to_point(-2, -3), color=self.ACCENT),
                Dot(axes.coords_to_point(2, 3), color=self.ACCENT),
                Dot(axes.coords_to_point(3, 4), color=self.ACCENT),
                Dot(axes.coords_to_point(5, 5), color=self.ACCENT),
            )
            self.play(Create(vectors), run_time=1.5)

            # Animate the vectors clustering
            self.play(
                vectors[0].animate.move_to(axes.coords_to_point(-4, -4)),
                vectors[1].animate.move_to(axes.coords_to_point(-4, -3)),
                vectors[2].animate.move_to(axes.coords_to_point(-4, -2)),
                vectors[3].animate.move_to(axes.coords_to_point(4, 2)),
                vectors[4].animate.move_to(axes.coords_to_point(4, 3)),
                vectors[5].animate.move_to(axes.coords_to_point(4, 4)),
                run_time=2
            )

            # Add labels to the clusters
            cluster_labels = VGroup(
                Text("Fashion", color=WHITE).next_to(axes.coords_to_point(-4, -3), LEFT),
                Text("Non-Fashion", color=WHITE).next_to(axes.coords_to_point(4, 3), RIGHT),
            )
            self.play(Create(cluster_labels), run_time=0.5)

            # Animate a CLIP embedding
            clip_embedding = Dot(axes.coords_to_point(0, 0), color=self.ACCENT)
            self.play(Create(clip_embedding), run_time=0.5)
            self.play(
                clip_embedding.animate.move_to(axes.coords_to_point(-4, -3)),
                run_time=1
            )

            # Add a label to the CLIP embedding
            clip_label = Text("CLIP Embedding", color=WHITE).next_to(clip_embedding, DOWN)
            self.play(Create(clip_label), run_time=0.5)

            self.wait(2)
            self.play(FadeOut(VGroup(axes, vectors, cluster_labels, clip_embedding, clip_label)), run_time=1.5)

"""Render the Hindi captions as transparent PNGs (1080x300), one per line.

Manim is used only because its text engine (Pango) shapes Devanagari correctly;
the image library used for the video frames does not.

Render (from this folder):
    uv run --no-project --python 3.12 --with manim \
        python -m manim -s -t -a --media_dir <somewhere> make_captions.py
Then copy the Caption1..3 PNGs into captions/ as line1.png .. line3.png.
"""

from manim import *

config.pixel_width, config.pixel_height = 1080, 300
config.frame_width, config.frame_height = 10.8, 3.0
config.background_opacity = 0.0

FONT = "Nirmala UI"
LINES = [
    "क्या कर रहे हो समीर?",
    "दिख नहीं रहा !!!",
    "मैं बर्तनों पर हाथ\nसाफ़ कर रहा हूँ।",
]


def caption_scene(text):
    class _Caption(Scene):
        def construct(self):
            label = Text(text, font=FONT, weight=BOLD, font_size=44, line_spacing=0.9)
            if label.width > 9.6:
                label.scale_to_fit_width(9.6)
            if label.height > 2.2:
                label.scale_to_fit_height(2.2)
            box = RoundedRectangle(
                width=label.width + 0.6, height=label.height + 0.5, corner_radius=0.25
            ).set_fill(BLACK, 0.72).set_stroke(WHITE, 2, opacity=0.6)
            self.add(box, label)

    return _Caption


for _n, _text in enumerate(LINES, 1):
    globals()[f"Caption{_n}"] = type(f"Caption{_n}", (caption_scene(_text),), {})

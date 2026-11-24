"""Turn the six-panel comic into a vertical Short (1080x1920, 30 fps).

Each panel is shown in turn while its line is spoken; there is a beat before the
punchline panel, and the laugh track plays over the last panel.

Run (from this folder):
    uv run --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_short.py
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).parent
COMIC = HERE / "Park Bench Name-Change Punchline.png"
OUTPUT = HERE / "purana-naam-roshan-short.mp4"

W, H, FPS, RATE = 1080, 1920, 30, 44100
CHANNEL = "Jokes Apart"

# Panel boxes in the comic image (left, top, right, bottom), in reading order.
COLS = [(0, 589), (601, 1215)]
ROWS = [(0, 430), (437, 852), (862, 1295)]
PANELS = [(c[0], r[0], c[1], r[1]) for r in ROWS for c in COLS]

# (panel index, audio clip, pause after the clip ends before the next panel)
BEATS = [
    (0, "line1", 0.45),
    (1, "line2", 0.45),
    (2, "line3", 0.45),
    (3, "line4", 0.95),   # the beat before the punchline
    (4, "line5", 0.20),   # punchline, then straight into the laughter
    (5, "laughter", 0.60),
]
LEAD_IN = 0.35       # silence before the first panel's line
VOICE_DELAY = 0.25   # a panel appears this long before its line starts
FADE = 0.25          # crossfade between panels
ZOOM = 0.06          # slow push-in on each panel over its time on screen


def decode_mono(path):
    resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
    parts = []
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            parts += [r.to_ndarray().ravel() for r in resampler.resample(frame)]
        parts += [r.to_ndarray().ravel() for r in resampler.resample(None)]
    return np.concatenate(parts).astype(np.float64) / 32768


def schedule():
    """Return [(panel, start, end)], [(clip, at, samples)] and the total length."""
    shots, sounds, t = [], [], LEAD_IN
    for panel, clip, pause in BEATS:
        samples = decode_mono(HERE / "audio" / f"{clip}.mp3")
        length = len(samples) / RATE
        start = t - (LEAD_IN if not shots else 0)
        sounds.append((clip, t + VOICE_DELAY, samples))
        t = t + VOICE_DELAY + length + pause
        shots.append((panel, start, t))
    return shots, sounds, t


def prepare(comic, box):
    """A panel scaled to the frame width (with zoom headroom) and its backdrop."""
    panel = comic.crop(box)
    width = int(W * (1 + ZOOM)) + 2
    sharp = panel.resize((width, round(panel.height * width / panel.width)), Image.LANCZOS)
    sharp = sharp.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    scale = max(W / panel.width, H / panel.height) * 1.1
    backdrop = panel.resize((round(panel.width * scale), round(panel.height * scale)), Image.BICUBIC)
    left, top = (backdrop.width - W) // 2, (backdrop.height - H) // 2
    backdrop = backdrop.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(28))
    backdrop = ImageEnhance.Brightness(backdrop).enhance(0.42)
    return sharp, backdrop


def render_shot(sharp, backdrop, progress, label):
    """One frame of a panel; progress runs 0..1 over the panel's time on screen."""
    frame = backdrop.copy()
    zoom = 1 + ZOOM * progress
    base_h = round(sharp.height * W / sharp.width)
    crop_w, crop_h = sharp.width / zoom, sharp.height / zoom  # the part shown at this zoom
    left, top = (sharp.width - crop_w) / 2, (sharp.height - crop_h) / 2
    view = sharp.resize((W, base_h), Image.BILINEAR, box=(left, top, left + crop_w, top + crop_h))
    y = (H - base_h) // 2 - 40
    frame.paste(view, (0, y))
    draw = ImageDraw.Draw(frame)
    draw.rectangle([0, y - 6, W, y - 1], fill="white")
    draw.rectangle([0, y + base_h, W, y + base_h + 5], fill="white")
    frame.paste(label, ((W - label.width) // 2, 250), label)
    return frame


def channel_label():
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 64)
    box = font.getbbox(CHANNEL)
    image = Image.new("RGBA", (box[2] + 40, box[3] + 30), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((22, 12), CHANNEL, font=font, fill=(0, 0, 0, 160))
    draw.text((20, 10), CHANNEL, font=font, fill=(255, 214, 77, 255))
    return image


def main():
    comic = Image.open(COMIC).convert("RGB")
    shots, sounds, total = schedule()
    prepared = [prepare(comic, box) for box in PANELS]
    label = channel_label()

    track = np.zeros(int((total + 0.5) * RATE))
    for _clip, at, samples in sounds:
        start = int(at * RATE)
        track[start:start + len(samples)] += samples[: len(track) - start]
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)

    def frame_at(t):
        for k, (panel, start, end) in enumerate(shots):
            if start <= t < end or k == len(shots) - 1:
                image = render_shot(*prepared[panel], (t - start) / (end - start), label)
                if k > 0 and t - start < FADE:          # crossfade from the previous panel
                    p_panel, p_start, p_end = shots[k - 1]
                    before = render_shot(*prepared[p_panel], (t - p_start) / (p_end - p_start), label)
                    image = Image.blend(before, image, (t - start) / FADE)
                return image

    with av.open(str(OUTPUT), "w") as out:
        video = out.add_stream("libx264", rate=FPS)
        video.width, video.height, video.pix_fmt = W, H, "yuv420p"
        video.options = {"crf": "18", "preset": "medium"}
        audio = out.add_stream("aac", rate=RATE, layout="mono")
        to_aac = av.AudioResampler(format="fltp", layout="mono", rate=RATE)

        n_frames = int(total * FPS)
        for n in range(n_frames):
            image = frame_at(n / FPS)
            if n >= n_frames - 9:                        # short fade to black at the end
                image = Image.blend(image, Image.new("RGB", (W, H)), (n - (n_frames - 9)) / 9)
            out.mux(video.encode(av.VideoFrame.from_image(image)))
        out.mux(video.encode(None))

        for i in range(0, int(total * RATE), 1024):
            frame = av.AudioFrame.from_ndarray(pcm[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
            frame.sample_rate, frame.pts = RATE, i
            for resampled in to_aac.resample(frame):
                out.mux(audio.encode(resampled))
        out.mux(audio.encode(None))

    for (panel, start, end), (clip, at, samples) in zip(shots, sounds):
        print(f"panel {panel + 1}: {start:5.2f}-{end:5.2f}s   {clip} at {at:5.2f}s ({len(samples) / RATE:.2f}s)")
    print(f"wrote {OUTPUT.name}: {total:.1f}s")


if __name__ == "__main__":
    sys.exit(main())

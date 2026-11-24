"""Assemble the lip-synced Short (1080x1920, 25 fps).

Teacher and student trade the four lines in a classroom (each with its Hindi
caption while it is spoken), then the teacher is left dumbfounded with the laugh
track over him.

Run (from this folder):
    uv run --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_short_lipsync.py
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image

from make_vertical_clip import RATE, WINDOW_H, WINDOW_Y, decode_mono, label_image, reframe

HERE = Path(__file__).parent
OUTPUT = HERE / "dinosaur-kab-vilupt-hue-lipsync-short.mp4"
FPS = 25

TEACHER_X, STUDENT_X = 0.50, 0.47   # crop centres across the 16:9 frame (the student's keeps his raised hand in shot)

# (talking clip, voice line, face position, [(caption, shown from this second of the line)], pause after the line)
BEATS = [
    ("line1-teacher", "line1", TEACHER_X, [("line1", 0.0)], 0.25),
    ("line2-student", "line2", STUDENT_X, [("line2", 0.0)], 0.35),
    ("line3-teacher", "line3", TEACHER_X, [("line3", 0.0)], 0.25),
    # The punchline is long, so its caption changes after "...कहा था कि" (about 2.8 s in; estimated
    # from the speaking pace, as this take has no pause there).
    ("line4-student-first-wording", "line4", STUDENT_X, [("line4a", 0.0), ("line4b", 2.8)], 0.10),
]
# The punchline was reworded after its clip was lip-synced, and the clip could not be redone, so
# the old clip is retimed to the new voice line: (second of the voice line, second of the clip)
# pairs matching where speech starts, pauses after "सर," and ends. The mouth moves when the voice
# does, but not syllable for syllable.
RETIME = {
    "line4-student-first-wording": [(0, 0), (0.12, 0.14), (0.50, 0.56), (0.92, 1.02), (6.82, 7.44), (7.20, 7.88)],
}
# Reaction: still of the dumbfounded teacher, a silent beat, then the laugh track.
REACTION_STILL, REACTION_X, REACTION_BEAT, REACTION_SOUND, REACTION_TAIL = (
    HERE / "characters" / "teacher-stunned.png", 0.47, 0.6, "laughter", 0.5)
CAPTION_Y = WINDOW_Y + WINDOW_H - 300
# Silent lead-in before the first line: the first frame of the first clip, easing out from a
# slight zoom so it lands exactly on the clip's own framing.
LEAD_IN_SECONDS, LEAD_IN_ZOOM = 1.0, 0.06


def clip_frames(path):
    """All frames of a clip, plus its frame rate."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        return [frame.to_image() for frame in container.decode(stream)], float(stream.average_rate)


def push_in(still, centre_x, count, amount, label):
    """`count` vertical frames of a still with a slow zoom towards the face."""
    w, h = still.size
    cache, shots = {}, []
    for k in range(count):
        zoom = 1 + amount * k / count
        cw, ch = w / zoom, h / zoom
        left, top = (w - cw) * centre_x, (h - ch) * 0.25
        zoomed = still.resize((w, h), Image.BILINEAR, box=(left, top, left + cw, top + ch))
        shots.append(reframe(zoomed, centre_x, cache, label))
    return shots


def main():
    label = label_image()
    captions = {name: Image.open(HERE / "captions" / f"{name}.png").convert("RGBA")
                for *_, cards, _ in BEATS for name, _ in cards}
    frames, sounds = [], []          # frames: finished vertical images; sounds: (name, start_s, samples)

    def add(image, caption=None):
        if caption is not None:
            image = image.copy()
            image.paste(caption, (0, CAPTION_Y), caption)
        frames.append(image)

    for clip, voice, centre_x, cards, pause in BEATS:
        cache = {}
        source, source_fps = clip_frames(HERE / "lipsync" / f"{clip}-raw.mp4")
        if not frames and LEAD_IN_SECONDS:
            frames += reversed(push_in(source[0], centre_x, round(LEAD_IN_SECONDS * FPS), LEAD_IN_ZOOM, label))
        samples = decode_mono(HERE / "audio" / f"{voice}.mp3")
        sounds.append((voice, len(frames) / FPS, samples))
        spoken = len(samples) / RATE
        count = round(len(source) / source_fps * FPS)       # the clip, resampled to 25 fps if need be
        at_voice, at_clip = zip(*RETIME.get(clip, [(0, 0), (count / FPS, count / FPS)]))
        count = round(at_voice[-1] * FPS)
        shot = None
        for k in range(count):
            t = k / FPS
            clip_t = float(np.interp(t, at_voice, at_clip))
            shot = reframe(source[min(int(clip_t * source_fps), len(source) - 1)], centre_x, cache, label)
            current = [name for name, start in cards if start <= t]
            add(shot, captions[current[-1]] if t < spoken else None)
        for _ in range(round(pause * FPS)):                 # hold the last frame for the pause
            add(shot)

    # Reaction: the dumbfounded teacher with a slow push-in; a silent beat, then the laughter.
    samples = decode_mono(HERE / "audio" / f"{REACTION_SOUND}.mp3")
    sounds.append((REACTION_SOUND, len(frames) / FPS + REACTION_BEAT, samples))
    count = round((REACTION_BEAT + len(samples) / RATE + REACTION_TAIL) * FPS)
    still = Image.open(REACTION_STILL).convert("RGB")
    for k, image in enumerate(push_in(still, REACTION_X, count, 0.12, label)):
        if k >= count - 8:                         # fade to black at the very end
            image = Image.blend(image, Image.new("RGB", image.size), (k - (count - 8)) / 8)
        frames.append(image)

    total = len(frames) / FPS
    track = np.zeros(int((total + 0.5) * RATE))
    for _, start, samples in sounds:
        at = int(start * RATE)
        track[at:at + len(samples)] += samples[: len(track) - at] / 32768
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)

    with av.open(str(OUTPUT), "w") as out:
        video = out.add_stream("libx264", rate=FPS)
        video.width, video.height, video.pix_fmt = frames[0].width, frames[0].height, "yuv420p"
        video.options = {"crf": "18", "preset": "medium"}
        audio = out.add_stream("aac", rate=RATE, layout="mono")
        to_aac = av.AudioResampler(format="fltp", layout="mono", rate=RATE)
        for image in frames:
            out.mux(video.encode(av.VideoFrame.from_image(image)))
        out.mux(video.encode(None))
        for i in range(0, int(total * RATE), 1024):
            chunk = av.AudioFrame.from_ndarray(pcm[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
            chunk.sample_rate, chunk.pts = RATE, i
            for resampled in to_aac.resample(chunk):
                out.mux(audio.encode(resampled))
        out.mux(audio.encode(None))

    for name, start, samples in sounds:
        print(f"{name:10s} starts {start:5.2f}s, lasts {len(samples) / RATE:.2f}s")
    print(f"wrote {OUTPUT.name}: {total:.1f}s, {len(frames)} frames")


if __name__ == "__main__":
    sys.exit(main())

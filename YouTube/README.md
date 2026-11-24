# Jokes Apart: how the Shorts are made

Hindi joke Shorts for the YouTube channel "Jokes Apart". Each Short is a cartoon
scene per line of the joke, lip-synced to a generated voice, with a Hindi caption
while the line is spoken and a laugh track over a reaction shot at the end.

This repository holds the scripts, captions, joke text and shared reference
files. Per-video media (images, voice takes, lip-sync clips, finished videos) is
not tracked; see `.gitignore`.

## Layout

| Path | What it is |
|---|---|
| `NN-joke-name/` | One folder per Short |
| `NN-.../basic-content.txt` | The joke as given, in Roman-script Hindi |
| `NN-.../captions.txt` | Caption cards, `name|text` with `\n` for a line break (Devanagari) |
| `NN-.../make_captions.ps1` | Renders the caption cards to `captions/*.png` |
| `NN-.../make_vertical_clip.py` | Shared framing helpers (4:5 window, backdrop, channel label) |
| `NN-.../make_short_lipsync.py` | Assembles the final Short; edit `BEATS` per video |
| `NN-.../upload-details.md` | Title, description and tags used for the upload |
| `shared/characters/` | Reference pictures of the recurring characters |
| `shared/audio/laughter.mp3` | The laugh track used at the end of every Short |
| `channel-art/make_banner.py` | Builds the 2560x1440 banner from a family picture |

Folders each script expects next to it, all untracked: `characters/` (chosen
scene images), `characters/options/` (all variations), `audio/` (`line1.mp3`,
... and `laughter.mp3`), `audio/takes/`, `lipsync/` (`<clip>-raw.mp4`),
`captions/`.

The newest folders (`08`, `09`) have the current version of the scripts. Start a
new Short by copying the three scripts from the latest folder.

## Format

- 1080x1920, 25 fps, H.264 + AAC mono 44.1 kHz.
- The scene sits in a 4:5 window (1080x1350 at y=330) over a blurred, darkened
  copy of itself, with "Jokes Apart" in yellow above it.
- Captions are 1080x300 cards placed at the bottom of the window.
- Order: 1 s silent lead-in on the first scene, one clip per line, a still
  reaction shot with a slow push-in, 0.6 s of silence, laughter, fade out.

## Cast

| Character | Look | Reference | Voice |
|---|---|---|---|
| Sameer | Neat hair, moustache, cream shirt | `shared/characters/sameer-cream-shirt.png` | Shivam Hindi Youtube |
| The channel's logo man | Messy hair, moustache, stubble, blue checked shirt | `shared/characters/man-blue-checked-shirt.png` | Shivam as the husband (09), Ketan M as a customer (08) |
| Wife | Hair in a bun, red bindi, magenta saree with gold border | `shared/characters/wife-magenta-saree.png` | Shreya G |
| Son and daughter | Yellow t-shirt; two plaits and blue frock | `shared/characters/family-son-husband-wife-daughter.png` | none yet |

Sameer played the lead in shorts 03, 04 and 08. The logo man is the husband in
short 09 and on the channel banner.

## Producing a new Short

Everything generated comes from ElevenLabs (image, speech and lip-sync models),
driven here through its MCP connector in Claude Code. One flow per Short keeps
the pieces connectable.

1. **Text.** Write the lines in Devanagari. Put the joke in `basic-content.txt`.
2. **Voices.** Model `eleven_v4`, two takes per line, with a direction tag in
   front, for example `[surprised, puzzled] अरे! ...`. Voice ids:
   - Shreya G (wife): `RwXLkVKnRloV1UPh3Ccx`
   - Shivam Hindi Youtube (Sameer, husband): `nzAfMLWbcsRz3lvui57b`
   - Ketan M (second man): `MSlUbyNmvjNnEAQL1ZAo`
3. **Scene images.** Model `gpt-image-2.5-sunburst`, quality high, aspect 4:5,
   resolution 1K (832x1040), with the character's reference picture connected.
   One image per speaker, plus a reaction still for the ending.
4. **Lip-sync.** Model `bytedance-omnihuman-v1.5` at 1080p, one clip per line,
   fed the chosen image and the chosen voice take.
5. **Captions.** Fill `captions.txt`, then
   `powershell -ExecutionPolicy Bypass -File make_captions.ps1`.
6. **Assemble.** Edit `BEATS`, the reaction still and the output name in
   `make_short_lipsync.py`, then
   `uv run --system-certs --no-project --python 3.12 --with av --with pillow --with numpy python make_short_lipsync.py`.
7. **Check.** Pull a few frames from the result and look at them; listen to it
   once.

## Things learned the hard way

- **One person per talking shot.** The lip-sync model moves every face in the
  picture. If a listener must be in shot, hold them still with a `FREEZE`
  polygon (short 07).
- **The lip-sync model changes details.** In short 09 it made a small cut pour
  blood. The fix was freezing everything below the chin to the first frame.
- **Lip-sync output is 3:4, not 4:5.** The model trims the sides of a 4:5
  picture and returns 1248x1664. `to_window()` trims the height back to 4:5.
  Keep important things away from the left and right edges of scene images.
- **Keep the bottom fifth of a scene empty.** The caption covers it.
- **Image edits default to 16:9.** Set aspect 4:5 on the node when making a
  reaction still from an existing scene.
- **No writing in images.** Ask for plain labels with a drawing; generated
  lettering comes out garbled.
- **Caption timing.** For a long line, use several cards and switch them in the
  pauses between phrases, so a punchline is not on screen before it is said.
- **Devanagari needs Windows text rendering.** The captions are drawn with
  GDI+ and the Nirmala UI font because Pillow does not shape Devanagari
  correctly.

## Rough cost per Short (ElevenLabs credits)

| Item | Cost |
|---|---|
| Voice line, per take | 50 to 120 |
| Scene image, 4:5 1K high | about 500 each |
| Lip-sync at 1080p | about 950 per second of speech |
| A whole three-line Short | 13,000 to 15,000 |

Lip-sync is most of the bill. Two image variations per scene are enough.

## Upload details

Titles, descriptions and tags are written in Roman-script Hindi, not
Devanagari. Category Comedy, language Hindi, not made for kids, and altered
content marked Yes because the voices and visuals are AI-generated.

The channel description is in `channel-art/channel-description.md`.

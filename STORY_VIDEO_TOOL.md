# Story Video Tool

A local automation tool for page-based dubbed story videos.

## What it does now

- Generates a story outline from a title and synopsis
- Breaks the story into pages
- Writes narration, dialogue, illustration descriptions, and image prompts
- Creates page images
- Creates per-page voice narration and dialogue audio
- Generates an `ffmpeg` assembly script for final MP4 rendering
- Generates a `storyboard.html` preview

## Built-in providers

### TTS

- `silent` - placeholder WAV files
- `edge` - real TTS via Edge voices using `.venv-story/bin/edge-tts`
- `command` - your own adapter command

### Images

- `placeholder` - generated text placeholder images
- `pollinations` - real generated images via Pollinations
- `command` - your own adapter command

## Quick start with real assets

```bash
python3 story_video_tool.py new \
  --title "The Clockmaker's Reef" \
  --synopsis "A young diver discovers a broken machine city under the sea and must restart it before the tide erases its memory." \
  --pages 8 \
  --characters "Mira,Otto,The Drowned Warden" \
  --real-assets
```

Then inspect:

- `story_video_projects/<slug>/story.md`
- `story_video_projects/<slug>/storyboard.html`
- `story_video_projects/<slug>/manifests/story.json`
- `story_video_projects/<slug>/render/assemble.sh`

To render the final video:

```bash
bash story_video_projects/<slug>/render/assemble.sh
```

Output:

- `story_video_projects/<slug>/render/final-story.mp4`

## Config file

Copy `story_video_config.example.yaml` and customize providers or voice defaults.

## Validation

```bash
python3 story_video_tool.py validate story_video_projects/<slug>
```

## Notes

- The built-in real-asset path depends on network access.
- Pollinations image output quality and consistency can vary.
- Edge TTS uses a narrator voice plus deterministic character voice assignment.

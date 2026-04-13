# story-video-tool

Automation for page-based voice dubbed story videos.

## Features

- story outline generation from title + synopsis
- page-by-page narration, dialogue, and illustration descriptions
- image prompt generation
- optional real TTS via Edge voices
- optional real image generation via Pollinations
- placeholder fallback mode when providers fail
- ffmpeg-based final MP4 assembly
- storyboard HTML preview

## Install

### System packages

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3-pip python3.12-venv
```

### Python environment

```bash
python3 -m venv .venv-story
./.venv-story/bin/python -m pip install edge-tts
```

## Usage

### Basic scaffold

```bash
python3 story_video_tool.py new \
  --title "The Clockmaker's Reef" \
  --synopsis "A young diver discovers a broken machine city under the sea and must restart it before the tide erases its memory." \
  --pages 8 \
  --characters "Mira,Otto,The Drowned Warden"
```

### Real assets

```bash
python3 story_video_tool.py new \
  --title "The Clockmaker's Reef" \
  --synopsis "A young diver discovers a broken machine city under the sea and must restart it before the tide erases its memory." \
  --pages 8 \
  --characters "Mira,Otto,The Drowned Warden" \
  --real-assets
```

### Render final video

```bash
bash story_video_projects/<slug>/render/assemble.sh
```

## Notes

- `--real-assets` uses Edge TTS and Pollinations.
- Remote providers can be slow or flaky, so the tool keeps fallback behavior.
- The generated project includes manifests, audio files, images, page data, and a storyboard preview.
- Audio and image manifests record which provider actually produced each asset.
- Real TTS page audio can be much longer than the nominal page duration, so the renderer now follows the audio length instead of truncating it.

## Smoke tests

```bash
python3 run_smoke_tests.py
```

This exercises multiple placeholder-mode stories plus one real-assets story and writes `qa_report.json`.

## Repo files

- `story_video_tool.py`
- `story_video_config.example.yaml`
- `STORY_VIDEO_TOOL.md`

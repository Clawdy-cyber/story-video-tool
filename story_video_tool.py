#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import time
import re
import shlex
import subprocess
import textwrap
import urllib.parse
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont


DEFAULT_CONFIG = {
    "video": {
        "pageDurationSeconds": 6.0,
        "width": 1280,
        "height": 720,
        "fps": 24,
    },
    "providers": {
        "ttsProvider": "silent",
        "imageProvider": "placeholder",
        "ttsCommand": None,
        "imageCommand": None,
        "ffmpegCommand": "ffmpeg",
        "edgeTtsBinary": ".venv-story/bin/edge-tts",
        "pollinationsModel": "flux",
    },
    "voices": {
        "narrator": "en-US-AvaMultilingualNeural",
        "fallbackCycle": [
            "en-US-AvaMultilingualNeural",
            "en-US-BrianMultilingualNeural",
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
            "en-AU-NatashaNeural",
            "en-AU-WilliamNeural",
        ],
    },
    "render": {
        "createPlaceholderImages": True,
        "createSilenceAudio": True,
        "allowAssembleWithoutAudio": False,
    },
}


@dataclass
class StoryPage:
    page_number: int
    title: str
    narration: str
    dialogue: list[dict[str, str]]
    illustration_description: str
    image_prompt: str
    mood: str
    camera: str
    duration_seconds: float


@dataclass
class StoryProject:
    title: str
    slug: str
    logline: str
    tone: str
    audience: str
    total_pages: int
    pages: list[StoryPage]


ACT_BEATS = [
    "setup",
    "inciting incident",
    "first challenge",
    "escalation",
    "midpoint turn",
    "setback",
    "deepest doubt",
    "final push",
    "resolution",
]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "story"


def load_config(path: Path | None) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and path.exists():
        user = yaml.safe_load(path.read_text()) or {}
        deep_merge(config, user)
    return config


def deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def split_characters(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def generate_story(
    title: str,
    synopsis: str,
    pages: int,
    characters: list[str],
    tone: str,
    audience: str,
    page_duration: float,
) -> StoryProject:
    pages = max(3, pages)
    slug = slugify(title)
    beats = build_beats(pages)
    protagonist = characters[0] if characters else "the young explorer"
    sidekick = characters[1] if len(characters) > 1 else "a cautious friend"
    antagonist = characters[2] if len(characters) > 2 else "the hidden obstacle"

    story_pages: list[StoryPage] = []
    for index in range(1, pages + 1):
        beat = beats[index - 1]
        page_title = make_page_title(index, beat)
        narration = make_narration(index, pages, beat, synopsis, protagonist, sidekick, antagonist, tone)
        dialogue = make_dialogue(index, pages, beat, protagonist, sidekick, antagonist)
        illustration = make_illustration(index, pages, beat, protagonist, sidekick, antagonist, synopsis, tone)
        prompt = make_image_prompt(title, page_title, illustration, tone, audience)
        mood = mood_for_beat(beat)
        camera = camera_for_beat(beat)
        story_pages.append(
            StoryPage(
                page_number=index,
                title=page_title,
                narration=narration,
                dialogue=dialogue,
                illustration_description=illustration,
                image_prompt=prompt,
                mood=mood,
                camera=camera,
                duration_seconds=page_duration,
            )
        )

    return StoryProject(
        title=title,
        slug=slug,
        logline=synopsis.strip(),
        tone=tone,
        audience=audience,
        total_pages=pages,
        pages=story_pages,
    )


def build_beats(page_count: int) -> list[str]:
    beats = []
    for i in range(page_count):
        ratio = i / max(1, page_count - 1)
        idx = min(len(ACT_BEATS) - 1, round(ratio * (len(ACT_BEATS) - 1)))
        beats.append(ACT_BEATS[idx])
    return beats


def make_page_title(page_number: int, beat: str) -> str:
    return f"Page {page_number}: {beat.title()}"


def make_narration(index: int, total: int, beat: str, synopsis: str, protagonist: str, sidekick: str, antagonist: str, tone: str) -> str:
    base = synopsis.strip().rstrip(".")
    line_map = {
        "setup": f"In a {tone} beginning, {protagonist} steps into the world of {base}. The day feels ordinary, but a quiet promise of change hangs in the air.",
        "inciting incident": f"Everything shifts when {protagonist} notices the first sign that the world of {base} is no longer safe to ignore. One choice now matters.",
        "first challenge": f"The path forward tests {protagonist}, and even with {sidekick} nearby, the first obstacle bites harder than expected.",
        "escalation": f"What began as a single problem grows wider. Each step deeper into {base} exposes new stakes and less room to turn back.",
        "midpoint turn": f"At the story's turning point, {protagonist} discovers a truth that changes the meaning of the journey. The mission becomes personal.",
        "setback": f"Just when progress seems possible, {antagonist} forces a setback. Confidence cracks, and the cost of failure becomes visible.",
        "deepest doubt": f"For a moment, {protagonist} nearly gives up. In the silence after the setback, fear speaks louder than hope.",
        "final push": f"Then resolve returns. With a clearer heart and sharper purpose, {protagonist} makes the final push through the heart of {base}.",
        "resolution": f"By the end, {protagonist} sees the world differently. The journey through {base} leaves behind a hard-won, lasting change.",
    }
    return line_map.get(beat, f"{protagonist} advances the story one meaningful step at a time.")


def make_dialogue(index: int, total: int, beat: str, protagonist: str, sidekick: str, antagonist: str) -> list[dict[str, str]]:
    if beat in {"setup", "resolution"}:
        return [
            {"speaker": protagonist, "text": "I can feel this story is about to change me."},
            {"speaker": sidekick, "text": "Then let us pay attention to what matters."},
        ]
    if beat in {"inciting incident", "first challenge", "escalation"}:
        return [
            {"speaker": protagonist, "text": "We do not have the luxury of waiting."},
            {"speaker": sidekick, "text": "Then we move carefully, but we move now."},
        ]
    if beat in {"setback", "deepest doubt"}:
        return [
            {"speaker": antagonist, "text": "You came this far only to discover you were never ready."},
            {"speaker": protagonist, "text": "Maybe I was not ready then. I am ready now."},
        ]
    return [
        {"speaker": protagonist, "text": "This is the moment that decides who I become."},
        {"speaker": sidekick, "text": "Then let us meet it properly."},
    ]


def make_illustration(index: int, total: int, beat: str, protagonist: str, sidekick: str, antagonist: str, synopsis: str, tone: str) -> str:
    details = {
        "setup": f"A wide cinematic establishing shot of {protagonist} in the world of {synopsis}, with subtle details that foreshadow danger.",
        "inciting incident": f"A dramatic discovery scene where {protagonist} notices the first rupture in normal life, with tense lighting and focused composition.",
        "first challenge": f"{protagonist} and {sidekick} face the first obstacle together, shown with motion, scale, and environmental texture.",
        "escalation": f"The environment grows more threatening as {protagonist} pushes deeper, with layered depth and rising visual stakes.",
        "midpoint turn": f"A revelatory image with symbolic composition, showing {protagonist} realizing the deeper truth behind the journey.",
        "setback": f"A low point image where {antagonist} dominates the frame, and {protagonist} appears small but not broken.",
        "deepest doubt": f"A quiet, intimate close shot of {protagonist} in reflection, with negative space and emotionally weighted lighting.",
        "final push": f"A kinetic heroic image of {protagonist} surging forward with renewed purpose, framed for maximum momentum.",
        "resolution": f"A warm concluding tableau showing the transformed world and the changed posture of {protagonist}.",
    }
    return details.get(beat, f"Illustrate {protagonist} inside the central conflict of {synopsis}.")


def make_image_prompt(title: str, page_title: str, illustration: str, tone: str, audience: str) -> str:
    return (
        f"Illustration for the story '{title}', {page_title}. "
        f"{illustration} Tone: {tone}. Audience: {audience}. "
        "High-detail storybook cinematic art, coherent character design, readable silhouette, rich environment storytelling, no text overlays."
    )


def mood_for_beat(beat: str) -> str:
    return {
        "setup": "curious",
        "inciting incident": "uneasy",
        "first challenge": "tense",
        "escalation": "urgent",
        "midpoint turn": "awed",
        "setback": "grim",
        "deepest doubt": "somber",
        "final push": "heroic",
        "resolution": "hopeful",
    }.get(beat, "focused")


def camera_for_beat(beat: str) -> str:
    return {
        "setup": "wide establishing shot",
        "inciting incident": "medium dramatic shot",
        "first challenge": "dynamic action frame",
        "escalation": "wide layered environment shot",
        "midpoint turn": "centered reveal composition",
        "setback": "low angle pressure shot",
        "deepest doubt": "close intimate portrait",
        "final push": "dynamic forward tracking shot",
        "resolution": "wide closing tableau",
    }.get(beat, "medium shot")


def ensure_dirs(base: Path) -> dict[str, Path]:
    paths = {
        "base": base,
        "images": base / "images",
        "audio": base / "audio",
        "pages": base / "pages",
        "manifests": base / "manifests",
        "render": base / "render",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def write_story_files(project: StoryProject, base: Path) -> None:
    paths = ensure_dirs(base)
    story_json = {
        "title": project.title,
        "slug": project.slug,
        "logline": project.logline,
        "tone": project.tone,
        "audience": project.audience,
        "total_pages": project.total_pages,
        "pages": [asdict(page) for page in project.pages],
    }
    (paths["manifests"] / "story.json").write_text(json.dumps(story_json, indent=2, ensure_ascii=False) + "\n")

    md_lines = [f"# {project.title}", "", f"- Logline: {project.logline}", f"- Tone: {project.tone}", f"- Audience: {project.audience}", ""]
    for page in project.pages:
        page_md = textwrap.dedent(
            f"""
            ## {page.title}
            - Mood: {page.mood}
            - Camera: {page.camera}
            - Duration: {page.duration_seconds:.1f}s

            **Narration**
            {page.narration}

            **Dialogue**
            {os.linesep.join(f'- {d["speaker"]}: {d["text"]}' for d in page.dialogue)}

            **Illustration description**
            {page.illustration_description}

            **Image prompt**
            {page.image_prompt}
            """
        ).strip()
        md_lines.append(page_md)
        md_lines.append("")
        (paths["pages"] / f"page-{page.page_number:02d}.txt").write_text(
            json.dumps(asdict(page), indent=2, ensure_ascii=False) + "\n"
        )
    (paths["base"] / "story.md").write_text("\n".join(md_lines).strip() + "\n")


def maybe_make_placeholder_images(project: StoryProject, base: Path, config: dict[str, Any]) -> None:
    if not config["render"].get("createPlaceholderImages", True):
        return
    width = int(config["video"].get("width", 1280))
    height = int(config["video"].get("height", 720))
    font = ImageFont.load_default()
    image_dir = base / "images"
    for page in project.pages:
        image = Image.new("RGB", (width, height), color=(24, 28, 36))
        draw = ImageDraw.Draw(image)
        margin = 60
        title = page.title
        body = textwrap.fill(page.illustration_description, width=55)
        prompt = textwrap.fill(page.image_prompt, width=65)
        draw.rectangle((margin - 20, margin - 20, width - margin + 20, height - margin + 20), outline=(110, 150, 220), width=3)
        draw.text((margin, margin), title, fill=(235, 240, 255), font=font)
        draw.text((margin, margin + 40), body, fill=(220, 225, 235), font=font)
        draw.text((margin, height - 220), "Prompt:", fill=(190, 210, 255), font=font)
        draw.text((margin, height - 190), prompt, fill=(170, 185, 210), font=font)
        out = image_dir / f"page-{page.page_number:02d}.png"
        image.save(out)


def synthesize_audio(project: StoryProject, base: Path, config: dict[str, Any]) -> None:
    audio_dir = base / "audio"
    ffmpeg_cmd = config["providers"].get("ffmpegCommand", "ffmpeg")
    tts_command = config["providers"].get("ttsCommand")
    tts_provider = config["providers"].get("ttsProvider", "silent")
    create_silence = config["render"].get("createSilenceAudio", True)
    manifest = []
    for page in project.pages:
        segments = build_tts_segments(page)
        script_text = "\n".join(f"[{segment['speaker']}] {segment['text']}" for segment in segments)
        text_path = audio_dir / f"page-{page.page_number:02d}.txt"
        wav_path = audio_dir / f"page-{page.page_number:02d}.wav"
        text_path.write_text(script_text + "\n")
        audio_status = "placeholder"
        if tts_provider == "edge":
            try:
                synthesize_with_edge_tts(page, segments, wav_path, ffmpeg_cmd, config)
                audio_status = "edge"
            except Exception as exc:
                if create_silence:
                    create_silent_wav(wav_path, page.duration_seconds)
                    audio_status = f"placeholder_after_error: {exc}"
                else:
                    raise RuntimeError(f"Edge TTS failed for page {page.page_number}: {exc}") from exc
        elif tts_provider == "command" and tts_command:
            run_provider_command(tts_command, page, script_text, wav_path)
            audio_status = "command"
        elif create_silence:
            create_silent_wav(wav_path, page.duration_seconds)
        manifest.append({
            "page": page.page_number,
            "text_file": str(text_path),
            "audio_file": str(wav_path),
            "seconds": wav_duration_seconds(wav_path),
            "audio_status": audio_status,
        })
    (base / "manifests" / "audio_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def generate_image_assets(project: StoryProject, base: Path, config: dict[str, Any]) -> None:
    image_command = config["providers"].get("imageCommand")
    image_provider = config["providers"].get("imageProvider", "placeholder")
    manifest = []
    for page in project.pages:
        image_path = base / "images" / f"page-{page.page_number:02d}.png"
        image_status = "placeholder"
        if image_provider == "pollinations":
            try:
                generate_with_pollinations(page, image_path, config)
                image_status = "pollinations"
            except Exception as exc:
                image_status = f"placeholder_after_error: {exc}"
        elif image_provider == "command" and image_command:
            run_provider_command(image_command, page, page.image_prompt, image_path)
            image_status = "command"
        manifest.append({
            "page": page.page_number,
            "image_file": str(image_path),
            "prompt": page.image_prompt,
            "image_status": image_status,
        })
    (base / "manifests" / "image_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def run_provider_command(template: str, page: StoryPage, payload: str, output_path: Path) -> None:
    context = {
        "page": str(page.page_number),
        "title": page.title,
        "mood": page.mood,
        "camera": page.camera,
        "payload": payload,
        "output": str(output_path),
    }
    command = template.format(**context)
    subprocess.run(command, shell=True, check=True)


def create_silent_wav(path: Path, seconds: float, sample_rate: int = 24000) -> None:
    total_frames = max(1, int(seconds * sample_rate))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * total_frames)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
    return frames / rate if rate else 0.0


def build_tts_segments(page: StoryPage) -> list[dict[str, str]]:
    parts = [{"speaker": "Narrator", "text": page.narration}]
    for line in page.dialogue:
        parts.append({"speaker": line["speaker"], "text": line["text"]})
    return parts


def synthesize_with_edge_tts(
    page: StoryPage,
    segments: list[dict[str, str]],
    output_path: Path,
    ffmpeg_cmd: str,
    config: dict[str, Any],
) -> None:
    edge_bin = resolve_edge_tts_binary(config)
    if not edge_bin.exists():
        raise FileNotFoundError(f"edge-tts binary not found at {edge_bin}")

    temp_dir = output_path.parent / f"tmp-page-{page.page_number:02d}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    concat_lines = []
    for idx, segment in enumerate(segments, start=1):
        mp3_path = temp_dir / f"segment-{idx:02d}.mp3"
        voice = choose_voice(segment["speaker"], config)
        subprocess.run(
            [
                str(edge_bin),
                "--voice",
                voice,
                "--text",
                segment["text"],
                "--write-media",
                str(mp3_path),
            ],
            check=True,
        )
        concat_lines.append(f"file '{mp3_path.resolve()}'")
    concat_path = temp_dir / "concat.txt"
    concat_path.write_text("\n".join(concat_lines) + "\n")
    subprocess.run(
        [
            ffmpeg_cmd,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-ar",
            "24000",
            str(output_path),
        ],
        check=True,
    )


def choose_voice(speaker: str, config: dict[str, Any]) -> str:
    if speaker == "Narrator":
        return config.get("voices", {}).get("narrator", "en-US-AvaMultilingualNeural")
    cycle = config.get("voices", {}).get("fallbackCycle", []) or ["en-US-BrianMultilingualNeural"]
    idx = sum(ord(ch) for ch in speaker) % len(cycle)
    return cycle[idx]


def resolve_edge_tts_binary(config: dict[str, Any]) -> Path:
    configured = config["providers"].get("edgeTtsBinary", ".venv-story/bin/edge-tts")
    candidate = Path(configured)
    search_paths = []
    if candidate.is_absolute():
        search_paths.append(candidate)
    else:
        cwd = Path.cwd()
        here = Path(__file__).resolve().parent
        search_paths.extend([
            cwd / candidate,
            here / candidate,
            here.parent / candidate,
            cwd.parent / candidate,
        ])
    for path in search_paths:
        if path.exists():
            return path
    return candidate


def generate_with_pollinations(page: StoryPage, image_path: Path, config: dict[str, Any]) -> None:
    model = config["providers"].get("pollinationsModel", "flux")
    width = int(config["video"].get("width", 1280))
    height = int(config["video"].get("height", 720))
    seed = 1000 + page.page_number
    encoded = urllib.parse.quote(page.image_prompt, safe="")
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model={urllib.parse.quote(str(model), safe='')}&seed={seed}"
    )
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            with Image.open(io.BytesIO(response.content)) as image:
                image = image.convert("RGB")
                image = image.resize((width, height))
                image.save(image_path, format="PNG")
            return
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Pollinations image generation failed after retries: {last_error}")


def write_render_script(project: StoryProject, base: Path, config: dict[str, Any]) -> None:
    render_dir = base / "render"
    ffmpeg_cmd = config["providers"].get("ffmpegCommand", "ffmpeg")
    width = int(config["video"].get("width", 1280))
    height = int(config["video"].get("height", 720))
    fps = int(config["video"].get("fps", 24))
    root_var = "$" + "ROOT"
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'ROOT=$(cd "$(dirname "$0")/.." && pwd)',
        f'mkdir -p "{root_var}/render/clips"',
    ]
    concat_entries = []
    for page in project.pages:
        image_rel = f"{root_var}/images/page-{page.page_number:02d}.png"
        audio_rel = f"{root_var}/audio/page-{page.page_number:02d}.wav"
        clip_rel = f"{root_var}/render/clips/page-{page.page_number:02d}.mp4"
        lines.append(
            f"{shlex.quote(ffmpeg_cmd)} -y -loop 1 -i \"{image_rel}\" -i \"{audio_rel}\" -c:v libx264 -vf \"scale={width}:{height},fps={fps}\" -pix_fmt yuv420p -c:a aac -shortest \"{clip_rel}\""
        )
        concat_entries.append(f"file 'clips/page-{page.page_number:02d}.mp4'")
    concat_path = render_dir / "concat.txt"
    concat_path.write_text("\n".join(concat_entries) + "\n")
    lines.append(f'cd "{root_var}/render"')
    lines.append(
        f"{shlex.quote(ffmpeg_cmd)} -y -f concat -safe 0 -i concat.txt -c:v libx264 -c:a aac -pix_fmt yuv420p final-story.mp4"
    )
    script_path = render_dir / "assemble.sh"
    script_path.write_text("\n".join(lines) + "\n")
    script_path.chmod(0o755)


def write_html_preview(project: StoryProject, base: Path) -> None:
    slides = []
    for page in project.pages:
        img = f"images/page-{page.page_number:02d}.png"
        slides.append(
            f"<section class='slide'><img src='{img}' alt='page {page.page_number}'/><div class='card'><h2>{escape_html(page.title)}</h2><p>{escape_html(page.narration)}</p></div></section>"
        )
    html = f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width, initial-scale=1'/>
<title>{escape_html(project.title)} storyboard</title>
<style>
body {{ background:#0f1115; color:#eef2ff; font-family: Arial, sans-serif; margin:0; }}
header {{ padding:24px 28px; border-bottom:1px solid #263043; }}
main {{ display:grid; gap:20px; padding:24px; }}
.slide {{ background:#171c26; border:1px solid #263043; border-radius:16px; overflow:hidden; }}
img {{ width:100%; display:block; background:#0b0d12; }}
.card {{ padding:18px; }}
h1, h2, p {{ margin:0 0 10px 0; }}
</style>
</head>
<body>
<header><h1>{escape_html(project.title)}</h1><p>{escape_html(project.logline)}</p></header>
<main>{''.join(slides)}</main>
</body>
</html>
"""
    (base / "storyboard.html").write_text(html)


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def cmd_new(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config) if args.config else None)
    if args.real_assets:
        config["providers"]["ttsProvider"] = "edge"
        config["providers"]["imageProvider"] = "pollinations"
    base_root = Path(args.output_dir or "story_video_projects")
    project = generate_story(
        title=args.title,
        synopsis=args.synopsis,
        pages=args.pages,
        characters=split_characters(args.characters),
        tone=args.tone,
        audience=args.audience,
        page_duration=float(config["video"].get("pageDurationSeconds", 6.0)),
    )
    project_dir = base_root / project.slug
    write_story_files(project, project_dir)
    maybe_make_placeholder_images(project, project_dir, config)
    synthesize_audio(project, project_dir, config)
    generate_image_assets(project, project_dir, config)
    write_render_script(project, project_dir, config)
    write_html_preview(project, project_dir)
    audio_manifest_path = project_dir / "manifests" / "audio_manifest.json"
    image_manifest_path = project_dir / "manifests" / "image_manifest.json"
    audio_manifest = json.loads(audio_manifest_path.read_text())
    image_manifest = json.loads(image_manifest_path.read_text())
    summary = {
        "project": project.title,
        "slug": project.slug,
        "project_dir": str(project_dir.resolve()),
        "story_manifest": str((project_dir / "manifests" / "story.json").resolve()),
        "audio_manifest": str(audio_manifest_path.resolve()),
        "image_manifest": str(image_manifest_path.resolve()),
        "assemble_script": str((project_dir / "render" / "assemble.sh").resolve()),
        "storyboard_html": str((project_dir / "storyboard.html").resolve()),
        "tts_provider": config["providers"].get("ttsProvider"),
        "image_provider": config["providers"].get("imageProvider"),
        "audio_statuses": [item.get("audio_status") for item in audio_manifest],
        "image_statuses": [item.get("image_status") for item in image_manifest],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir)
    required = [
        project_dir / "manifests" / "story.json",
        project_dir / "manifests" / "audio_manifest.json",
        project_dir / "manifests" / "image_manifest.json",
        project_dir / "render" / "assemble.sh",
    ]
    missing = [str(path) for path in required if not path.exists()]
    ok = not missing
    print(json.dumps({"ok": ok, "missing": missing}, indent=2))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a page-based dubbed story video project.")
    sub = parser.add_subparsers(dest="command", required=True)

    new_cmd = sub.add_parser("new", help="Create a new story project scaffold")
    new_cmd.add_argument("--title", required=True)
    new_cmd.add_argument("--synopsis", required=True)
    new_cmd.add_argument("--pages", type=int, default=8)
    new_cmd.add_argument("--characters", default="")
    new_cmd.add_argument("--tone", default="cinematic and emotionally clear")
    new_cmd.add_argument("--audience", default="general")
    new_cmd.add_argument("--config")
    new_cmd.add_argument("--output-dir")
    new_cmd.add_argument("--real-assets", action="store_true", help="Use built-in Edge TTS and Pollinations image generation")
    new_cmd.set_defaults(func=cmd_new)

    validate_cmd = sub.add_parser("validate", help="Check that required project files exist")
    validate_cmd.add_argument("project_dir")
    validate_cmd.set_defaults(func=cmd_validate)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

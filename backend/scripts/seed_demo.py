"""Create a polished demo project by running the real pipeline end to end.

Nothing here is faked: it generates a narrated sample video, then drives the same
services the app uses (ffmpeg -> transcription -> Content DNA -> best moments ->
shorts -> campaign -> thumbnails -> evaluation).

Usage (from backend/, venv active):
    python scripts/seed_demo.py
    python scripts/seed_demo.py --video path/to/your.mp4
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import UPLOADS_DIR, settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine, ensure_schema  # noqa: E402
from app.models.project import Project, ProjectStatus  # noqa: E402
from app.schemas.campaign import Campaign  # noqa: E402
from app.schemas.content_dna import ContentDNA  # noqa: E402
from app.schemas.moment import BestMoment, Clip  # noqa: E402
from app.services.analysis_service import get_analysis_service  # noqa: E402
from app.services.clip_service import generate_clip  # noqa: E402
from app.services.evaluation_service import evaluate_campaign  # noqa: E402
from app.services.media_service import extract_metadata  # noqa: E402
from app.services.pipeline_service import run_analysis, run_moment_detection, run_pipeline  # noqa: E402
from app.services.platform_service import generate_campaign, score_campaign  # noqa: E402
from app.services.thumbnail_service import generate_thumbnail_concepts  # noqa: E402
from app.services.upload_service import new_project_id  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"
SAMPLE_VIDEO = SAMPLE_DIR / "demo_source.mp4"

NARRATION = (
    "Welcome back to the channel. Today we are talking about how to turn one "
    "video into an entire social media campaign. Here is the problem. Most "
    "creators spend six to eight hours every single week repurposing one video. "
    "They cut clips by hand, they write captions from scratch, and they rewrite "
    "everything again for each platform. That is an entire working day gone. And "
    "here is the part that really hurts. Most of that work gets almost no "
    "engagement, because the wrong moments get clipped. The single biggest "
    "mistake creators make is clipping the introduction instead of the payoff. "
    "Nobody wants to watch you say hello. They want the insight. So what is the "
    "fix? You need to find the moments where you deliver actual value, and you "
    "need to lead with the strongest line. Our tool analyzes your video, scores "
    "every possible segment, and picks the three to five moments that work as "
    "standalone shorts. It then generates the caption, the hook, and the SEO "
    "keywords for every platform automatically. One upload becomes a full "
    "campaign in under a minute. If that sounds useful, subscribe for more "
    "creator workflow breakdowns."
)


def log(step: str, detail: str = "") -> None:
    print(f"  {step:<28} {detail}", flush=True)


def build_sample_video() -> Path:
    """Render a narrated 1280x720 sample using Windows TTS + ffmpeg."""
    if SAMPLE_VIDEO.exists():
        log("sample video", f"reusing {SAMPLE_VIDEO.name}")
        return SAMPLE_VIDEO

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    wav = SAMPLE_DIR / "_narration.wav"

    escaped = NARRATION.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('{escaped}'); $s.Dispose()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            "Could not synthesise narration (Windows TTS unavailable).\n"
            "Pass your own file instead:  python scripts/seed_demo.py --video my.mp4"
        ) from exc

    subprocess.run(
        [
            settings.ffmpeg_bin, "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
            "-i", str(wav),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(SAMPLE_VIDEO),
        ],
        check=True, capture_output=True,
    )
    wav.unlink(missing_ok=True)
    log("sample video", f"created {SAMPLE_VIDEO.name}")
    return SAMPLE_VIDEO


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a RECAST demo project.")
    parser.add_argument("--video", type=Path, help="Use this video instead of the generated sample")
    parser.add_argument("--title", default="How to Repurpose One Video Into a Full Campaign")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    ensure_schema()

    source = args.video if args.video else build_sample_video()
    if not source.exists():
        raise SystemExit(f"Video not found: {source}")

    started = time.perf_counter()
    print(f"\nSeeding demo project from {source.name}\n")

    project_id = new_project_id()
    dest = UPLOADS_DIR / f"{project_id}{source.suffix.lower()}"
    shutil.copy(source, dest)
    meta = extract_metadata(dest)

    db = SessionLocal()
    try:
        db.add(
            Project(
                id=project_id,
                title=args.title,
                status=ProjectStatus.UPLOADED,
                video_path=str(dest),
                video_filename=source.name,
                duration_seconds=meta.duration_seconds,
                video_width=meta.width,
                video_height=meta.height,
                video_fps=meta.fps,
                video_size_bytes=meta.size_bytes,
            )
        )
        db.commit()
    finally:
        db.close()
    log("uploaded", f"{meta.width}x{meta.height}, {meta.duration_seconds:.0f}s")

    run_pipeline(project_id)
    run_analysis(project_id)
    run_moment_detection(project_id)

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project.best_moments_json:
            raise SystemExit(f"Pipeline stopped early: {project.error_message}")

        transcript = json.loads(project.transcript_json)
        dna = ContentDNA.model_validate_json(project.content_dna_json)
        moments = [BestMoment.model_validate(m) for m in json.loads(project.best_moments_json)]
        log("transcript", f"{len(transcript['segments'])} segments")
        log("content DNA", dna.primary_topic)
        log("best moments", f"{len(moments)} selected")

        # Shorts
        clips: list[Clip] = []
        for moment in moments:
            generated = generate_clip(
                Path(project.video_path), moment.start, moment.end,
                f"{project.id}_{moment.id}",
            )
            clips.append(
                Clip(
                    clip_id=generated.clip_id, moment_id=moment.id,
                    video_url=f"/media/clips/{generated.video_path.name}",
                    thumbnail_url=f"/media/thumbnails/{generated.thumbnail_path.name}",
                    title=moment.title, hook=moment.hook, score=moment.score,
                    start=generated.start, end=generated.end, duration=generated.duration,
                    width=generated.width, height=generated.height, vertical=generated.vertical,
                )
            )
        project.clips_json = json.dumps([c.model_dump() for c in clips])
        db.commit()
        log("shorts", f"{len(clips)} vertical clips rendered")

        # Campaign
        service = get_analysis_service()
        campaign, failed = generate_campaign(
            dna=dna, moments=moments,
            transcript_excerpt=transcript.get("text", ""), service=service,
        )
        project.platform_content_json = campaign.model_dump_json()
        project.campaign_score = score_campaign(campaign, dna, moments)
        db.commit()
        log("campaign", f"{len(campaign.generated_platforms)} platforms"
            + (f" (failed: {', '.join(failed)})" if failed else ""))

        # Thumbnails (optional)
        try:
            concepts = generate_thumbnail_concepts(
                project_id=project.id, video_path=Path(project.video_path),
                dna=dna, moments=moments, duration=project.duration_seconds, service=service,
            )
            project.thumbnail_concepts_json = json.dumps([c.model_dump() for c in concepts])
            db.commit()
            log("thumbnails", f"{len(concepts)} concepts")
        except Exception as exc:
            log("thumbnails", f"skipped ({exc})")

        # Quality score (optional)
        try:
            evaluation = evaluate_campaign(
                Campaign.model_validate_json(project.platform_content_json), dna, service
            )
            project.campaign_evaluation_json = evaluation.model_dump_json()
            db.commit()
            log("quality score", f"{evaluation.overall}/100")
        except Exception as exc:
            log("quality score", f"skipped ({exc})")

        project.status = ProjectStatus.COMPLETED
        project.error_message = None
        db.commit()
    finally:
        db.close()

    elapsed = time.perf_counter() - started
    print(f"\nDemo project ready in {elapsed:.0f}s")
    print(f"  http://localhost:3000/projects/{project_id}\n")


if __name__ == "__main__":
    main()

import json
import logging
from pathlib import Path

from app.core.database import SessionLocal
from app.models.project import Project, ProjectStatus
from app.schemas.campaign import Campaign
from app.schemas.content_dna import ContentDNA
from app.schemas.moment import BestMoment
from app.services.analysis_service import AnalysisError, get_analysis_service
from app.services.moment_service import detect_moments
from app.services.platform_service import generate_campaign, score_campaign
from app.services.evaluation_service import EvaluationError, evaluate_campaign
from app.services.thumbnail_service import generate_thumbnail_concepts
from app.services.media_service import MediaProcessingError, extract_audio, extract_metadata
from app.services.transcription_service import TranscriptionError, get_transcription_service

logger = logging.getLogger(__name__)


def run_pipeline(project_id: str) -> None:
    """Runs the Phase 2 media pipeline for a project: metadata -> audio -> transcription.

    Executed as a background task with its own DB session. Never marks a stage
    successful unless the underlying ffmpeg/ffprobe/transcription call actually
    succeeded; any failure is recorded on the project with a clear error message.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            logger.error("Pipeline started for unknown project %s", project_id)
            return
        if not project.video_path:
            project.status = ProjectStatus.FAILED
            project.error_message = "No video attached to this project."
            db.commit()
            return

        try:
            video_path = Path(project.video_path)

            project.status = ProjectStatus.PROCESSING
            project.error_message = None
            db.commit()

            metadata = extract_metadata(video_path)
            project.duration_seconds = metadata.duration_seconds
            project.video_width = metadata.width
            project.video_height = metadata.height
            project.video_fps = metadata.fps
            project.video_size_bytes = metadata.size_bytes
            db.commit()

            audio_path = extract_audio(video_path, project.id)
            project.audio_path = str(audio_path)
            db.commit()

            project.status = ProjectStatus.TRANSCRIBING
            db.commit()

            transcription_service = get_transcription_service()
            transcript = transcription_service.transcribe(audio_path)
            project.transcript_json = json.dumps(transcript.to_dict())
            project.status = ProjectStatus.TRANSCRIBED
            db.commit()

            logger.info(
                "Pipeline finished for project %s: metadata + audio + transcript ready "
                "(analysis/generation land in a later phase)",
                project.id,
            )

        except (MediaProcessingError, TranscriptionError) as exc:
            logger.warning("Pipeline failed for project %s: %s", project.id, exc)
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            db.commit()
        except Exception as exc:  # unexpected — still surface, never leave state ambiguous
            logger.exception("Unexpected pipeline error for project %s", project.id)
            project.status = ProjectStatus.FAILED
            project.error_message = f"Unexpected error: {exc}"
            db.commit()
    finally:
        db.close()


def run_analysis(project_id: str) -> None:
    """Builds Content DNA from a project's stored transcript.

    Runs as a background task with its own DB session. Requires a transcript to
    already exist; the analysis backend is never allowed to fabricate results, so
    any failure marks the project failed with an actionable message while the
    transcript and video are preserved for retry.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            logger.error("Analysis started for unknown project %s", project_id)
            return
        if not project.transcript_json:
            project.status = ProjectStatus.FAILED
            project.error_message = "No transcript available. Run processing first."
            db.commit()
            return

        try:
            project.status = ProjectStatus.ANALYZING
            project.error_message = None
            db.commit()

            transcript = json.loads(project.transcript_json)
            service = get_analysis_service()
            dna = service.analyze(
                transcript_text=transcript.get("text", ""),
                segments=transcript.get("segments") or [],
                max_timestamp=project.duration_seconds,
            )

            project.content_dna_json = dna.model_dump_json()
            # Key topics are derived from the DNA so downstream steps share one source.
            project.key_topics_json = json.dumps(
                [dna.primary_topic, *dna.secondary_topics] if dna.primary_topic else dna.secondary_topics
            )
            project.status = ProjectStatus.ANALYZED
            db.commit()

            logger.info(
                "Content DNA ready for project %s (%d key moments, %d keywords)",
                project.id,
                len(dna.key_moments),
                len(dna.keywords),
            )

        except AnalysisError as exc:
            logger.warning("Analysis failed for project %s: %s", project.id, exc)
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            db.commit()
        except Exception as exc:
            logger.exception("Unexpected analysis error for project %s", project.id)
            project.status = ProjectStatus.FAILED
            project.error_message = f"Unexpected error: {exc}"
            db.commit()
    finally:
        db.close()


def run_moment_detection(project_id: str) -> None:
    """Selects the best short-form moments from the transcript + Content DNA.

    Runs as a background task with its own DB session. Timestamps come from real
    transcript segments (see moment_service), never from model output.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            logger.error("Moment detection started for unknown project %s", project_id)
            return
        if not project.transcript_json:
            project.status = ProjectStatus.FAILED
            project.error_message = "No transcript available. Run processing first."
            db.commit()
            return

        try:
            project.status = ProjectStatus.DETECTING_MOMENTS
            project.error_message = None
            db.commit()

            transcript = json.loads(project.transcript_json)
            dna = (
                ContentDNA.model_validate_json(project.content_dna_json)
                if project.content_dna_json
                else None
            )

            moments = detect_moments(transcript, dna, get_analysis_service())
            project.best_moments_json = json.dumps([m.model_dump() for m in moments])
            project.status = ProjectStatus.MOMENTS_READY
            db.commit()

            logger.info(
                "Detected %d best moments for project %s (top score %d)",
                len(moments),
                project.id,
                moments[0].score if moments else 0,
            )

        except AnalysisError as exc:
            logger.warning("Moment detection failed for project %s: %s", project.id, exc)
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            db.commit()
        except Exception as exc:
            logger.exception("Unexpected moment-detection error for project %s", project.id)
            project.status = ProjectStatus.FAILED
            project.error_message = f"Unexpected error: {exc}"
            db.commit()
    finally:
        db.close()


def run_campaign_generation(project_id: str, platforms: list[str] | None = None) -> None:
    """Generate platform-specific content from Content DNA + moments.

    Each platform is generated separately so one failure does not lose the rest.
    """
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            logger.error("Campaign generation started for unknown project %s", project_id)
            return
        if not project.content_dna_json:
            project.status = ProjectStatus.FAILED
            project.error_message = "No Content DNA available. Run analysis first."
            db.commit()
            return

        try:
            project.status = ProjectStatus.GENERATING
            project.error_message = None
            db.commit()

            dna = ContentDNA.model_validate_json(project.content_dna_json)
            moments = (
                [BestMoment.model_validate(m) for m in json.loads(project.best_moments_json)]
                if project.best_moments_json
                else []
            )
            transcript = json.loads(project.transcript_json) if project.transcript_json else {}
            existing = (
                Campaign.model_validate_json(project.platform_content_json)
                if project.platform_content_json
                else None
            )

            campaign, failed = generate_campaign(
                dna=dna,
                moments=moments,
                transcript_excerpt=transcript.get("text", ""),
                platforms=platforms,
                # Resolved here so the backend is patchable in one place.
                service=get_analysis_service(),
                existing=existing,
            )

            if not campaign.generated_platforms:
                project.status = ProjectStatus.FAILED
                project.error_message = (
                    "Campaign generation failed for every platform. "
                    "Check the analysis backend and retry."
                )
                db.commit()
                return

            project.platform_content_json = campaign.model_dump_json()
            project.campaign_score = score_campaign(campaign, dna, moments)

            # Quality evaluation is an add-on: a failure here must never lose the
            # campaign that was just generated.
            try:
                evaluation = evaluate_campaign(campaign, dna, get_analysis_service())
                project.campaign_evaluation_json = evaluation.model_dump_json()
            except Exception as exc:
                # Deliberately broad: scoring is an add-on, and *no* failure in it
                # -- expected or not -- may cost us the campaign we just generated.
                logger.warning(
                    "Campaign evaluation skipped for %s: %s", project.id, exc, exc_info=True
                )
                project.campaign_evaluation_json = None

            project.status = ProjectStatus.COMPLETED
            project.error_message = (
                f"Some platforms could not be generated: {', '.join(failed)}"
                if failed
                else None
            )
            db.commit()

            logger.info(
                "Campaign ready for project %s: %d platforms, score %.1f%s",
                project.id,
                len(campaign.generated_platforms),
                project.campaign_score,
                f" (failed: {', '.join(failed)})" if failed else "",
            )

        except AnalysisError as exc:
            logger.warning("Campaign generation failed for project %s: %s", project.id, exc)
            project.status = ProjectStatus.FAILED
            project.error_message = str(exc)
            db.commit()
        except Exception as exc:
            logger.exception("Unexpected campaign error for project %s", project.id)
            project.status = ProjectStatus.FAILED
            project.error_message = f"Unexpected error: {exc}"
            db.commit()
    finally:
        db.close()


def run_thumbnail_generation(project_id: str) -> None:
    """Generate thumbnail concepts. Isolated: failure never touches other outputs."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            logger.error("Thumbnail generation started for unknown project %s", project_id)
            return
        if not project.content_dna_json:
            logger.warning("Thumbnails requested before analysis for project %s", project_id)
            return

        previous_status = project.status
        try:
            dna = ContentDNA.model_validate_json(project.content_dna_json)
            moments = (
                [BestMoment.model_validate(m) for m in json.loads(project.best_moments_json)]
                if project.best_moments_json
                else []
            )

            concepts = generate_thumbnail_concepts(
                project_id=project.id,
                video_path=Path(project.video_path) if project.video_path else None,
                dna=dna,
                moments=moments,
                duration=project.duration_seconds,
                service=get_analysis_service(),
            )

            project.thumbnail_concepts_json = json.dumps(
                [c.model_dump() for c in concepts]
            )
            db.commit()
            logger.info("Stored %d thumbnail concepts for project %s", len(concepts), project.id)

        except AnalysisError as exc:
            # Deliberately non-fatal: thumbnails are an add-on, and losing them
            # must not mark a project with a finished campaign as failed.
            logger.warning("Thumbnail generation failed for project %s: %s", project.id, exc)
            project.status = previous_status
            db.commit()
        except Exception:
            logger.exception("Unexpected thumbnail error for project %s", project.id)
            project.status = previous_status
            db.commit()
    finally:
        db.close()


def run_campaign_evaluation(project_id: str) -> None:
    """Re-score an existing campaign. Never mutates the campaign itself."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None or not project.platform_content_json:
            logger.warning("Evaluation requested with no campaign for %s", project_id)
            return

        try:
            campaign = Campaign.model_validate_json(project.platform_content_json)
            dna = ContentDNA.model_validate_json(project.content_dna_json or "{}")
            evaluation = evaluate_campaign(campaign, dna, get_analysis_service())
            project.campaign_evaluation_json = evaluation.model_dump_json()
            db.commit()
            logger.info("Re-evaluated campaign for %s: %d", project.id, evaluation.overall)
        except EvaluationError as exc:
            logger.warning("Campaign evaluation failed for %s: %s", project.id, exc)
        except Exception:
            logger.exception("Unexpected evaluation error for %s", project.id)
    finally:
        db.close()

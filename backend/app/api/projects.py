import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project, ProjectStatus
from app.schemas.campaign import Campaign, CampaignResponse, PLATFORM_NAMES
from app.schemas.content_dna import ContentDNA, ContentDNAResponse
from app.schemas.evaluation import EvaluationResponse
from app.schemas.thumbnail import ThumbnailConcept, ThumbnailsResponse
from app.schemas.moment import (
    BestMoment,
    BestMomentsResponse,
    Clip,
    ClipRequest,
    ClipsResponse,
)
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    TranscriptResponse,
)
from app.services.clip_service import clip_path_for, generate_clip
from app.services.media_service import MediaProcessingError
from app.services.evaluation_service import load_evaluation
from app.services.thumbnail_service import image_generation_available
from app.services.pipeline_service import (
    run_analysis,
    run_campaign_evaluation,
    run_thumbnail_generation,
    run_campaign_generation,
    run_moment_detection,
    run_pipeline,
)
from app.services.upload_service import new_project_id

ACTIVE_STATUSES = {
    ProjectStatus.PROCESSING,
    ProjectStatus.TRANSCRIBING,
    ProjectStatus.ANALYZING,
    ProjectStatus.DETECTING_MOMENTS,
    ProjectStatus.GENERATING,
}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


def _parse_json_field(raw: str | None) -> dict | list | None:
    if raw is None:
        return None
    return json.loads(raw)


def _to_detail(project: Project) -> ProjectDetail:
    return ProjectDetail(
        id=project.id,
        title=project.title,
        status=project.status,
        error_message=project.error_message,
        video_filename=project.video_filename,
        video_url=project.video_url,
        duration_seconds=project.duration_seconds,
        video_width=project.video_width,
        video_height=project.video_height,
        video_fps=project.video_fps,
        video_size_bytes=project.video_size_bytes,
        campaign_score=project.campaign_score,
        clip_count=project.clip_count,
        post_count=project.post_count,
        moment_count=project.moment_count,
        has_content_dna=project.has_content_dna,
        created_at=project.created_at,
        updated_at=project.updated_at,
        transcript=_parse_json_field(project.transcript_json),
        content_dna=_parse_json_field(project.content_dna_json),
        key_topics=_parse_json_field(project.key_topics_json),
        best_moments=_parse_json_field(project.best_moments_json),
        clips=_parse_json_field(project.clips_json),
        platform_content=_parse_json_field(project.platform_content_json),
        thumbnail_concepts=_parse_json_field(project.thumbnail_concepts_json),
        campaign_evaluation=load_evaluation(project.campaign_evaluation_json),
    )


@router.post("", response_model=ProjectSummary, status_code=201)
def create_project(
    payload: ProjectCreateRequest, db: Session = Depends(get_db)
) -> Project:
    """Create an empty project shell. A video is attached afterwards via POST /api/upload."""
    project = Project(
        id=new_project_id(),
        title=payload.title or "Untitled Project",
        status=ProjectStatus.PENDING,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("Created project %s (%s)", project.id, project.title)
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectDetail:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_detail(project)


@router.get("/{project_id}/transcript", response_model=TranscriptResponse)
def get_transcript(project_id: str, db: Session = Depends(get_db)) -> TranscriptResponse:
    """Return the stored transcript with timestamped segments."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.transcript_json:
        if project.status == ProjectStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=project.error_message or "Transcription failed for this project",
            )
        raise HTTPException(
            status_code=404,
            detail="Transcript not ready yet. Run POST /api/projects/{id}/process first.",
        )

    payload = json.loads(project.transcript_json)
    return TranscriptResponse(project_id=project.id, **payload)


@router.post("/{project_id}/process", response_model=ProjectSummary)
def process_project(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Project:
    """Kick off the media pipeline (metadata extraction, audio extraction, transcription)."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.video_path:
        raise HTTPException(status_code=400, detail="No video attached to this project")
    if project.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Processing is already in progress")

    project.status = ProjectStatus.PROCESSING
    project.error_message = None
    db.commit()
    db.refresh(project)

    background_tasks.add_task(run_pipeline, project.id)
    logger.info("Queued pipeline for project %s", project.id)
    return project


@router.post("/{project_id}/analyze", response_model=ProjectSummary)
def analyze_project(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Project:
    """Build Content DNA from the project's transcript (runs in the background)."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.transcript_json:
        raise HTTPException(
            status_code=400,
            detail="No transcript available. Run POST /api/projects/{id}/process first.",
        )
    if project.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Processing is already in progress")

    project.status = ProjectStatus.ANALYZING
    project.error_message = None
    db.commit()
    db.refresh(project)

    background_tasks.add_task(run_analysis, project.id)
    logger.info("Queued analysis for project %s", project.id)
    return project


@router.get("/{project_id}/content-dna", response_model=ContentDNAResponse)
def get_content_dna(project_id: str, db: Session = Depends(get_db)) -> ContentDNAResponse:
    """Return the stored Content DNA — the source of truth for downstream generation."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.content_dna_json:
        if project.status == ProjectStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=project.error_message or "Analysis failed for this project",
            )
        raise HTTPException(
            status_code=404,
            detail="Content DNA not ready yet. Run POST /api/projects/{id}/analyze first.",
        )

    return ContentDNAResponse(
        project_id=project.id,
        content_dna=ContentDNA.model_validate_json(project.content_dna_json),
    )


@router.post("/{project_id}/moments", response_model=ProjectSummary)
def detect_project_moments(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Project:
    """Detect the best short-form moments (runs in the background)."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.transcript_json:
        raise HTTPException(
            status_code=400,
            detail="No transcript available. Run POST /api/projects/{id}/process first.",
        )
    if project.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Processing is already in progress")

    project.status = ProjectStatus.DETECTING_MOMENTS
    project.error_message = None
    db.commit()
    db.refresh(project)

    background_tasks.add_task(run_moment_detection, project.id)
    logger.info("Queued moment detection for project %s", project.id)
    return project


@router.get("/{project_id}/moments", response_model=BestMomentsResponse)
def get_project_moments(project_id: str, db: Session = Depends(get_db)) -> BestMomentsResponse:
    """Return the detected best moments, ranked strongest first."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.best_moments_json:
        if project.status == ProjectStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=project.error_message or "Moment detection failed for this project",
            )
        raise HTTPException(
            status_code=404,
            detail="Moments not ready yet. Run POST /api/projects/{id}/moments first.",
        )

    moments = [BestMoment.model_validate(m) for m in json.loads(project.best_moments_json)]
    return BestMomentsResponse(project_id=project.id, moments=moments)


def _load_moments(project: Project) -> list[BestMoment]:
    if not project.best_moments_json:
        return []
    return [BestMoment.model_validate(m) for m in json.loads(project.best_moments_json)]


def _load_clips(project: Project) -> list[Clip]:
    if not project.clips_json:
        return []
    return [Clip.model_validate(c) for c in json.loads(project.clips_json)]


@router.post("/{project_id}/clips", response_model=Clip, status_code=201)
def create_clip(
    project_id: str, payload: ClipRequest, db: Session = Depends(get_db)
) -> Clip:
    """Render a real short video (and thumbnail) for one detected moment."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.video_path:
        raise HTTPException(status_code=400, detail="No video attached to this project")

    moments = _load_moments(project)
    if not moments:
        raise HTTPException(
            status_code=400,
            detail="No detected moments. Run POST /api/projects/{id}/moments first.",
        )

    moment = next((m for m in moments if m.id == payload.moment_id), None)
    if moment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Moment '{payload.moment_id}' not found. Available: "
            + ", ".join(m.id for m in moments),
        )

    clip_id = f"{project.id}_{moment.id}"
    transcript = json.loads(project.transcript_json) if project.transcript_json else {}
    try:
        generated = generate_clip(
            Path(project.video_path),
            moment.start,
            moment.end,
            clip_id,
            transcript_segments=transcript.get("segments") or [],
        )
    except MediaProcessingError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Rendering takes many seconds. Re-read the row so clips saved by a
    # concurrent request during the render are not silently overwritten.
    db.refresh(project)

    clip = Clip(
        clip_id=generated.clip_id,
        moment_id=moment.id,
        video_url=f"/media/clips/{generated.video_path.name}",
        thumbnail_url=f"/media/thumbnails/{generated.thumbnail_path.name}",
        title=moment.title,
        hook=moment.hook,
        score=moment.score,
        start=generated.start,
        end=generated.end,
        duration=generated.duration,
        width=generated.width,
        height=generated.height,
        vertical=generated.vertical,
        subtitled=generated.subtitled,
    )

    # Replace any previous render of the same moment rather than duplicating.
    clips = [c for c in _load_clips(project) if c.moment_id != moment.id]
    clips.append(clip)
    clips.sort(key=lambda c: c.moment_id)
    project.clips_json = json.dumps([c.model_dump() for c in clips])
    db.commit()

    logger.info("Rendered clip %s for project %s", clip.clip_id, project.id)
    return clip


@router.get("/{project_id}/clips/{clip_id}/download")
def download_clip(project_id: str, clip_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Serve a clip as an attachment.

    The static /media mount has no Content-Disposition, and the browser ignores
    an <a download> attribute cross-origin (API :8000 vs app :3000), so a plain
    link would play the video instead of saving it.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    clip = next((c for c in _load_clips(project) if c.clip_id == clip_id), None)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")

    path = clip_path_for(clip.clip_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file is missing; regenerate it")

    safe_title = "".join(
        ch for ch in (clip.title or "short") if ch.isalnum() or ch in " -_"
    ).strip() or "short"
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{safe_title}.mp4",
    )


@router.get("/{project_id}/clips", response_model=ClipsResponse)
def list_clips(project_id: str, db: Session = Depends(get_db)) -> ClipsResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ClipsResponse(project_id=project.id, clips=_load_clips(project))


@router.post("/{project_id}/campaign", response_model=ProjectSummary)
def generate_project_campaign(
    project_id: str,
    background_tasks: BackgroundTasks,
    platform: str | None = None,
    db: Session = Depends(get_db),
) -> Project:
    """Generate the multi-platform campaign.

    Pass ?platform=tiktok to regenerate a single platform, leaving the rest intact.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.content_dna_json:
        raise HTTPException(
            status_code=400,
            detail="No Content DNA. Run POST /api/projects/{id}/analyze first.",
        )
    if project.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Processing is already in progress")

    platforms: list[str] | None = None
    if platform is not None:
        if platform not in PLATFORM_NAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown platform '{platform}'. Supported: {', '.join(PLATFORM_NAMES)}",
            )
        platforms = [platform]

    project.status = ProjectStatus.GENERATING
    project.error_message = None
    db.commit()
    db.refresh(project)

    background_tasks.add_task(run_campaign_generation, project.id, platforms)
    logger.info(
        "Queued campaign generation for project %s (%s)",
        project.id,
        platform or "all platforms",
    )
    return project


@router.get("/{project_id}/campaign", response_model=CampaignResponse)
def get_campaign(project_id: str, db: Session = Depends(get_db)) -> CampaignResponse:
    """Return the generated multi-platform campaign."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.platform_content_json:
        if project.status == ProjectStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=project.error_message or "Campaign generation failed",
            )
        raise HTTPException(
            status_code=404,
            detail="Campaign not ready yet. Run POST /api/projects/{id}/campaign first.",
        )

    return CampaignResponse(
        project_id=project.id,
        campaign=Campaign.model_validate_json(project.platform_content_json),
        campaign_score=project.campaign_score,
    )


@router.post("/{project_id}/evaluate", response_model=ProjectSummary)
def evaluate_project_campaign(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Project:
    """Re-run the AI quality evaluation for an existing campaign."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.platform_content_json:
        raise HTTPException(
            status_code=400,
            detail="No campaign to evaluate. Run POST /api/projects/{id}/campaign first.",
        )

    background_tasks.add_task(run_campaign_evaluation, project.id)
    logger.info("Queued campaign evaluation for project %s", project.id)
    return project


@router.get("/{project_id}/evaluation", response_model=EvaluationResponse)
def get_evaluation(project_id: str, db: Session = Depends(get_db)) -> EvaluationResponse:
    """Return the campaign quality evaluation.

    A missing evaluation is not an error: scoring is an add-on and the campaign
    stands on its own without it.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return EvaluationResponse(
        project_id=project.id,
        evaluation=load_evaluation(project.campaign_evaluation_json),
        completeness_score=project.campaign_score,
    )


@router.post("/{project_id}/thumbnails", response_model=ProjectSummary)
def generate_project_thumbnails(
    project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> Project:
    """Generate 3 thumbnail concepts (runs in the background)."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.content_dna_json:
        raise HTTPException(
            status_code=400,
            detail="No Content DNA. Run POST /api/projects/{id}/analyze first.",
        )

    background_tasks.add_task(run_thumbnail_generation, project.id)
    logger.info("Queued thumbnail generation for project %s", project.id)
    return project


@router.get("/{project_id}/thumbnails", response_model=ThumbnailsResponse)
def get_thumbnails(project_id: str, db: Session = Depends(get_db)) -> ThumbnailsResponse:
    """Return thumbnail concepts. Empty list rather than 404: thumbnails are an
    optional add-on and their absence should not read as an error."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    concepts = (
        [ThumbnailConcept.model_validate(c) for c in json.loads(project.thumbnail_concepts_json)]
        if project.thumbnail_concepts_json
        else []
    )
    return ThumbnailsResponse(
        project_id=project.id,
        concepts=concepts,
        image_generation_available=image_generation_available(),
    )


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.video_path:
        Path(project.video_path).unlink(missing_ok=True)
    db.delete(project)
    db.commit()

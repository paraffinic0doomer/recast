import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project, ProjectStatus
from app.schemas.project import ProjectSummary
from app.services.upload_service import save_video

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=ProjectSummary)
async def upload_video(
    project_id: str = Form(...),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    dest_path, size = await save_video(project.id, video)

    project.video_path = str(dest_path)
    project.video_filename = video.filename or dest_path.name
    project.status = ProjectStatus.UPLOADED
    db.commit()
    db.refresh(project)

    logger.info("Attached video to project %s (%d bytes)", project.id, size)
    return project

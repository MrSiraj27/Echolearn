import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.folders.schemas import CreateFolderRequest, FolderResponse
from app.models import Document, DocumentFolder, User

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(DocumentFolder)
        .filter(DocumentFolder.user_id == current_user.id, DocumentFolder.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have a folder with that name.")

    folder = DocumentFolder(user_id=current_user.id, name=payload.name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderResponse(id=folder.id, name=folder.name, created_at=folder.created_at, document_count=0)


@router.get("/", response_model=list[FolderResponse])
def list_folders(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    folders = (
        db.query(DocumentFolder)
        .filter(DocumentFolder.user_id == current_user.id)
        .order_by(DocumentFolder.created_at.asc())
        .all()
    )
    items = []
    for folder in folders:
        count = db.query(Document).filter(Document.folder_id == folder.id).count()
        items.append(FolderResponse(id=folder.id, name=folder.name, created_at=folder.created_at, document_count=count))
    return items


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    folder = (
        db.query(DocumentFolder)
        .filter(DocumentFolder.id == folder_id, DocumentFolder.user_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")

    # Deleting a folder never deletes the documents inside it — they just become
    # unfiled again, same as before they were grouped.
    db.query(Document).filter(Document.folder_id == folder_id).update({"folder_id": None})
    db.delete(folder)
    db.commit()

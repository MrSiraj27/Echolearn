import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Document, User, Workspace, WorkspaceDocument
from app.workspaces.schemas import (
    AddDocumentRequest,
    CreateWorkspaceRequest,
    WorkspaceDetailResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _get_owned_workspace(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Workspace:
    workspace = (
        db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user_id).first()
    )
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return workspace


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document_ids = set(payload.document_ids)
    if document_ids:
        count = (
            db.query(Document)
            .filter(Document.id.in_(document_ids), Document.user_id == current_user.id)
            .count()
        )
        if count != len(document_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents not found.")

    workspace = Workspace(user_id=current_user.id, name=payload.name)
    db.add(workspace)
    db.flush()

    for document_id in document_ids:
        db.add(WorkspaceDocument(workspace_id=workspace.id, document_id=document_id))

    db.commit()
    db.refresh(workspace)
    return WorkspaceResponse(
        id=workspace.id, name=workspace.name, created_at=workspace.created_at, document_count=len(document_ids)
    )


@router.get("/", response_model=list[WorkspaceResponse])
def list_workspaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspaces = (
        db.query(Workspace).filter(Workspace.user_id == current_user.id).order_by(Workspace.created_at.asc()).all()
    )
    items = []
    for workspace in workspaces:
        count = (
            db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace.id).count()
        )
        items.append(
            WorkspaceResponse(
                id=workspace.id, name=workspace.name, created_at=workspace.created_at, document_count=count
            )
        )
    return items


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
def get_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_owned_workspace(db, workspace_id, current_user.id)
    document_ids = [
        row.document_id
        for row in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == workspace.id).all()
    ]
    return WorkspaceDetailResponse(
        id=workspace.id, name=workspace.name, created_at=workspace.created_at, document_ids=document_ids
    )


@router.post("/{workspace_id}/documents", status_code=status.HTTP_204_NO_CONTENT)
def add_document(
    workspace_id: uuid.UUID,
    payload: AddDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_owned_workspace(db, workspace_id, current_user.id)
    document = (
        db.query(Document)
        .filter(Document.id == payload.document_id, Document.user_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    existing = (
        db.query(WorkspaceDocument)
        .filter(WorkspaceDocument.workspace_id == workspace.id, WorkspaceDocument.document_id == document.id)
        .first()
    )
    if not existing:
        db.add(WorkspaceDocument(workspace_id=workspace.id, document_id=document.id))
        db.commit()


@router.delete("/{workspace_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = _get_owned_workspace(db, workspace_id, current_user.id)
    db.query(WorkspaceDocument).filter(
        WorkspaceDocument.workspace_id == workspace.id, WorkspaceDocument.document_id == document_id
    ).delete()
    db.commit()


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Deleting a workspace never deletes the underlying documents — only the grouping.
    workspace = _get_owned_workspace(db, workspace_id, current_user.id)
    db.delete(workspace)
    db.commit()

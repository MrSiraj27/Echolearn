import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.chats.export import build_markdown, build_pdf
from app.chats.schemas import (
    ChatDetailResponse,
    ChatListItem,
    ChatResponse,
    CreateChatRequest,
    DiagramRequest,
    DiagramResponse,
    ExplainRequest,
    ExplainResponse,
    InfographicRequest,
    InfographicResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.core.database import get_db
from app.core.security import block_if_impersonating, get_current_user
from app.models import (
    Chat,
    ChatDocument,
    Document,
    DocumentStatus,
    Message,
    MessageRole,
    QueryLog,
    User,
    Workspace,
    WorkspaceDocument,
)
from app.admin.config_service import is_feature_enabled
from app.core.usage import check_and_record_usage
from app.rag.diagram import generate_diagram
from app.rag.infographic_generator import VALID_TEMPLATES, extract_infographic_data
from app.rag.langgraph_pipeline import run_rag_pipeline, stream_rag_pipeline
from app.rag.smalltalk import detect_smalltalk_reply
from app.rag.vectorstore import search, search_multi_document

router = APIRouter(prefix="/chats", tags=["chats"])


def _get_owned_chat(db: Session, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat:
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    return chat


def _get_ready_document_ids(db: Session, chat: Chat) -> list[uuid.UUID]:
    """Documents this chat can search right now — resolved fresh on every call rather than
    frozen at chat-creation time, so a document that finishes embedding after the chat was
    created (or a document added to the chat's workspace later) becomes searchable
    automatically, with no need to start a new chat.
    """
    if chat.workspace_id:
        rows = (
            db.query(Document.id)
            .join(WorkspaceDocument, WorkspaceDocument.document_id == Document.id)
            .filter(
                WorkspaceDocument.workspace_id == chat.workspace_id,
                Document.status.in_([DocumentStatus.embedded, DocumentStatus.ready]),
            )
            .all()
        )
        return [row.id for row in rows]

    rows = (
        db.query(Document.id)
        .join(ChatDocument, ChatDocument.document_id == Document.id)
        .filter(
            ChatDocument.chat_id == chat.id,
            Document.status.in_([DocumentStatus.embedded, DocumentStatus.ready]),
        )
        .all()
    )
    return [row.id for row in rows]


def _derive_chat_title(filenames: list[str]) -> str | None:
    """Turn document filename(s) into a friendly chat title, e.g. 'style_guide-v2.pdf' ->
    'Style guide v2'. Falls back to None (frontend shows 'Untitled chat') if none given."""
    if not filenames:
        return None

    def clean(name: str) -> str:
        stem = name.rsplit(".", 1)[0]
        words = re.sub(r"[\s_\-]+", " ", stem).strip()
        return words[:1].upper() + words[1:] if words else stem

    cleaned = [clean(f) for f in filenames]
    if len(cleaned) == 1:
        return cleaned[0][:60]
    return f"{cleaned[0]} + {len(cleaned) - 1} more"[:60]


@router.post("/", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    payload: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.workspace_id:
        workspace = (
            db.query(Workspace)
            .filter(Workspace.id == payload.workspace_id, Workspace.user_id == current_user.id)
            .first()
        )
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

        title = payload.title or workspace.name
        chat = Chat(user_id=current_user.id, title=title, workspace_id=workspace.id)
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat

    documents: list[Document] = []
    if payload.document_ids:
        documents = (
            db.query(Document)
            .filter(Document.id.in_(payload.document_ids), Document.user_id == current_user.id)
            .all()
        )
        if len(documents) != len(set(payload.document_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more documents not found.")

    title = payload.title or _derive_chat_title([d.filename for d in documents])
    chat = Chat(user_id=current_user.id, title=title)
    db.add(chat)
    db.flush()

    for document_id in payload.document_ids:
        db.add(ChatDocument(chat_id=chat.id, document_id=document_id))

    db.commit()
    db.refresh(chat)
    return chat


@router.get("/", response_model=list[ChatListItem])
def list_chats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chats = (
        db.query(Chat).filter(Chat.user_id == current_user.id).order_by(Chat.created_at.desc()).all()
    )

    items = []
    for chat in chats:
        last_message = (
            db.query(Message)
            .filter(Message.chat_id == chat.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        items.append(
            ChatListItem(
                id=chat.id,
                title=chat.title,
                created_at=chat.created_at,
                preview=(last_message.content[:120] if last_message else None),
            )
        )
    return items


@router.get("/{chat_id}", response_model=ChatDetailResponse)
def get_chat_detail(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, chat_id, current_user.id)

    if chat.workspace_id:
        document_ids = [
            row.document_id
            for row in db.query(WorkspaceDocument).filter(WorkspaceDocument.workspace_id == chat.workspace_id).all()
        ]
        workspace_name = chat.workspace.name if chat.workspace else None
    else:
        document_ids = [
            row.document_id for row in db.query(ChatDocument).filter(ChatDocument.chat_id == chat.id).all()
        ]
        workspace_name = None

    return ChatDetailResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        document_ids=document_ids,
        workspace_id=chat.workspace_id,
        workspace_name=workspace_name,
    )


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
def get_chat_messages(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_chat(db, chat_id, current_user.id)
    messages = (
        db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.asc()).all()
    )
    return messages


@router.post("/{chat_id}/message")
async def send_message(
    chat_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(block_if_impersonating),
):
    chat = _get_owned_chat(db, chat_id, current_user.id)

    if not payload.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    check_and_record_usage(db, current_user, "message")

    user_message = Message(chat_id=chat.id, role=MessageRole.user, content=payload.content)
    db.add(user_message)
    db.commit()

    document_ids = _get_ready_document_ids(db, chat)

    prior_messages = (
        db.query(Message)
        .filter(Message.chat_id == chat.id, Message.id != user_message.id)
        .order_by(Message.created_at.desc())
        .limit(6)
        .all()
    )
    chat_history = [
        {"role": m.role.value, "content": m.content} for m in reversed(prior_messages)
    ]

    async def event_stream():
        full_answer = ""
        citations: list[dict] = []
        follow_ups: list[str] = []
        was_answered = True
        skip_log = False

        smalltalk_reply = detect_smalltalk_reply(user_message.content)
        if smalltalk_reply is not None:
            full_answer = smalltalk_reply
            yield f"event: token\ndata: {json.dumps({'content': full_answer})}\n\n"
        elif not document_ids:
            full_answer = (
                "This chat doesn't have any ready documents to search yet. If you just "
                "uploaded a file, wait for it to finish processing (check the sidebar for "
                "\"Ready\"), then ask again."
            )
            skip_log = True
            yield f"event: token\ndata: {json.dumps({'content': full_answer})}\n\n"
        else:
            async for event_type, payload_data in stream_rag_pipeline(
                question=user_message.content,
                chat_history=chat_history,
                user_id=current_user.id,
                document_ids=document_ids,
            ):
                if event_type == "token":
                    full_answer += payload_data
                    yield f"event: token\ndata: {json.dumps({'content': payload_data})}\n\n"
                elif event_type == "done":
                    citations = payload_data.get("citations", [])
                    follow_ups = payload_data.get("follow_ups", [])
                    was_answered = payload_data.get("was_answered", True)

        assistant_message = Message(
            chat_id=chat.id, role=MessageRole.assistant, content=full_answer, citations=citations
        )
        db.add(assistant_message)

        if not skip_log:
            db.add(
                QueryLog(
                    user_id=current_user.id,
                    chat_id=chat.id,
                    document_ids=[str(d) for d in document_ids],
                    workspace_id=chat.workspace_id,
                    question=user_message.content,
                    was_answered=was_answered,
                )
            )

        db.commit()

        yield (
            "event: done\ndata: "
            + json.dumps(
                {"citations": citations, "follow_ups": follow_ups, "message_id": str(assistant_message.id)}
            )
            + "\n\n"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{chat_id}/explain", response_model=ExplainResponse)
async def explain_selection(
    chat_id: uuid.UUID,
    payload: ExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, chat_id, current_user.id)

    selected_text = payload.text.strip()
    if not selected_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No text selected.")

    document_ids = _get_ready_document_ids(db, chat)

    question = (
        f'Explain the following in more detail, using the document as context: "{selected_text}"'
    )
    result = await run_rag_pipeline(
        question=question, chat_history=[], user_id=current_user.id, document_ids=document_ids
    )
    return ExplainResponse(explanation=result["answer"], citations=result["citations"])


@router.post("/{chat_id}/diagram", response_model=DiagramResponse)
def generate_chat_diagram(
    chat_id: uuid.UUID,
    payload: DiagramRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_feature_enabled("diagram_generation_enabled"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Diagram generation is temporarily unavailable.")

    check_and_record_usage(db, current_user, "diagram_infographic")

    chat = _get_owned_chat(db, chat_id, current_user.id)

    instruction = payload.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter what you'd like diagrammed.")

    document_ids = _get_ready_document_ids(db, chat)
    if not document_ids:
        return DiagramResponse(
            possible=False, error="This chat doesn't have any ready documents to diagram yet."
        )

    if len(document_ids) > 1:
        chunks = search_multi_document(instruction, current_user.id, document_ids, top_k=8, per_doc_k=3)
    else:
        chunks = search(instruction, current_user.id, document_ids, top_k=8)

    if not chunks:
        return DiagramResponse(
            possible=False, error="Couldn't find anything relevant to diagram in this document."
        )

    mermaid_code = generate_diagram(instruction, chunks)
    if not mermaid_code:
        return DiagramResponse(
            possible=False,
            error="This content doesn't have a clear structure to diagram — try asking about a "
            "specific process or relationship in the document.",
        )

    message = Message(chat_id=chat.id, role=MessageRole.assistant, content=mermaid_code, content_type="mermaid")
    db.add(message)
    db.commit()
    db.refresh(message)

    return DiagramResponse(possible=True, message=message)


@router.post("/{chat_id}/infographic", response_model=InfographicResponse)
def generate_chat_infographic(
    chat_id: uuid.UUID,
    payload: InfographicRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_feature_enabled("infographic_generation_enabled"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Infographic generation is temporarily unavailable.")

    check_and_record_usage(db, current_user, "diagram_infographic")

    chat = _get_owned_chat(db, chat_id, current_user.id)

    template = (payload.template or "auto").strip().lower()
    if template != "auto" and template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"template must be one of: auto, {', '.join(sorted(VALID_TEMPLATES))}.",
        )

    instruction = (payload.instruction or "").strip()

    document_ids = _get_ready_document_ids(db, chat)
    if not document_ids:
        return InfographicResponse(
            possible=False, error="This chat doesn't have any ready documents to summarize yet."
        )

    query = instruction or "key facts, figures, and structure of this document"
    if len(document_ids) > 1:
        chunks = search_multi_document(query, current_user.id, document_ids, top_k=10, per_doc_k=3)
    else:
        chunks = search(query, current_user.id, document_ids, top_k=10)

    if not chunks:
        return InfographicResponse(
            possible=False, error="Couldn't find anything relevant to summarize in this document."
        )

    result = extract_infographic_data(chunks, instruction, template)
    if not result:
        return InfographicResponse(
            possible=False,
            error="This content doesn't have enough structured information for an infographic — "
            "try generating a plain summary instead.",
        )

    resolved_template, data = result
    content = json.dumps({"template": resolved_template, "data": data})
    message = Message(chat_id=chat.id, role=MessageRole.assistant, content=content, content_type="infographic")
    db.add(message)
    db.commit()
    db.refresh(message)

    return InfographicResponse(possible=True, message=message)


@router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a single message — mainly for clearing a diagram generation that came out
    malformed, without deleting the whole chat."""
    chat = _get_owned_chat(db, chat_id, current_user.id)
    message = db.query(Message).filter(Message.id == message_id, Message.chat_id == chat.id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    db.delete(message)
    db.commit()


@router.get("/{chat_id}/export")
def export_chat(
    chat_id: uuid.UUID,
    format: str = "markdown",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if format not in ("markdown", "pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'markdown' or 'pdf'.")

    chat = _get_owned_chat(db, chat_id, current_user.id)
    messages = db.query(Message).filter(Message.chat_id == chat.id).order_by(Message.created_at.asc()).all()

    if chat.workspace_id:
        document_filenames = [
            row.filename
            for row in db.query(Document.filename)
            .join(WorkspaceDocument, WorkspaceDocument.document_id == Document.id)
            .filter(WorkspaceDocument.workspace_id == chat.workspace_id)
            .all()
        ]
    else:
        document_filenames = [
            row.filename
            for row in db.query(Document.filename)
            .join(ChatDocument, ChatDocument.document_id == Document.id)
            .filter(ChatDocument.chat_id == chat.id)
            .all()
        ]

    safe_title = re.sub(r"[^\w\-]+", "_", chat.title or "echolearn_chat").strip("_") or "echolearn_chat"

    if format == "markdown":
        content = build_markdown(chat, messages, document_filenames)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
        )

    pdf_bytes = build_pdf(chat, messages, document_filenames)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, chat_id, current_user.id)
    db.delete(chat)
    db.commit()

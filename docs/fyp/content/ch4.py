"""Chapter 4: System design and architecture (includes the requirements)."""

BLOCKS = [
    ("h1", "Chapter 4: System Design and Architecture"),
    ("h2", "4.1 Overview"),
    ("p", "This chapter explains how EchoLearn is put together and why. It begins with the requirements the "
          "system had to meet, then describes the architecture, the database, the API and the web client, and "
          "finishes with the two AI pipelines that matter most: how a document becomes searchable, and how a "
          "question becomes a cited answer."),

    ("h2", "4.2 System requirements"),
    ("h3", "4.2.1 Functional requirements"),
    ("p", "{tbl:frs} lists the functional requirements. Each one maps to implemented routes and screens, and the "
          "requirement identifiers are used again in the testing chapter."),
    ("table", "frs", "Functional requirements",
     ["ID", "Requirement"],
     [
         ["FR-01", "A visitor can register with a name, email and password (at least 8 characters) and must "
                   "confirm the email address through a link that expires after 24 hours."],
         ["FR-02", "A user can log in, stay signed in through a refresh token, and reset a forgotten password "
                   "through an emailed link."],
         ["FR-03", "A user can upload PDF, Word, PowerPoint, text, CSV, image, audio and video files, or add a "
                   "video by link, within the size allowed by the plan."],
         ["FR-04", "Uploaded files are processed in the background (parsing, OCR, transcription, chunking, "
                   "embedding) and the user can see the status."],
         ["FR-05", "Each document gets a short summary and suggested questions once it is ready."],
         ["FR-06", "Documents can be placed in folders and grouped into workspaces."],
         ["FR-07", "A user can chat over one document, a folder or a workspace and receive a streamed answer with "
                   "page or timestamp citations."],
         ["FR-08", "When the documents do not contain the answer the system says so and shows no sources."],
         ["FR-09", "A user can search inside a document and open the cited page with the passage highlighted."],
         ["FR-10", "A user can ask by voice and listen to answers, with an optional cloned voice."],
         ["FR-11", "A user can request an answer again in Urdu or Roman Urdu."],
         ["FR-12", "A user can generate a diagram or an infographic from a chat."],
         ["FR-13", "A user can generate a quiz from documents, take it and see a score with explanations."],
         ["FR-14", "Flashcards are scheduled with SM-2 and a daily review session shows what is due."],
         ["FR-15", "A user can create a study plan from an exam date, then complete, skip or compress sessions."],
         ["FR-16", "A user can run a tutor session that asks questions and gives hints in steps."],
         ["FR-17", "A user can generate a one- or two-page revision sheet and download it as a PDF."],
         ["FR-18", "A user can generate a practice paper, optionally patterned on uploaded past papers, and "
                   "submit it for scoring."],
         ["FR-19", "A user can see analytics about activity, weak topics and quiz results."],
         ["FR-20", "Usage is limited by plan, and the user can see how much of each limit is used."],
         ["FR-21", "An administrator can manage users, plans, limits, reported content and platform settings."],
     ], [0.7, 5.55]),

    ("h3", "4.2.2 Non-functional requirements"),
    ("table", "nfrs", "Non-functional requirements",
     ["ID", "Requirement", "How it is addressed"],
     [
         ["NFR-01", "Security of credentials", "bcrypt password hashes; signed JWTs; refresh token in an "
                                              "httpOnly, secure cookie."],
         ["NFR-02", "Data isolation between users", "Every document and vector chunk carries the owner; "
                                                   "queries filter on the owner."],
         ["NFR-03", "Run on a small free host", "ONNX embedding model, batches of 16, OCR only for scanned "
                                              "files, one parsing job at a time."],
         ["NFR-04", "Resilience to provider failure", "Fallback from Groq to Gemini; fixed message when both "
                                                     "fail; study plans cached in the database."],
         ["NFR-05", "Fair use", "Per-plan quotas on documents, storage, messages, generations, voice and "
                               "tutor sessions."],
         ["NFR-06", "Responsiveness", "Answers stream token by token; ingestion runs outside the request."],
         ["NFR-07", "Maintainability", "Alembic migrations; one module per feature; pinned dependencies."],
         ["NFR-08", "Portability", "Vector store and file storage selected by configuration; Docker files "
                                  "for self-hosting."],
     ], [0.8, 2.0, 3.45]),

    ("h2", "4.3 System architecture"),
    ("h3", "4.3.1 High-level architecture"),
    ("p", "The system has three tiers plus a set of external and local AI services. The client tier is a Next.js "
          "web application, a Flutter mobile application, and an administration console that is part of the web "
          "application under the /admin routes. The application tier is a FastAPI service that exposes a REST "
          "API. The data tier is PostgreSQL for structured data, a vector store for embeddings, and file storage "
          "for the original files and the parsed text."),
    ("p", "Two design rules were kept throughout. The client never talks to the database, the vector store or "
          "the model providers directly, so keys and filters stay on the server. And slow work (parsing, OCR, "
          "transcription, embedding, plan and sheet generation) runs outside the request that triggered it, with "
          "a status field the client can poll."),
    ("h3", "4.3.2 System architecture diagram"),
    ("p", "{fig:arch} shows the tiers and how they connect. Requests travel over HTTPS with a JWT bearer token. "
          "The backend calls Groq (and Gemini as a fallback) for language-model work, and runs the embedding "
          "model, the speech recogniser, the OCR engine and the text-to-speech voice inside its own process."),
    ("fig", "arch", "fig_architecture.png", "High-level system architecture of EchoLearn", 6.25),

    ("h2", "4.4 Database design"),
    ("h3", "4.4.1 Tables overview"),
    ("p", "The PostgreSQL schema has 32 tables, created through 18 Alembic migrations. {tbl:tables} describes "
          "the main groups; the full set is visible in the entity relationship diagram at the end of the "
          "chapter."),
    ("table", "tables", "Main database tables in EchoLearn",
     ["Table", "Purpose", "Key fields"],
     [
         ["users", "Accounts, roles and plan assignment", "email, password_hash, is_verified, plan_id, "
                                                          "custom_limits, is_blocked"],
         ["plans", "Plan names, prices and limits", "slug, price_monthly, limits (JSON)"],
         ["documents", "Uploaded files and processing status", "filename, file_type, status, page_count, "
                                                              "summary, folder_id"],
         ["document_folders / workspaces", "Organising documents", "name, user_id; workspace_documents links"],
         ["chats / messages", "Conversations and their messages", "title, role, content, citations (JSON)"],
         ["quizzes / quiz_attempts", "Generated quizzes and scored attempts", "questions (JSON), answers, score"],
         ["review_cards / review_card_states", "Flashcards and their SM-2 state", "ease_factor, interval_days, "
                                                                                 "repetitions, next_review_date"],
         ["study_plans / study_sessions", "Exam plans and daily sessions", "exam_date, scheduled_date, "
                                                                          "topic_title, status"],
         ["tutor_sessions / tutor_turns", "Guided tutoring state and transcript", "plan, level, hint_level, "
                                                                                 "verdict"],
         ["revision_sheets", "Generated sheets and PDFs", "topics, content, pdf_path, content_hash"],
         ["past_papers / practice_papers", "Exam structure and generated papers", "extracted_pattern, "
                                                                                  "pattern_config, generated_content"],
         ["usage_events, api_call_logs", "Quota accounting and provider call log", "event_type, provider, "
                                                                                  "duration_ms, success"],
         ["content_reports, admin_audit_logs", "Moderation and audit trail", "reason, status, action, target_id"],
     ], [1.9, 2.1, 2.25]),
    ("h3", "4.4.2 Schema design decisions"),
    ("p", "Questions of a quiz, the citations of a message and the limits of a plan are stored as JSON columns. "
          "They are always read and written as a unit and never queried field by field, so a separate table for "
          "each would add joins without adding value. Everything that is queried or constrained, such as who owns "
          "a document or which flashcard is due today, is a normal column with a foreign key."),
    ("p", "Plan limits are a JSON object on the plan, and a user can carry a custom_limits object that overrides "
          "it key by key. A key set to null in the override means unlimited. All quota checks go through a single "
          "function that merges the two, so an override cannot be bypassed by reading the plan directly. "
          "Documents have a status (uploaded, parsing, embedded, ready, failed) so that failures are visible and "
          "an administrator can retry processing."),

    ("h2", "4.5 API design"),
    ("h3", "4.5.1 Endpoint groups"),
    ("p", "The backend exposes 139 endpoints in 22 route groups plus a health check. Apart from the health "
          "check and the sign-up, login, verification and password-reset routes under /auth, every endpoint "
          "requires a bearer token. {tbl:api} lists the groups and a few typical endpoints; the full list is the "
          "OpenAPI document that FastAPI publishes."),
    ("table", "api", "Main API groups in EchoLearn",
     ["Group", "Endpoints", "Examples"],
     [
         ["auth", "7", "POST /auth/signup, POST /auth/login, POST /auth/refresh-token"],
         ["documents", "12", "POST /documents/upload, POST /documents/from-url, GET /documents/{id}/status"],
         ["folders, workspaces", "9", "POST /folders/, POST /workspaces/{id}/documents"],
         ["chats", "12", "POST /chats/{id}/message (streamed), POST /chats/{id}/explain, "
                             "POST /chats/{id}/diagram"],
         ["quizzes", "4", "POST /quizzes/generate, POST /quizzes/{id}/submit"],
         ["review", "6", "GET /review/today, POST /review/{card_id}/submit"],
         ["study-plans", "12", "POST /study-plans/preview, POST /study-plans/, GET /study-plans/today"],
         ["tutor", "9", "POST /tutor/sessions, POST /tutor/sessions/{id}/hint"],
         ["revision-sheets", "6", "POST /revision-sheets/, GET /revision-sheets/{id}/download"],
         ["practice-papers, past-papers", "13", "POST /practice-papers/generate, POST /past-papers/upload"],
         ["voice", "11", "POST /voice/speak, POST /voice/clone-request"],
         ["analytics, users", "7", "GET /analytics/overview, GET /users/me/usage"],
         ["admin-*", "30", "GET /admin/users/, PATCH /admin/plans/{id}, POST /admin/users/{id}/block"],
     ], [1.6, 0.9, 3.75]),
    ("h3", "4.5.2 Authentication and authorisation"),
    ("p", "Login returns a short-lived access token (15 minutes) in the response body and sets a 7-day refresh "
          "token as an httpOnly cookie. The cookie uses SameSite=None and Secure, because the web client and "
          "the API are on different domains in the deployed setup. Protected routes read the bearer token, "
          "check its signature and type, load the user and reject blocked accounts. Admin routes use a separate "
          "dependency that also checks the admin flag. Login and verification-email requests are rate limited "
          "per email address (5 attempts in 15 minutes) so that passwords cannot be guessed quickly. The login "
          "error is the same whether the email or the password is wrong, so the endpoint does not reveal which "
          "emails are registered."),

    ("h2", "4.6 Frontend architecture"),
    ("p", "The web client is a Next.js application with route groups: (auth) for sign-in pages, (chat) for the "
          "main product screens, and admin for the console. It is written in TypeScript with Tailwind CSS and a "
          "small set of shared components such as the sidebar, source viewer and modal dialogs."),
    ("h3", "4.6.1 Shared state management"),
    ("p", "State is kept small. An authentication context holds the signed-in user and the in-memory access token; "
          "a Zustand store keeps the chat list and the active selection; the rest is local component state. "
          "There is no global cache layer. Requests go through one API helper that attaches the token and, when "
          "a call returns 401, refreshes the token once and retries."),
    ("h3", "4.6.2 Theming"),
    ("p", "Light and dark themes are handled by next-themes with CSS variables, so components do not carry "
          "their own colour logic. Diagrams are rendered in the browser from Mermaid text produced by the "
          "backend, and infographics from a small JSON description."),
    ("h3", "4.6.3 Mobile client"),
    ("p", "The Flutter application covers sign-in, documents, chat, study features and voice settings. It uses "
          "the same REST API as the web client, a provider-based state layer and a small API client that stores "
          "the token on the device. Admin features are web only."),

    ("h2", "4.7 AI pipelines"),
    ("h3", "4.7.1 Document ingestion pipeline"),
    ("p", "{fig:ingest} shows what happens after an upload. The file is saved, a background task picks it up, "
          "and the parser for its type extracts text and tables page by page. PDFs with a text layer are read "
          "directly; if most pages have no text the file is treated as scanned and the pages are passed to the "
          "OCR engine. Audio and video are transcribed with timestamps. The text is split into chunks of about "
          "1,000 characters with 150 characters of overlap; each table is kept as one chunk so that its rows are "
          "not separated. Each chunk is embedded into a 384-dimension vector and stored with the document, "
          "page and owner. A summary and suggested questions are generated last, and a failure there does not "
          "stop the document from being usable."),
    ("fig", "ingest", "fig_ingestion.png", "Document ingestion pipeline", 6.25),
    ("h3", "4.7.2 Question-answering pipeline"),
    ("p", "{fig:rag} shows how a question is answered. First a small model turns the question into a standalone "
          "form (resolving words like \"it\" from the chat history) and proposes alternative phrasings. "
          "Retrieval then combines three signals: vector search for each phrasing, a BM25 keyword search over "
          "all chunks of the chat's documents, and a reference lookup that matches a cited number such as 240 "
          "against the bracketed marker [240] in the text. The lists are merged with reciprocal rank fusion. "
          "When a numbered item is found, the text that continues onto the next page is added, because such "
          "items often cross a page break."),
    ("p", "A relevance check follows. If the closest vector is already very near, the context is accepted; "
          "otherwise a small model answers yes or no to \"could these excerpts answer the question?\". When "
          "the user asked for a specific number or page and it was found, the check is skipped. If the context "
          "is rejected, or the answer model replies that the information is not in the document, the system "
          "says so and returns no citations. Otherwise the larger model writes the answer from the excerpts, "
          "streams it, and two follow-up questions are suggested."),
    ("fig", "rag", "fig_rag.png", "Question-answering (RAG) pipeline", 6.25),
    ("h3", "4.7.3 Tutor mode"),
    ("p", "The tutor works from a plan of concepts extracted from the selected documents once per session and "
          "cached. For each concept it asks a question, grades the student's reply against the passages (not "
          "against the model's general knowledge) and then moves along a hint ladder: level 0 is the question "
          "alone, level 1 a nudge, level 2 a larger clue, level 3 a partial explanation with a blank, and level "
          "4 the full explanation followed by a short check question. The \"Just tell me\" button always jumps "
          "to level 4. A student turn needs at most two model calls, which keeps sessions cheap and inside the "
          "provider's rate limit."),
    ("h3", "4.7.4 Generation of study material"),
    ("p", "Revision sheets, practice papers and study plans are generated with map-reduce style pipelines so "
          "that long documents never exceed the model's context. For revision sheets, small-model passes extract "
          "candidate items (definitions, formulas, facts) from batches of chunks and each item is verified against "
          "the chunk's text; the larger model then only picks and orders items by identifier and does not "
          "rewrite them, so a fact on the sheet is always text that was extracted and verified. Practice papers "
          "are generated section by section, every question is checked against the passage it cites, and "
          "unsupported questions are discarded and regenerated; if a section cannot be filled with supported "
          "questions the generation fails with a message instead of delivering an unverifiable paper. A study "
          "plan is created in two steps: a preview that makes the one expensive model call and returns a "
          "proposal, then a confirmation that schedules the sessions deterministically without calling the "
          "model again."),

    ("h2", "4.8 Use case diagram"),
    ("p", "{fig:usecase} shows the two actors. A student uses the document, study and voice features; an "
          "administrator additionally manages users, plans, moderation and platform settings. The administrator "
          "role extends the student role, so an administrator can also use every student feature."),
    ("fig", "usecase", "fig_usecases.png", "Use case diagram for EchoLearn", 4.6),

    ("h2", "4.9 Entity relationship diagram"),
    ("p", "{fig:er} shows the core tables and their relationships. The users table is the hub: nearly every "
          "other table carries a user_id foreign key, drawn once as a bus line to keep the diagram readable. A "
          "document belongs to at most one folder and can be attached to many chats and workspaces through "
          "link tables. A quiz has many attempts, a flashcard has one scheduling state, a study plan has many "
          "sessions and a tutor session has many turns."),
    ("fig", "er", "fig_er.png", "Entity relationship diagram of the main EchoLearn tables", 6.25),
]

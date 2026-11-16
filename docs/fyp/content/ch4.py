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
                   "embedding); the user can see the status and, when processing fails, the reason and a retry "
                   "action."],
         ["FR-05", "Each document gets a short summary and suggested questions once it is ready."],
         ["FR-06", "Documents can be placed in folders and grouped into workspaces."],
         ["FR-07", "A user can chat over one document, a folder or a workspace and receive a streamed answer with "
                   "page or timestamp citations."],
         ["FR-08", "When the documents do not contain the answer the system says so and shows no sources."],
         ["FR-09", "A user can search inside a document and open the cited page with the passage highlighted."],
         ["FR-10", "A user can ask by voice and listen to answers, with an optional cloned voice recorded in the "
                   "browser after confirming consent."],
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
         ["FR-22", "A user can read a processed document page by page in the application, search it, and select "
                   "any word, sentence, formula or passage to get a simple explanation based on the surrounding "
                   "text, with follow-up questions."],
         ["FR-23", "A user can rate an answer as helpful or not helpful, or report it as incorrect with a note."],
         ["FR-24", "A user can rename, move, retry and delete documents from a dedicated documents page."],
         ["FR-25", "Signing up with an address that already has an account sends that address a sign-in "
                   "reminder, without revealing on screen that the account exists."],
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
         ["NFR-09", "Reliability of background work", "Jobs interrupted by a restart are marked failed at "
                                                      "start-up; status changes only along allowed transitions; "
                                                      "retries reuse already-extracted text."],
         ["NFR-10", "Session continuity", "Access tokens are renewed in the background and every authenticated "
                                         "request retries once after renewing an expired token."],
         ["NFR-11", "Usable on every screen size", "One design system (DESIGN.md) and layouts tested at 375, "
                                                  "768, 1024, 1280 and 1920 pixels wide."],
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
    ("p", "The PostgreSQL schema has 33 tables, created through 19 Alembic migrations. {tbl:tables} describes "
          "the main groups; the full set is visible in the entity relationship diagram at the end of the "
          "chapter."),
    ("table", "tables", "Main database tables in EchoLearn",
     ["Table", "Purpose", "Key fields"],
     [
         ["users", "Accounts, roles and plan assignment", "email, password_hash, is_verified, plan_id, "
                                                          "custom_limits, is_blocked"],
         ["plans", "Plan names, prices and limits", "slug, price_monthly, limits (JSON)"],
         ["documents", "Uploaded files and processing status", "filename, file_type, status, error_message, "
                                                              "page_count, file_size, summary, folder_id"],
         ["document_folders / workspaces", "Organising documents", "name, user_id; workspace_documents links"],
         ["chats / messages", "Conversations and their messages", "title, role, content, citations (JSON)"],
         ["message_feedback", "One rating per user per answer", "message_id, user_id, rating, comment"],
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
          "Documents have a status (uploaded, parsing, embedded, ready, failed) and, when processing fails, an "
          "error_message written for the user (for example a password-protected or damaged PDF), so that "
          "failures are visible and can be retried."),
    ("p", "Several tables carry a status that moves through fixed states: documents, practice papers, past "
          "papers, revision sheets, voice-clone jobs, study plans and sessions, and moderation reports. These "
          "transitions are enforced in code rather than left implicit. A study session can only move from "
          "pending to completed or skipped, and only while its plan is active; finishing the last session "
          "completes the plan; a moderation report can be resolved only once; and a document can be retried "
          "only after it has failed. Because background jobs do not survive a server restart, every job that "
          "is still in progress at start-up is marked failed with an explanation, so nothing waits forever."),

    ("h2", "4.5 API design"),
    ("h3", "4.5.1 Endpoint groups"),
    ("p", "The backend exposes 147 endpoints in 17 route groups plus a health check. Apart from the health "
          "check and the sign-up, login, verification and password-reset routes under /auth, every endpoint "
          "requires a bearer token. {tbl:api} lists the groups and a few typical endpoints; the full list is the "
          "OpenAPI document that FastAPI publishes."),
    ("table", "api", "Main API groups in EchoLearn",
     ["Group", "Endpoints", "Examples"],
     [
         ["auth", "7", "POST /auth/signup, POST /auth/login, POST /auth/refresh-token"],
         ["documents", "16", "POST /documents/upload, GET /documents/{id}/pages, POST /documents/{id}/explain, "
                             "POST /documents/{id}/retry"],
         ["folders, workspaces", "9", "POST /folders/, POST /workspaces/{id}/documents"],
         ["chats", "14", "POST /chats/{id}/message (streamed), PUT /chats/{id}/messages/{id}/feedback, "
                             "POST /chats/{id}/diagram"],
         ["quizzes", "4", "POST /quizzes/generate, POST /quizzes/{id}/submit"],
         ["review", "6", "GET /review/today, POST /review/{card_id}/submit"],
         ["study-plans", "12", "POST /study-plans/preview, POST /study-plans/, GET /study-plans/today"],
         ["tutor", "9", "POST /tutor/sessions, POST /tutor/sessions/{id}/hint"],
         ["revision-sheets", "6", "POST /revision-sheets/, GET /revision-sheets/{id}/download"],
         ["practice-papers, past-papers", "13", "POST /practice-papers/generate, POST /past-papers/upload"],
         ["voice", "11", "POST /voice/speak, POST /voice/clone-request"],
         ["analytics, users", "8", "GET /analytics/overview, GET /users/me, GET /users/me/usage"],
         ["admin-*", "32", "GET /admin/users/, GET /admin/system/feedback, POST /admin/system/index-health"],
     ], [1.6, 0.9, 3.75]),
    ("h3", "4.5.2 Authentication and authorisation"),
    ("p", "Login returns a short-lived access token (15 minutes) in the response body and sets a 7-day refresh "
          "token as an httpOnly cookie. The cookie uses SameSite=None and Secure, because the web client and "
          "the API are on different domains in the deployed setup. Protected routes read the bearer token, "
          "check its signature and type, load the user and reject blocked accounts. Admin routes use a separate "
          "dependency that also checks the admin flag. Login and verification-email requests are rate limited "
          "per email address (5 attempts in 15 minutes) so that passwords cannot be guessed quickly. The login "
          "error is the same whether the email or the password is wrong, so the endpoint does not reveal which "
          "emails are registered. For the same reason, signing up with a registered address shows the usual "
          "message on screen; the owner of the address receives an email instead (a fresh verification link "
          "if the account is unverified, otherwise a sign-in reminder sent at most once every 15 minutes)."),
    ("p", "Because access tokens are short-lived, the web client renews them in the background every 12 "
          "minutes and when the browser tab becomes visible again. Every authenticated request, including the "
          "streamed chat and tutor answers, file uploads and downloads, goes through one helper that renews an "
          "expired token once and retries, so a long study session is not interrupted by an expired token."),

    ("h2", "4.6 Frontend architecture"),
    ("p", "The web client is a Next.js application with route groups: (auth) for sign-in pages, (chat) for the "
          "main product screens, and admin for the console. It is written in TypeScript with Tailwind CSS. Every "
          "signed-in screen shares one application shell: a dark navigation rail with labelled sections "
          "(Dashboard, My Documents, AI Assistant, Document Reader, Tutor Mode, Quizzes, Study Plans, Practice "
          "Papers, Revision Sheets, Analytics, Voice and Listening, Settings), the current plan and usage, and a "
          "top bar with search, theme switch, notifications and the account menu. The dashboard brings the main "
          "tasks onto one screen: recent documents, today's study plan, a reader and an AI assistant panel for "
          "the selected document."),
    ("h3", "4.6.1 Shared state management"),
    ("p", "State is kept small. An authentication context holds the signed-in user and the in-memory access token; "
          "a Zustand store keeps the chat list and the active selection; the rest is local component state. "
          "There is no global cache layer. Requests go through one API helper that attaches the token and, when "
          "a call returns 401, refreshes the token once and retries."),
    ("h3", "4.6.2 Theming"),
    ("p", "The visual design follows a written design system (DESIGN.md): a warm cream canvas instead of pure "
          "white, warm near-black dark surfaces, a serif typeface (Source Serif 4) for headings and reading, Inter "
          "for the interface, and a single coral accent reserved for primary actions. The palette is defined as "
          "theme tokens, so both light and dark themes, handled by next-themes, come from one place and "
          "components do not carry their own colour logic. Layouts change with the screen width: on a phone the "
          "navigation becomes a drawer and panels stack; on a laptop the reader and assistant sit side by side; "
          "on a wide monitor the dashboard uses three columns. Diagrams are rendered in the browser from Mermaid "
          "text produced by the backend, and infographics from a small JSON description."),
    ("h3", "4.6.3 Document reader"),
    ("p", "Text extracted from a PDF arrives one printed line at a time, with the chapter title repeated at the "
          "top of each page and page numbers mixed in. Before display, the reader rebuilds each page: lines are "
          "joined into paragraphs, words split by a hyphen at the end of a line are rejoined, headers that repeat "
          "on many pages and bare page numbers are removed, short headline-like lines become headings (and are "
          "listed as sections), and code is kept as a monospaced block with its line breaks. Search, highlights "
          "and explanations all work on this rebuilt text. For PDFs an Original view shows the file itself."),
    ("h3", "4.6.4 Mobile client"),
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

    ("h3", "4.7.5 Explaining a selected passage"),
    ("p", "When a reader selects text and asks for an explanation, the selection is first classified as a term, "
          "a sentence, a passage, code or a formula, because each needs a different kind of explanation (a "
          "meaning and an example for a term, a step-by-step reading for code, the role of each symbol for a "
          "formula). The prompt then carries the text around the selection on its page and up to four related "
          "passages from the same document found by the hybrid retriever, so a word is explained as the "
          "document uses it rather than in isolation. All document text is wrapped as data and the model is "
          "told never to follow instructions inside it. The model returns a simple explanation, key points, an "
          "example, difficult terms and suggested follow-up questions as JSON, which is validated before it is "
          "shown. Follow-up questions use the same context. Only text is sent: images inside documents are not "
          "passed to a vision model, and the interface does not claim otherwise."),

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

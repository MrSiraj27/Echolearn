"""Chapter 5: Implementation."""

SM2 = '''def update_card_after_review(card, quality):
    if quality < 3:                   # forgotten: start the card over
        card.repetitions = 0
        card.interval_days = 1
    else:
        if card.repetitions == 0:
            card.interval_days = 1
        elif card.repetitions == 1:
            card.interval_days = 6
        else:
            card.interval_days = round(card.interval_days * card.ease_factor)
        card.repetitions += 1

    q = 5 - quality
    card.ease_factor = max(1.3, card.ease_factor + 0.1 - q * (0.08 + q * 0.02))
    card.next_review_date = date.today() + timedelta(days=card.interval_days)'''

FUSION = '''scores = defaultdict(float)
for ranked_list in ranked:        # dense lists plus the BM25 list
    for rank, chunk in enumerate(ranked_list):
        scores[_key(chunk)] += 1.0 / (60 + rank)    # k = 60
fused = sorted(scores, key=scores.get, reverse=True)

# exact reference matches and their continuation always come first
merged = pinned + [by_key[k] for k in fused]'''

BLOCKS = [
    ("h1", "Chapter 5: Implementation"),
    ("h2", "5.1 Overview"),
    ("p", "This chapter describes how the system was built, feature by feature, and the problems we met. The "
          "source is a single repository with a backend folder (FastAPI), a frontend folder (Next.js), a "
          "flutter_app folder, and small deployment and set-up folders. By the end of the project it held about "
          "21,700 lines of Python, 18,800 lines of TypeScript and 4,300 lines of Dart, in 58 commits made between "
          "31 August and 16 November 2026."),

    ("h2", "5.2 Backend implementation"),
    ("h3", "5.2.1 Project structure"),
    ("p", "The backend is organised by feature. Each feature has its own package with routes, schemas and, where "
          "needed, background tasks: auth, documents, folders, workspaces, chats, quizzes, study, tutor, "
          "practice, revision, voice, users, analytics and admin. The language-model and retrieval code sits in "
          "an rag package, shared configuration, security and quota code in core, and SQLAlchemy models in "
          "models. Settings are read from environment variables through a single settings object, and a "
          "pinned requirements file keeps installs reproducible."),
    ("h3", "5.2.2 Model access and fallback"),
    ("p", "All language-model calls go through one function. It calls Groq first, records the call (provider, "
          "purpose, duration, success) in the api_call_logs table, and if the call raises an error or returns an "
          "empty reply it tries Gemini once. Empty replies are a real case: the gpt-oss models reason before "
          "they answer, and on a large prompt a small token budget can be spent entirely on reasoning. Short "
          "internal prompts therefore pass a low reasoning effort. Streaming answers use Groq's streaming call; "
          "if it fails halfway, the same request is repeated without streaming so that the user still gets an "
          "answer."),
    ("h3", "5.2.3 Document processing"),
    ("p", "Upload only validates the file type and the size allowed by the plan, saves the file, and creates a "
          "document row with status uploaded. A background function then takes over. A semaphore allows one "
          "parsing job at a time, because parsing and embedding are memory-heavy and the target host is small. "
          "The parser is chosen by file type: pdfplumber for PDFs (text and tables), python-docx and "
          "python-pptx for Office files, plain readers for text and CSV, RapidOCR for images, and faster-whisper "
          "for audio and video."),
    ("p", "For PDFs, a page counts as empty if it has fewer than 20 characters of text. OCR is used only if at "
          "least half of the pages are empty, which separates a scanned book from a normal PDF that happens to "
          "have a blank cover. OCR runs at 150 dpi and has a 240-second budget per document; pages beyond "
          "the budget are kept without text so that the document still becomes usable. Tables are detected on "
          "each page and converted to Markdown, and each table becomes one chunk. Parsed text is also "
          "written to disk as JSON, next to the original file."),
    ("p", "Failures are reported in words a student can act on. A password-protected PDF, a damaged file, a "
          "file with no readable text, a failed download from a video link, an indexing failure and a job "
          "interrupted by a restart each set a specific error_message on the document. A file that yields no "
          "text at all is now marked failed instead of becoming ready with nothing to search. Text is cleaned "
          "before chunking: placeholder glyph codes such as \"(cid:1127)\" and bare URL footer lines are removed. "
          "A retry reuses the text saved by the earlier attempt and repeats only the indexing step, which turns "
          "minutes of re-transcription on the small host into seconds."),
    ("h3", "5.2.4 Retrieval and answering"),
    ("p", "Chunks are embedded in batches of 16 with the all-MiniLM-L6-v2 model through the ONNX runtime. Search "
          "is done by a hybrid function that first builds, and caches for five minutes, an in-memory BM25 index "
          "from the stored chunks of the chat's documents. The index is skipped if a collection has more than "
          "25,000 chunks, in which case the system falls back to vector search only. The three result lists "
          "are merged as follows (excerpt)."),
    ("code", FUSION),
    ("p", "The reference lookup is deliberately simple. If the question contains a reference word (hadith, "
          "number, chapter, section, question and similar) and a number, the number is searched for in "
          "bracketed form, for example \"[240]\". Matches in other numbering systems, such as \"240 - (153)\", "
          "are added after the main match so that the model can mention them. For the matching chunk, the "
          "chunks that follow it on the same page and the first chunks of the next page are added, and each "
          "chunk is labelled in the prompt (\"exact match\", \"continues the exact match\") so that the model "
          "reads them in order. The prompt context is capped at 9,000 characters to stay inside the provider's "
          "per-minute token limit; pinned chunks come first so they always survive the cap."),
    ("h3", "5.2.5 Authentication, quotas and rate limiting"),
    ("p", "Passwords are hashed with bcrypt through passlib. Access and refresh tokens are signed with HS256. "
          "Email verification and password-reset tokens are random URL-safe strings stored in a table with an "
          "expiry time and a used flag, so a link works once. Usage is counted as rows in a usage_events table "
          "and compared with the effective limits (plan merged with the user's overrides) before an expensive "
          "action runs. A small in-memory rate limiter protects login and verification resends. It resets when "
          "the process restarts, which is acceptable for a single-instance deployment and is listed under "
          "limitations."),
    ("h3", "5.2.6 Spaced repetition"),
    ("p", "Flashcard scheduling follows the SM-2 formulas exactly. The interface offers three buttons, Forgot, "
          "Hard and Easy, which are sent as qualities 1, 3 and 5. A card starts with an ease factor of 2.5, which "
          "never drops below 1.3. The daily session shows at most 25 cards by default (the user can set 5 to "
          "50), with the most overdue and most difficult first. The listing uses shortened names."),
    ("code", SM2),
    ("h3", "5.2.7 Tutor engine"),
    ("p", "The tutor is written as a pure engine: it works on plain dictionaries and has no database access, "
          "and the routes load the state, run it and save what changed. That made it easy to test the hint "
          "ladder in isolation. The plan (the list of concepts and a question for each) is produced by one "
          "model call at the start and stored with the session, so a provider failure in the middle of a "
          "lesson loses nothing. The student can end a session early and still receive a summary and "
          "flashcards for the concepts that were not mastered."),

    ("h3", "5.2.8 Explanations and answer feedback"),
    ("p", "The selection explainer is a small module with pure functions for classifying the selection, cutting "
          "the surrounding window from the page, building the prompt and validating the reply, plus one function "
          "that calls the model and retries once if the reply is not usable JSON. The route enforces ownership "
          "and the message quota, which is charged only after a successful explanation. Answer ratings are "
          "stored in a message_feedback table with one row per user and answer; an administrator endpoint "
          "returns the totals per rating and the recent rated answers with the question that produced them, "
          "so retrieval and answer quality can be reviewed."),
    ("h3", "5.2.9 Reliability measures"),
    ("p", "A review of the code found several statuses whose allowed changes were only implied. They are now "
          "explicit: a lifecycle module owns the study-plan and study-session transitions and is used by both "
          "the plan routes and the quiz auto-completion; moderation reports can be resolved once; the "
          "administrator can retry a document only when it has failed or finished, never while a parse job is "
          "still running. At start-up the server marks every interrupted job as failed: voice-clone jobs, "
          "revision sheets, practice papers, past-paper analyses and documents. When the voice-cloning provider "
          "reports an account-level problem (an invalid key, missing credit or a model limit), cloning is paused "
          "for 30 minutes, users see a plain message and answers are read with the standard voice instead. An "
          "administrator page runs every indexing step on the live server and reports which one fails, which "
          "made a deployment problem with the vector store visible within one click."),

    ("h2", "5.3 Frontend implementation"),
    ("h3", "5.3.1 Structure"),
    ("p", "The Next.js application keeps screens under app/ in route groups and reusable pieces in components/. "
          "Shared logic lives in lib/: the API helper (including the token-renewing fetch), the authentication "
          "context, the chat store, the reader's text formatter, a speech recognition hook and type "
          "definitions. The figures in this section are screenshots of the running application, signed in as a "
          "local test account with the book Mathematics for Machine Learning [[mml]] uploaded, so that no real "
          "student's documents appear in them."),
    ("h3", "5.3.2 Dashboard and documents"),
    ("p", "The dashboard ({fig:ui_dashboard}) follows the layout the team's designer produced: a welcome line, "
          "four quick actions (upload, start a chat, open the reader, start the tutor), recent documents with "
          "their status, today's study plan, a reader for the selected document and an AI assistant panel. "
          "Selecting a document in the list opens it in the reader; selecting text in the reader opens the "
          "explanation in the assistant panel; and the assistant's Sources tab moves the reader to a cited page. "
          "The documents page ({fig:ui_documents}) lists every file with its full name, size, date and status, "
          "with filters for status and folder, drag-and-drop upload, and one menu per document for reading, "
          "chatting, tutoring, revision sheets, searching, renaming, moving, retrying and deleting."),
    ("fig", "ui_dashboard", "ui_dashboard.png", "Dashboard of the running application", 6.25),
    ("fig", "ui_documents", "ui_documents.png", "Documents page with status, size and per-document actions", 6.25),
    ("h3", "5.3.3 Reader and explanations"),
    ("p", "The reader ({fig:ui_reader}) shows the rebuilt text of each page on a centred sheet, with the detected "
          "sections and the page list on the left. Selecting text shows an Explain with AI button; the "
          "explanation panel then gives the selection, a plain explanation, key points, an example, difficult "
          "terms, the pages it used and suggested follow-up questions. On a laptop the panel slides over the "
          "text and on a phone it becomes a bottom sheet."),
    ("fig", "ui_reader", "ui_reader_explain.png", "Reader with an explanation of a selected term", 6.25),
    ("h3", "5.3.4 Chat"),
    ("p", "In the chat, the answer streams in as it is generated. Under each answer the student sees Listen, "
          "Copy, the cited sources and the three rating buttons; less frequent actions (explain in Urdu or Roman "
          "Urdu, teach me this, save as flashcard, regenerate) are grouped in a labelled More menu so the row "
          "stays readable ({fig:ui_chat}). When the documents do not contain the answer, the application says "
          "so and shows no sources ({fig:ui_notfound})."),
    ("fig", "ui_chat", "ui_chat_cited.png", "Cited answer with its sources open", 6.25),
    ("fig", "ui_notfound", "ui_chat_notfound_new.png", "Answer when the information is not in the document", 6.25),
    ("h3", "5.3.5 Voice and language"),
    ("p", "Voice input uses the browser's built-in speech recognition, so no audio is uploaded for dictation. "
          "Spoken answers are produced on the server by Piper and returned as audio, with a cache so that the "
          "same text is not synthesised twice. For the cloned voice, the student records a sample in the "
          "browser (with pause and resume, a live waveform and a timer) or uploads one, listens to it, and must "
          "confirm that it is their own voice or that they have permission before it is uploaded; the server "
          "rejects samples without that confirmation ({fig:ui_voice}). Silent, too short and too long "
          "recordings are rejected before upload. Urdu and Roman Urdu explanations are shown under the English "
          "answer, with right-to-left layout for Urdu script."),
    ("fig", "ui_voice", "ui_voice_settings.png", "Voice settings with in-browser recording", 6.25),
    ("h3", "5.3.6 Study tools"),
    ("p", "The tutor start screen ({fig:ui_tutor}) asks for a topic, the documents to learn from, a level and a "
          "language, and lists past sessions with how many concepts were mastered. In a session the tutor "
          "shows the current concept and the Hint, Just tell me and Skip controls. Quizzes and the daily "
          "flashcard review share one page ({fig:ui_quizzes}). The study plan screen lays out the sessions up "
          "to the exam date, and practice papers and revision sheets each have their own pages, with a note "
          "that they are AI-generated study aids; revision sheets download as server-generated PDFs."),
    ("fig", "ui_tutor", "ui_tutor_start.png", "Tutor mode start screen", 6.25),
    ("fig", "ui_quizzes", "ui_quizzes.png", "Quizzes and daily review", 6.25),
    ("h3", "5.3.7 Responsive layout, administration and mobile client"),
    ("p", "Every screen was checked at phone, tablet, laptop and wide-monitor widths. On a phone the navigation "
          "rail becomes a drawer and the dashboard panels stack ({fig:ui_mobile}). The administration console "
          "is a set of pages under /admin with its own login. It lists users and lets an administrator block or "
          "unblock an account, change its plan, set per-user limit overrides, reset usage, add notes, verify an "
          "email manually, or sign in as the user for support (written to the audit log). Other pages cover "
          "plans and their limits, reported content, system health with the search-index check, and platform "
          "configuration. The Flutter client reuses the same API for sign-in, document upload, chat, study "
          "features and voice settings."),
    ("fig", "ui_mobile", "ui_mobile.png", "Dashboard on a phone-sized screen", 2.6),

    ("h2", "5.4 Key implementation challenges"),
    ("h3", "5.4.1 Running on a very small host"),
    ("p", "The first version used sentence-transformers with PyTorch for embeddings. PyTorch alone added about "
          "400 MB to the process, which was fine on a development machine and reliably killed the process on a "
          "512 MB free host at the first upload. Moving to the same model through ONNX Runtime (fastembed) "
          "gave numerically identical vectors in our check (cosine similarity of 1.0 on test sentences) at a fraction of the memory. The default batch size of "
          "256 then still reached about 1.2 GB when embedding a long document; a batch of 16 peaked at roughly "
          "280 MB. OCR had a similar problem: loading the OCR engine for every PDF was enough to run out of "
          "memory, which is why it is now used only when most pages have no text."),
    ("h3", "5.4.2 Numbers are invisible to embeddings"),
    ("p", "The most instructive problem came late. With seven volumes of Sahih Muslim uploaded, asking \"tell "
          "me about 240 hadees\" returned \"I couldn't find this in the document\", although the text of "
          "hadith 240 was in the index. The cause was in retrieval: an embedding model captures what a text is "
          "about, and the number 240 carries almost no meaning, so the closest chunks were passages about the "
          "author's biography. There were two further complications. The collection prints several numbers per "
          "entry (\"[386] 240 - (153)\"), and an entry can run across a page break, so even a correct hit "
          "returned half a hadith. The fix is the hybrid retrieval described in Section 5.2.4; Chapter 6 "
          "measures the same method on a textbook, where it raised the retrieval of exact passages from 23 "
          "to 60 of 60."),
    ("h3", "5.4.3 Rate limits and empty replies"),
    ("p", "The answer model on the plan we used allows 8,000 tokens per minute. A first version of the "
          "hybrid retrieval raised the amount of context and hit that limit within two questions, at which "
          "point the Gemini fallback answered instead. Capping the context at 9,000 characters and letting "
          "pinned passages take priority solved this without losing the exact match. The empty reply case "
          "described in Section 5.2.2 was found the same way."),
    ("h3", "5.4.4 Cookies across domains"),
    ("p", "In the deployed setup the web client is served from one domain and the API from another. A refresh "
          "cookie with SameSite=Lax is never sent on a cross-site request, so the session silently ended at "
          "every page reload once the 15-minute access token was lost. Setting SameSite=None with Secure and "
          "limiting the cookie to the /auth path fixed it."),

    ("h3", "5.4.5 Text that is easy to search is hard to read"),
    ("p", "Text extracted from PDFs is well suited to search but poor to read: one printed line per line break, "
          "the chapter title on every page and page numbers in the middle of sentences. Showing it directly made "
          "the reader look broken. The formatter described in Section 4.6.3 rebuilds paragraphs, headings and "
          "code blocks in the browser; the stored text is unchanged, so retrieval and citations are not "
          "affected."),
    ("h3", "5.4.6 Differences between the local and the deployed system"),
    ("p", "Two problems appeared only after deployment. Uploads that worked locally failed online at the "
          "indexing step, because the deployed backend stores vectors in Qdrant Cloud, which local testing never "
          "touched, and the free cluster had become unavailable; the administrator health check was added so "
          "that the failing step and its error are shown directly. Separately, the voice-cloning provider "
          "started refusing new voice models once the account reached its limit; this is now reported plainly "
          "and the standard voice is used. Both taught us to test the deployed configuration, not only the local "
          "one."),
    ("h3", "5.4.7 Expired sessions during streaming"),
    ("p", "Students reported \"Invalid or expired token\" when sending a question after some time in the "
          "application. The shared API helper renewed expired tokens, but the streamed chat request, uploads, "
          "exports and audio requests called the browser's fetch directly. All of them now use one helper that "
          "renews and retries, and tokens are renewed in the background as well."),

    ("h2", "5.5 Deployment"),
    ("p", "The repository includes a Render blueprint for the backend, which installs the requirements and runs "
          "the Alembic migrations at build time, and the frontend deploys to Vercel with the API address "
          "supplied as an environment variable. PostgreSQL can be a free Neon or Supabase instance. Because "
          "the free web host has no persistent disk, the vector store can be switched to Qdrant Cloud by setting "
          "two environment variables. For self-hosting there is a Docker Compose file with a Caddy reverse "
          "proxy. Secrets (database URL, provider keys, JWT secret) are environment variables and are not in "
          "the repository. Appendix A lists the steps for a local installation."),
]

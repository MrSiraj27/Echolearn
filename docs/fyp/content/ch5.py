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
          "19,000 lines of Python and 16,000 lines of TypeScript, in 51 commits made between 31 August and "
          "10 October 2026."),

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

    ("h2", "5.3 Frontend implementation"),
    ("h3", "5.3.1 Structure"),
    ("p", "The Next.js application keeps screens under app/ in route groups and reusable pieces in components/. "
          "Shared logic lives in lib/: the API helper, the authentication context, the chat store, a speech "
          "recognition hook and type definitions. The interface figures in this section are renders of the "
          "screens with sample content (a biology textbook), produced for this report, so that no real "
          "student's documents appear in it."),
    ("h3", "5.3.2 Documents and chat"),
    ("p", "The documents screen accepts several files at once, shows a progress bar and a status badge for "
          "each, and displays the generated summary and suggested questions when the first file is ready "
          "({fig:ui_upload}). In the chat, the answer streams in as it is generated. Under each answer the "
          "student sees the cited pages as chips; clicking one opens the source viewer with the passage "
          "highlighted ({fig:ui_source}). Each answer also has actions to listen, copy, and \"teach me this\" "
          "(which starts a tutor session on the topic)."),
    ("fig", "ui_upload", "ui_upload.png", "Document upload with progress, summary and suggested questions "
                                          "(interface render with sample content)", 5.6),
    ("fig", "ui_source", "ui_chat_source.png", "Cited answer with the source page open and the passage highlighted "
                                               "(interface render with sample content)", 5.6),
    ("p", "When the documents do not contain the answer, the application says so, as in {fig:ui_notfound}, and "
          "shows no source chips."),
    ("fig", "ui_notfound", "ui_chat_notfound.png", "Answer when the information is not in the documents "
                                                   "(interface render with sample content)", 5.6),
    ("h3", "5.3.3 Voice and language"),
    ("p", "Voice input uses the browser's built-in speech recognition, so no audio is uploaded for dictation. "
          "Spoken answers are produced on the server by Piper and returned as audio, with a cache so that the "
          "same text is not synthesised twice. A user who has uploaded a short voice sample can have answers "
          "read in a cloned voice through the Fish Audio service. The Urdu and Roman Urdu explanations are "
          "shown under the English answer through a language switcher, with right-to-left layout for Urdu "
          "script ({fig:ui_urdu})."),
    ("fig", "ui_voice", "ui_voice.png", "Voice question and spoken answer (interface render with sample content)", 5.6),
    ("fig", "ui_urdu", "ui_urdu.png", "Roman Urdu explanation of an answer (interface render with sample content)", 5.6),
    ("h3", "5.3.4 Study tools"),
    ("p", "The study screens share the same visual language. The tutor screen shows the current concept, the "
          "question, the student's reply and the three controls Hint, Just tell me and Skip, with a counter "
          "of the hint level ({fig:ui_tutor}). The daily review screen shows one card at a time and the three "
          "rating buttons, together with the streak ({fig:ui_review}). The study plan screen lays out the "
          "days up to the exam, with the exam date highlighted ({fig:ui_plan})."),
    ("fig", "ui_tutor", "ui_tutor.png", "Tutor mode with a hint (interface render with sample content)", 5.6),
    ("fig", "ui_review", "ui_review.png", "Daily flashcard review with SM-2 ratings (interface render with "
                                          "sample content)", 5.6),
    ("fig", "ui_plan", "ui_studyplan.png", "Study plan leading up to an exam date (interface render with "
                                           "sample content)", 5.6),
    ("h3", "5.3.5 Practice papers and revision sheets"),
    ("p", "A practice paper and a one-page revision sheet are shown in {fig:ui_exam}. Both carry a note that "
          "they are AI-generated study aids. The revision sheet can be downloaded as a PDF that is produced on "
          "the server, and it can include a short \"watch out\" section built from the student's own wrong quiz "
          "answers and hard flashcards."),
    ("fig", "ui_exam", "ui_exam.png", "Practice paper and revision sheet (interface render with sample content)", 5.0),
    ("h3", "5.3.6 Administration console and mobile client"),
    ("p", "The administration console is a set of pages under /admin with its own login. It lists users and lets "
          "an administrator block or unblock an account, change its plan, set per-user limit overrides, reset "
          "usage, add notes, verify an email manually, or sign in as the user for support (this action is written to "
          "the audit log). Other pages cover plans and their limits, reported content, system health "
          "(job status and storage) and platform configuration. The Flutter client reuses the same API for "
          "sign-in, document upload, chat, study features and voice settings."),

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
          "returned half a hadith. The fix is the hybrid retrieval described in Section 5.2.4, and its effect "
          "is measured in Chapter 6."),
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

    ("h2", "5.5 Deployment"),
    ("p", "The repository includes a Render blueprint for the backend, which installs the requirements and runs "
          "the Alembic migrations at build time, and the frontend deploys to Vercel with the API address "
          "supplied as an environment variable. PostgreSQL can be a free Neon or Supabase instance. Because "
          "the free web host has no persistent disk, the vector store can be switched to Qdrant Cloud by setting "
          "two environment variables. For self-hosting there is a Docker Compose file with a Caddy reverse "
          "proxy. Secrets (database URL, provider keys, JWT secret) are environment variables and are not in "
          "the repository. Appendix A lists the steps for a local installation."),
]

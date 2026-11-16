"""Front matter strings and the appendices."""
import importlib.util
import os

TITLE = "EchoLearn: A Document-Grounded AI Study Assistant"
GROUP_ID = "BSCS-F25-[___]"
SUPERVISOR = "Mahreen Tariq"
MEMBERS = [
    ("03-134231-058", "Siraj Sadiq"),
    ("03-134231-043", "Ibrahim Abdul Sami"),
    ("03-134231-045", "Jarrar Hussain"),
]
COVER_DATE = "November 2026"
CERT_DATE = "[Date]"

DEDICATION = ("To our families, who put up with our schedules and our laptops at the dinner table. And to every "
              "student who has lost an hour looking for a single page.")

ACK = [
    "We would like to thank everyone who helped us finish this project. We are especially grateful to our "
    "supervisor, Ms Mahreen Tariq, for her guidance, her patience, and for asking the questions that made us "
    "test things we would otherwise have assumed.",
    "We also thank our parents, siblings and friends for their encouragement, and the students who tried early "
    "versions of EchoLearn and told us plainly what did not work.",
]

ABSTRACT = (
    "EchoLearn is a study assistant that answers questions from a student's own documents. A student uploads PDF, "
    "Word, PowerPoint, text, spreadsheet, image, audio or video files, and the system extracts the text (using OCR "
    "for scanned pages and Whisper for recordings), indexes it, and answers questions in text or voice. Every "
    "answer is tied to the pages it came from, and the system says so when the documents do not contain the "
    "answer. Documents can be read inside the application, where any selected word, sentence or formula is "
    "explained simply using the surrounding text. The same material is used to generate quizzes, flashcards "
    "scheduled with the SM-2 algorithm, study plans, a tutor mode that gives hints in steps, revision sheets and "
    "practice papers, and answers can be explained again in Urdu or Roman Urdu. The web client is built with "
    "Next.js, the backend with FastAPI and PostgreSQL, and a Flutter application provides a mobile client. Answers "
    "come from open-weight models served by Groq, with Gemini as a fallback. Because a purely semantic search could "
    "not find exact passages or numbered items, we combined vector search with BM25 keyword search and a "
    "reference lookup, merged by reciprocal rank fusion. On the 417-page textbook Mathematics for Machine "
    "Learning this raised the retrieval of exact passages from 23 of 60 to 60 of 60 at a cost of about one "
    "millisecond per query. On the same book, processed in about two minutes, every answer the system gave cited "
    "a correct page and every unanswerable question that reached the model was declined. An automated suite of 76 tests covers security, quotas, spaced repetition, chunking, status "
    "transitions, the reader and the API, and all pass. The system runs on free-tier hosting, whose daily model "
    "limits are its main constraint; a formal study with students is left as future work."
)

# ------------------------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "backend", "app", "rag", "prompts.py")


def _load_prompts() -> dict:
    spec = importlib.util.spec_from_file_location("echolearn_prompts", _PROMPTS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"grounding": mod.GROUNDING_SYSTEM_PROMPT, "analysis": mod.QUERY_ANALYSIS_PROMPT}


def appendices() -> list:
    prompts = _load_prompts()
    return [
        ("h1", "Appendices", {"numbered": False}),
        ("h2", "Appendix A: System Installation and Setup Guide"),
        ("h3", "A.1 Prerequisites"),
        ("p", "Python 3.11 or newer, Node.js 18 or newer, a PostgreSQL database (local or hosted), FFmpeg for audio "
              "and video, and API keys for Groq and for Gemini (the fallback model). Optional: the Piper voice "
              "model file for spoken answers, a Fish Audio key for voice cloning, and an email provider key for "
              "verification emails."),
        ("h3", "A.2 Installation steps"),
        ("ol", [
            "Clone the repository.",
            "From the repository root run: npm install. This installs the frontend packages, creates the backend "
            "virtual environment, installs the pinned requirements and copies the example environment files.",
            "Open backend/.env and set DATABASE_URL, JWT_SECRET, GROQ_API_KEY and GEMINI_API_KEY, and FFMPEG_PATH "
            "if FFmpeg is not on the PATH.",
            "Create the database tables: cd backend, then run python -m alembic upgrade head inside the virtual "
            "environment.",
            "Start the backend from the repository root with: npm run dev:backend. It listens on port 8000.",
            "Start the frontend in a second terminal with: npm run dev:frontend. Open http://localhost:3000.",
            "Optional: run the tests from the backend folder with: python -m unittest discover -s tests -t .",
        ]),
        ("h2", "Appendix B: Prompts"),
        ("p", "The first prompt is the system prompt that governs answers. {context} is replaced by the retrieved "
              "excerpts. The second prompt prepares a question for retrieval."),
        ("h3", "B.1 Answer system prompt"),
        ("code", prompts["grounding"].strip()),
        ("h3", "B.2 Query analysis prompt"),
        ("code", prompts["analysis"].strip()),
        ("h2", "Appendix C: Usability Questionnaire"),
        ("p", "This questionnaire is the instrument prepared for a future user study. It has not been "
              "administered, so no results from it appear in this report."),
        ("p", "Section 1: Usability (rate 1 to 5; 1 = strongly disagree, 5 = strongly agree)"),
        ("ul", [
            "The interface was easy to use without guidance.",
            "I could find all the features I needed.",
            "Uploading my files was straightforward and I understood their status.",
            "The answer appeared quickly enough.",
        ]),
        ("p", "Section 2: Answers and trust (rate 1 to 5)"),
        ("ul", [
            "The answers were relevant to my question.",
            "The cited pages supported the answer.",
            "I opened the source page to check an answer.",
            "When the system said it could not find something, that was the right response.",
        ]),
        ("p", "Section 3: Study features (rate 1 to 5)"),
        ("ul", [
            "The quizzes matched what I was studying.",
            "The daily review helped me remember the material.",
            "The study plan was realistic for the time I had.",
            "The tutor's hints were helpful without giving the answer away too early.",
            "The Urdu or Roman Urdu explanation was accurate and clear.",
        ]),
        ("p", "Section 4: Open questions"),
        ("ul", [
            "What was most useful?",
            "What was frustrating or confusing?",
            "What one feature would you add?",
        ]),
        ("h2", "Appendix D: Retrieval Evaluation Protocol"),
        ("ul", [
            "Document: Mathematics for Machine Learning, 417 pages, 1,226 chunks (about 1,000 characters, 150 "
            "overlap), uploaded through the application as the local test account.",
            "Random seed 2026. Concept questions: 20 fixed questions; correct pages are those holding the "
            "defining heading (pages 15 to 399), and a hit is within one page.",
            "Numbered labels: 60 drawn from the 221 Example, Definition and Theorem labels in the book, asked "
            "as \"What does {label} say?\"; a hit is a returned chunk containing the label, ignoring spaces.",
            "Phrase queries: 60 chunks with more than 400 characters; five consecutive words longer than three "
            "letters were taken from each.",
            "Depth: the top 8 chunks. System A: dense search. System B: hybrid retrieval with one phrasing (no "
            "language model in the loop).",
            "Metrics: correct page or chunk retrieved (strict); all five words present in any returned chunk "
            "(lenient); median time per query after warm-up.",
            "Answer evaluation (evidence/eval_mml.py): 22 answerable and 8 unanswerable questions through the "
            "full pipeline, 25 seconds apart, plus three Explain with AI selections.",
        ]),
    ]

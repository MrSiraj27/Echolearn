"""Chapter 6 (testing and evaluation) and Chapter 7 (conclusion). Test result cells that read
"@ID" are replaced at build time with the real outcome of the last test run."""

# (id, test case, expected result)
T_AUTH = [
    ("AUTH01", "Hash a password and verify the same password", "Verification succeeds"),
    ("AUTH02", "Verify a wrong password against the hash", "Verification fails"),
    ("AUTH03", "Hash the same password twice", "Two different bcrypt hashes; plaintext not present"),
    ("AUTH04", "Create an access token and decode it", "Subject is the user id; type is access"),
    ("AUTH05", "Check the lifetime of an access token", "Equal to the configured 15 minutes"),
    ("AUTH06", "Create a refresh token and decode it", "Type is refresh"),
    ("AUTH07", "Alter the last characters of a valid token", "Rejected with 401"),
    ("AUTH08", "Present a token whose expiry time has passed", "Rejected with 401"),
    ("AUTH09", "Present a token signed with a different secret", "Rejected"),
    ("AUTH10", "Make six login-style attempts under one key", "Sixth attempt rejected with 429"),
]
T_LIM = [
    ("LIM01", "User without a plan", "Schema defaults apply"),
    ("LIM02", "User on a plan with limits", "Plan values replace the defaults"),
    ("LIM03", "User with a custom limit for the same key", "Custom value wins over the plan"),
    ("LIM04", "Custom limit set to null", "Treated as unlimited (null)"),
]
T_SR = [
    ("SR01", "Two successful reviews of a new card", "Intervals of 1 day, then 6 days"),
    ("SR02", "Third successful review", "Interval is 6 multiplied by the ease factor, rounded"),
    ("SR03", "Review with quality 1 after three successes", "Repetitions reset to 0, interval 1 day"),
    ("SR04", "Thirty failing reviews in a row", "Ease factor never falls below 1.3"),
    ("SR05", "Next review date after a review", "Today plus the interval in days"),
]
T_CH = [
    ("CH01", "Chunk a long single-page text", "Several chunks, none above about 1,000 characters"),
    ("CH02", "Chunk a two-page document", "Every chunk keeps its page number and file name"),
    ("CH03", "Chunk a page that contains a table", "The table is one chunk of type table"),
    ("CH04", "Chunk timestamped transcript segments", "Chunks carry start and end times"),
    ("CH05", "Clean text with (cid:9) placeholders and a footer URL", "Placeholders and URL line removed"),
]
T_RET = [
    ("RET01", "Normalise \"tell me about 240 hadees\"", "Becomes \"tell me about 240 hadith\""),
    ("RET02", "Extract reference numbers from three questions", "240 and 1663 found; \"top 5 reasons\" has none"),
    ("RET03", "Extract page numbers", "\"explain page 168\" gives 168; \"summarise this\" gives none"),
    ("RET04", "Tokenise a noisy question", "Stop words and glyph placeholders removed"),
    ("RET05", "BM25 over three small chunks, query \"hadith 240\"", "Chunk holding [240] ranks first"),
    ("RET06", "Find markers for 240 in two numbering systems", "[240] is primary; \"240 - (153)\" secondary"),
    ("RET07", "Continuation of a chunk that ends a page", "First chunk of the next page is returned"),
    ("ST01", "Detect a greeting", "A reply is returned without retrieval"),
    ("ST02", "Detect a real study question", "Not treated as small talk"),
]
T_API = [
    ("API01", "GET /health", "200 with {\"status\": \"ok\"}"),
    ("API02", "GET five protected routes without a token", "401 for each"),
    ("API03", "GET /documents/ with a malformed token", "401"),
    ("API04", "GET /admin/users/ without a token", "401 or 403"),
    ("API05", "POST /auth/signup with an invalid email", "422, nothing created"),
    ("API06", "POST /auth/signup with a 5-character password", "422, nothing created"),
    ("API07", "POST /auth/login for an unknown account", "401 with a generic message"),
    ("API08", "GET /openapi.json", "200 and more than 100 documented paths"),
]


def _rows(items):
    return [[i, d, e, "@" + i] for i, d, e in items]


HDR = ["ID", "Test case", "Expected result", "Actual result"]
W = [0.7, 2.4, 2.2, 0.95]

BLOCKS = [
    ("h1", "Chapter 6: Testing and Evaluation"),
    ("h2", "6.1 Overview"),
    ("p", "Two kinds of evidence are reported in this chapter. The first is an automated test suite that checks the "
          "logic the rest of the system depends on: security, quotas, spaced repetition, chunking, retrieval "
          "helpers and the API's public behaviour. The second is a measured comparison of retrieval methods on a "
          "real, large document collection. We did not run a formal study with external users; this is stated in "
          "Section 6.5 and not hidden."),

    ("h2", "6.2 Functional testing"),
    ("p", "The suite is in backend/tests/test_core.py and uses Python's unittest. It contains 41 tests. They are "
          "written to be free of side effects: no test creates an account, sends an email, or writes to the "
          "database or the vector store. The eight HTTP tests call the running backend only on endpoints that are "
          "rejected before any state is changed. The suite was run on the final code; the actual-result column "
          "below is copied from that run."),
    ("h3", "6.2.1 Authentication and security"),
    ("table", "t_auth", "Authentication and security test cases", HDR, _rows(T_AUTH), W),
    ("h3", "6.2.2 Plans and quotas"),
    ("table", "t_lim", "Plan limit test cases", HDR, _rows(T_LIM), W),
    ("h3", "6.2.3 Spaced repetition"),
    ("table", "t_sr", "SM-2 spaced repetition test cases", HDR, _rows(T_SR), W),
    ("h3", "6.2.4 Document chunking"),
    ("table", "t_ch", "Chunking test cases", HDR, _rows(T_CH), W),
    ("h3", "6.2.5 Retrieval helpers and small talk"),
    ("table", "t_ret", "Retrieval helper test cases", HDR, _rows(T_RET), W),
    ("h3", "6.2.6 API behaviour"),
    ("table", "t_api", "API contract test cases", HDR, _rows(T_API), W),
    ("p", "One failure occurred during development and is worth recording. The first version of the login test "
          "used an email address on the reserved \".test\" domain and expected a 401. The server correctly "
          "answered 422, because the email validator rejects reserved domains before the login logic runs. The "
          "same mistake made the short-password test pass for the wrong reason. Both tests now use a normal "
          "domain, so each checks what its name says."),

    ("h2", "6.3 Retrieval evaluation"),
    ("h3", "6.3.1 Method"),
    ("p", "The test collection is seven PDF volumes of an English translation of Sahih Muslim, 3,762 pages in "
          "total, indexed by the application into 6,233 chunks. It is a hard case for a general-purpose "
          "retriever because the text is long, repetitive and full of numbered items."),
    ("p", "Two sets of queries were built automatically from the indexed text with a fixed random seed (2026)."),
    ("ul", [
        "Reference queries: 60 hadith numbers were sampled from the 6,328 numbers that appear as a bracketed "
        "marker in exactly one chunk, so that the correct chunk is unambiguous. Each number was asked in two "
        "forms: \"tell me about {n} hadees\" and \"what does hadith number {n} say\".",
        "Phrase queries: 60 chunks were sampled, and five consecutive words (longer than three letters) were "
        "taken from each, giving a question of the form \"what does it say about ...\".",
    ]),
    ("p", "Two systems were compared at the same depth (the top 8 chunks). System A is dense-only retrieval, which "
          "is how the application worked before this change. System B is the hybrid retrieval described in "
          "Chapter 4. The strict metric counts a hit only when the chunk that holds the marker or the sampled "
          "text is among the results. Because neighbouring chunks overlap by 150 characters, a second metric "
          "for phrase queries counts a hit when all five words appear in any returned chunk. No language model "
          "was involved, so the numbers measure retrieval and not answer wording."),
    ("h3", "6.3.2 Results"),
    ("table", "t_eval", "Retrieval results on the Sahih Muslim collection (top 8 chunks)",
     ["Query set (n = 60)", "Metric", "A: dense only", "B: hybrid"],
     [
         ["\"tell me about {n} hadees\"", "Correct chunk retrieved", "0 / 60 (0%)", "60 / 60 (100%)"],
         ["\"what does hadith number {n} say\"", "Correct chunk retrieved", "0 / 60 (0%)", "60 / 60 (100%)"],
         ["Reference queries, both forms", "Mean rank of the correct chunk", "not found", "1.0"],
         ["Five-word phrase", "Same chunk retrieved", "15 / 60 (25%)", "47 / 60 (78%)"],
         ["Five-word phrase", "All words in a returned chunk", "26 / 60 (43%)", "55 / 60 (92%)"],
         ["Median time per query (warm)", "Reference queries", "about 0.23 s", "about 0.40 s"],
         ["Median time per query (warm)", "Phrase queries", "about 0.22 s", "about 0.23 s"],
     ], [2.2, 1.75, 1.15, 1.15]),
    ("h3", "6.3.3 Discussion"),
    ("p", "Dense retrieval did not find a single numbered item. This is the behaviour that made the original "
          "\"240 hadees\" question fail, and it is a property of the method and not of one bad example. The hybrid "
          "system found all 60 and ranked each one first. This result should be read with care: the reference "
          "lookup was written for exactly this marker format, so the test shows that it works, not that "
          "retrieval is solved in general."),
    ("p", "The phrase queries are a fairer comparison, because neither system was built around them. Keyword "
          "search roughly tripled the strict hit rate (25% to 78%) and more than doubled the lenient one (43% to "
          "92%). They also favour keyword matching, since the queries reuse the document's own words. We did not "
          "build a paraphrase test set, so we make no claim about questions phrased very differently from the "
          "text."),
    ("p", "The cost is small. Hybrid retrieval added about 0.17 s to a reference query and nothing measurable to "
          "a phrase query. The first query on a new set of documents builds the keyword index; for the 6,233 "
          "chunks used here that took 0.9 s, and about 2.6 to 3.4 s for the whole first call including loading "
          "the chunks from the store."),

    ("h2", "6.4 Worked example"),
    ("p", "The question that started this work was \"tell me about 240 hadees\" asked over the seven-volume "
          "folder. Before the change the application replied \"I couldn't find this in your document(s)\". "
          "After the change, retrieval returned the entry [240] on page 168 together with its continuation on "
          "page 169, and the answer named the narrator and gave the text of the hadith, citing pages 168 and "
          "169. It also noted that the number 240 appears under other numbering systems in the same book. A "
          "follow-up, \"who narrated it and what is the lesson?\", was answered about the same hadith, since "
          "the number survived the query rewrite. A question that is not in the books at all (a recipe) "
          "returned \"I couldn't find this in the document\" and no sources."),

    ("h2", "6.5 Known issues and limitations"),
    ("ul", [
        "No user study. We have not measured whether students learn more with EchoLearn. The questionnaire in "
        "Appendix C is ready for such a study.",
        "One collection, one language. The retrieval evaluation uses a single English text. Results on notes, "
        "slides or Urdu documents are not measured.",
        "Generated material is not scored. The correctness of generated quizzes, flashcards and practice papers "
        "relies on the verification steps described in Chapter 4; we did not measure how often they are wrong.",
        "Speech and OCR quality are not measured. Transcription accuracy depends on audio quality and accent, and "
        "scanned pages are limited by a time budget.",
        "Reference lookup targets bracketed markers. Items numbered in other styles (for example \"Q7)\" or "
        "\"7.\") are found by keyword search but not pinned.",
        "Provider limits. The hosted answer model allows 8,000 tokens per minute on the plan used, so several "
        "simultaneous users would fall back to Gemini or wait.",
        "Single-instance assumptions. The keyword index and the rate limiter are held in the memory of one "
        "process. Running several backend instances would duplicate the index and share no rate-limit state.",
    ]),

    # ---------------------------------------------------------------- Chapter 7
    ("h1", "Chapter 7: Conclusion and Future Work"),
    ("h2", "7.1 Summary of work"),
    ("p", "EchoLearn was built to answer a simple frustration: the answer is somewhere in the student's own "
          "files, and the tools that could find it either guess or cost money. The result is a web and mobile "
          "application in which a student uploads documents of many kinds, asks questions in text or voice, and "
          "gets answers with the pages they came from. The same material feeds quizzes, flashcards scheduled with "
          "SM-2, a study plan, a guided tutor, revision sheets and practice papers, and explanations can be "
          "requested in Urdu or Roman Urdu."),
    ("p", "The main technical contribution is the retrieval pipeline. A purely semantic search could not find a "
          "numbered item, so the system combines vector search, keyword search and reference lookup, merges the "
          "rankings, and follows a passage across a page break. On a seven-volume collection this raised the "
          "retrieval of numbered items from 0 of 60 to 60 of 60 at a cost of about 0.17 seconds per query."),
    ("h2", "7.2 Evaluation of objectives"),
    ("p", "Going back to the objectives in Chapter 1: the full-stack application, with web, mobile and "
          "administration clients, was built and is deployable on free hosting. The processing of PDF, Office, "
          "text, CSV, image, audio and video files, including OCR and transcription, is implemented. Answers are "
          "produced by retrieval-augmented generation with page or timestamp citations, and the system declines "
          "when the information is missing. Quizzes, SM-2 flashcards, study plans, revision sheets and practice "
          "papers are generated from the uploaded material, and the tutor mode with its hint ladder is "
          "implemented. Voice input, spoken answers and Urdu or Roman Urdu explanations are available. Accounts, "
          "plans with limits and the administration console are complete. The testing objective was met for the "
          "core logic and for retrieval; it was not met for user outcomes, as explained in Section 6.5. The "
          "mobile client covers the main features and not every screen of the web client."),
    ("h2", "7.3 Lessons learned"),
    ("h3", "7.3.1 Measure retrieval instead of assuming it works"),
    ("p", "The system looked fine on questions in natural language and failed on a question that "
          "contained a number. Once we wrote the evaluation script, the failure was easy to quantify and easy "
          "to fix. We would now build the evaluation set at the start of a retrieval project, not at the end."),
    ("h3", "7.3.2 The hosting plan shapes the architecture"),
    ("p", "Memory limits, a sleeping host, a non-persistent disk and a token-per-minute cap each forced a "
          "design change: ONNX instead of PyTorch, a selectable vector store, a context cap and a fallback "
          "model. Deciding the target host first would have saved a rewrite."),
    ("h3", "7.3.3 Let the model choose, but let code verify"),
    ("p", "For generated study material the models are used to select and organise, and ordinary code checks the "
          "result: facts are matched to the chunk they came from, questions are checked against the passage they "
          "cite, and the final step picks items by identifier and does not rewrite them. This kept generated "
          "material tied to the documents."),
    ("h3", "7.3.4 Keep engines pure"),
    ("p", "Writing the tutor as an engine with no database access made it testable and made failures cheap, "
          "because state is saved after each step. The same split between logic and storage made the SM-2 and "
          "quota code easy to test."),
    ("h2", "7.4 Future work"),
    ("h3", "7.4.1 Urdu-native retrieval"),
    ("p", "Documents and questions in Urdu script need a multilingual embedding model and a tokeniser that "
          "handles Urdu for the keyword index. Today the Urdu support is an explanation layer over English "
          "retrieval."),
    ("h3", "7.4.2 A larger evaluation set"),
    ("p", "A set of questions written by students, including paraphrased and multi-step ones, over several "
          "subjects, with a reranking model compared against the current fusion."),
    ("h3", "7.4.3 A user study"),
    ("p", "A short study with students preparing for a real exam, comparing quiz scores and time spent with and "
          "without the application."),
    ("h3", "7.4.4 Shared state for multi-instance deployment"),
    ("p", "Moving the rate limiter and the keyword index to a shared store, so that more than one backend "
          "process can run."),
    ("h3", "7.4.5 Payments and teacher tools"),
    ("p", "Online checkout for the paid plan, and class-level analytics that show a teacher which topics are "
          "hard without exposing individual students' files."),
    ("h2", "7.5 Final remarks"),
    ("p", "The most useful finding of the project came from a failure: a simple question about a numbered item "
          "returned \"couldn't find this\", and that forced us to measure what we had only assumed. EchoLearn is "
          "not finished in the way a commercial product is, but it does what it set out to do, and the parts "
          "that do not work yet are written down in this report."),
]

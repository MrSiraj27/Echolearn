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
# Newer suites: (id, test method, test case, expected result); the result cell reads the method's outcome.
T_SM = [
    ("SM01", "test_complete_pending_sets_timestamp", "Complete a pending study session", "Status completed, completion time set"),
    ("SM02", "test_skip_pending_has_no_timestamp", "Skip a pending session", "Status skipped, no completion time"),
    ("SM03", "test_same_target_is_a_noop", "Complete an already completed session", "No change, no error"),
    ("SM04", "test_completed_cannot_be_skipped_and_vice_versa", "Skip a completed session, complete a skipped one", "Both rejected"),
    ("SM05", "test_cannot_reopen_a_session", "Move a finished session back to pending", "Rejected"),
    ("SM06", "test_sessions_of_abandoned_plan_are_frozen", "Change a session of an abandoned plan", "Rejected"),
    ("SM07", "test_last_pending_session_completes_the_plan", "Complete the last pending session", "Plan becomes completed"),
    ("SM08", "test_skipping_the_last_session_also_completes_the_plan", "Skip the last pending session", "Plan becomes completed"),
    ("SM09", "test_abandoned_plan_never_becomes_completed", "Finish all sessions of an abandoned plan", "Plan stays abandoned"),
    ("SM10", "test_require_active", "Edit a plan that is not active", "Rejected with 400"),
    ("SM11", "test_resolved_reports_cannot_be_resolved_again", "Resolve a moderation report twice", "Second attempt rejected"),
    ("SM12", "test_in_progress_documents_cannot_be_retried", "Administrator retries a document still parsing", "Rejected with 409"),
]
T_RR = [
    ("RR01", "test_kinds", "Classify a word, sentence, passage, code and formula", "Each gets the right selection type"),
    ("RR02", "test_window_around_selection", "Cut the context around a selection", "Window contains the selection and its neighbours"),
    ("RR03", "test_tolerates_whitespace_differences", "Selection with different line breaks", "Still located on the page"),
    ("RR04", "test_missing_selection_falls_back_to_page_start", "Selection not found on the page", "Start of the page is used"),
    ("RR05", "test_document_text_is_wrapped_as_data", "Build an explanation prompt", "Document text wrapped as data, never instructions"),
    ("RR06", "test_follow_up_uses_answer_schema", "Build a follow-up prompt", "Follow-up answer format requested"),
    ("RR07", "test_language_instruction", "Ask for Urdu output", "Language instruction included"),
    ("RR08", "test_parse_reply_handles_fences_and_noise", "Parse a reply with code fences and extra text", "JSON extracted"),
    ("RR09", "test_normalize_result", "Normalise an incomplete reply", "Missing fields filled, lists trimmed"),
    ("RR10", "test_corrupt_pdf", "Process a damaged PDF", "Failed with a \"damaged file\" reason"),
    ("RR11", "test_password_protected_pdf", "Process an encrypted PDF", "Failed with a \"password-protected\" reason"),
    ("RR12", "test_only_failed_documents_can_be_retried", "Retry a ready document", "Rejected"),
    ("RR13", "test_retry_without_original_file_is_refused", "Retry when the original file is gone", "Rejected with a clear message"),
    ("RR14", "test_retry_requeues_a_failed_document", "Retry a failed document", "Status reset, error cleared, job queued"),
    ("RR15", "test_rename_keeps_extension_and_rejects_slashes", "Rename a document", "Extension kept; slashes rejected"),
    ("RR16", "test_upload_without_consent_is_rejected_before_reading_the_file", "Upload a voice sample without consent", "Rejected before the file is read"),
    ("RR17", "test_only_assistant_answers_can_be_rated", "Rate a user's own message", "Rejected; only answers can be rated"),
    ("RR18", "test_limit_reached_is_unavailable_and_pauses", "Voice provider reports its model limit", "Cloning paused, plain message shown"),
    ("RR19", "test_rate_limit_pauses_briefly", "Voice provider rate-limits a request", "Short pause only"),
    ("RR20", "test_bad_request_is_a_per_request_failure_without_pause", "Voice provider rejects one request", "That request fails, no pause"),
    ("RR21", "test_verified_account_gets_existing_account_email_once_per_window", "Sign up twice with a verified address", "One reminder email per 15 minutes"),
    ("RR22", "test_throttle_ignores_case", "Same address in different letter case", "Treated as one address"),
    ("RR23", "test_unverified_account_still_gets_a_fresh_verification_link", "Sign up again before verifying", "New verification link sent"),
]


def _rows(items):
    return [[i, d, e, "@" + i] for i, d, e in items]


def _rows_named(items):
    return [[i, d, e, "@" + m] for i, m, d, e in items]


HDR = ["ID", "Test case", "Expected result", "Actual result"]
W = [0.7, 2.4, 2.2, 0.95]

BLOCKS = [
    ("h1", "Chapter 6: Testing and Evaluation"),
    ("h2", "6.1 Overview"),
    ("p", "Two kinds of evidence are reported in this chapter. The first is an automated test suite that checks the "
          "logic the rest of the system depends on: security, quotas, spaced repetition, chunking, retrieval "
          "helpers, status transitions, the reader and the API's public behaviour. The second is measurement on "
          "a real, large document, the 417-page textbook Mathematics for Machine Learning [[mml]]: a comparison "
          "of retrieval methods, and an end-to-end evaluation of processing, answers and explanations. We "
          "did not run a formal study with external users; this is stated in Section 6.6 and not hidden."),

    ("h2", "6.2 Functional testing"),
    ("p", "The suite uses Python's unittest and contains 76 tests in three files: test_core.py (41 tests of "
          "security, quotas, spaced repetition, chunking, retrieval helpers and the API), test_state_machines.py "
          "(12 tests of the status transitions) and test_reader_and_reliability.py (23 tests of the reader "
          "explanations, document failures, retry and rename, voice consent, feedback, the voice provider's "
          "limits and sign-up emails). They are written to be free of side effects: no test creates a real "
          "account, sends an email, or writes to the database or the vector store; the newer suites use small "
          "in-memory stand-ins for the database. The eight HTTP tests call the running backend only on endpoints "
          "that are rejected before any state is changed. The suite was run on the final code; the actual-result "
          "column below is copied from that run."),
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
    ("h3", "6.2.7 Status transitions"),
    ("table", "t_sm", "Study plan, moderation and retry transition test cases", HDR, _rows_named(T_SM), W),
    ("h3", "6.2.8 Reader, documents and reliability"),
    ("table", "t_rr", "Reader, document, voice and email test cases", HDR, _rows_named(T_RR), W),

    ("h2", "6.3 Retrieval evaluation"),
    ("h3", "6.3.1 Method"),
    ("p", "The test document is the textbook Mathematics for Machine Learning [[mml]]: 417 pages, uploaded "
          "through the application and indexed into 1,226 chunks. It is a demanding case for a retriever: "
          "it is long, full of formulas, and refers to its own numbered examples, definitions and theorems. "
          "The PDF text extractor also drops many spaces in this book (\"thecolumnrankequalstherowrank\"), "
          "which is common in typeset PDFs and makes the text harder to match."),
    ("p", "Three sets of queries were built automatically from the indexed text with a fixed random seed "
          "(2026), so that the test is repeatable and not chosen by hand."),
    ("ul", [
        "Concept questions: 20 questions in ordinary language, such as \"What is a conjugate prior?\" or "
        "\"How does backpropagation compute gradients?\". The correct pages are those whose text holds the "
        "defining heading; a hit is a returned chunk within one page of a correct page.",
        "Numbered labels: the book contains 221 distinct labels of the form Example, Definition or Theorem "
        "followed by a number. 60 were sampled and asked as \"What does Example 4.5 say?\"; a hit is a "
        "returned chunk that contains the label.",
        "Exact phrases: 60 chunks were sampled, and five consecutive words longer than three letters were "
        "taken from each, giving a question of the form \"what does it say about ...\".",
    ]),
    ("p", "Two systems were compared at the same depth (the top 8 chunks). System A is dense-only retrieval, "
          "which is how the application worked before this change. System B is the hybrid retrieval described "
          "in Chapter 4. For phrase queries, the strict metric counts a hit only when the sampled chunk itself "
          "is returned, and the lenient metric when all five words appear in any returned chunk. No language "
          "model was involved, so the numbers measure retrieval and not answer wording. The script and its raw "
          "output are kept in evidence/eval_mml_retrieval.py and eval_mml_retrieval.json."),
    ("h3", "6.3.2 Results"),
    ("table", "t_eval", "Retrieval results on Mathematics for Machine Learning (top 8 chunks)",
     ["Query set", "Metric", "A: dense only", "B: hybrid"],
     [
         ["Concept questions (n = 20)", "Correct page retrieved", "20 / 20 (100%)", "20 / 20 (100%)"],
         ["Numbered labels (n = 60)", "Chunk with the label retrieved", "6 / 60 (10%)", "13 / 60 (22%)"],
         ["Exact phrases (n = 60)", "Same chunk retrieved", "23 / 60 (38%)", "60 / 60 (100%)"],
         ["Exact phrases (n = 60)", "All words in a returned chunk", "25 / 60 (42%)", "60 / 60 (100%)"],
         ["Median time per query (warm)", "Concept questions", "28 ms", "28 ms"],
         ["Median time per query (warm)", "Numbered labels", "44 ms", "45 ms"],
         ["Median time per query (warm)", "Exact phrases", "28 ms", "29 ms"],
     ], [2.0, 1.95, 1.15, 1.15]),
    ("h3", "6.3.3 Discussion"),
    ("p", "On questions written in ordinary language both systems found the right pages every time. These "
          "questions use the book's own vocabulary, which is exactly what meaning-based search is good at, and "
          "adding keyword search did not disturb those results."),
    ("p", "The difference appears when the question depends on exact wording. Dense retrieval found the sampled "
          "passage for only 23 of 60 phrase queries, because a vector captures the general topic of a passage "
          "and many passages in a textbook share a topic. Hybrid retrieval found all 60, because the keyword "
          "index matches the rare words of the phrase directly. The same mechanism doubled the hit rate for "
          "numbered labels, from 6 to 13 of 60, but most labels were still missed. A label such as \"Example "
          "4.5\" is extracted as \"Example4.5\", which the keyword index stores as a different token, and the "
          "reference lookup was written for bracketed markers such as [240] rather than for labels. This is "
          "the clearest weakness found by the evaluation and is listed as future work."),
    ("p", "The cost is negligible. Hybrid retrieval added at most 1 ms per query once warm. The first query on "
          "a document builds its keyword index; for the 1,226 chunks of this book the whole first call, "
          "including loading the chunks from the store, took 1.9 s."),

    ("h2", "6.4 Answer and explanation evaluation"),
    ("h3", "6.4.1 Method"),
    ("p", "The same textbook (17.6 MB) was used to test the whole pipeline as a student meets it. It was "
          "uploaded through the application as the local test account, with the same configuration as normal "
          "use. The script evidence/eval_mml.py then ran the checks below against the processed document; its "
          "raw output is kept in evidence/eval_mml.json."),
    ("ul", [
        "Processing: the time from upload to the document becoming ready, and the number of chunks produced.",
        "Answers: 22 questions (the 20 concept questions of Section 6.3 and two numbered references, \"What "
        "does Example 4.5 compute?\" and \"What does Definition 6.13 define?\") through the full answer "
        "pipeline, recording whether an answer was given, "
        "whether a cited page is correct, whether the answer contains the expected key terms, and the time "
        "taken. A further 8 questions have no answer in the book (a football team, ChatGPT, a recipe, a stock "
        "price and similar) and should be declined.",
        "Explanations: the reader's Explain with AI on a term (\"positive definite\"), a sentence from the "
        "conjugate-prior page and a formula line from the SVD section.",
    ]),
    ("p", "Questions were sent one at a time with a 25-second pause between them so that the answer model's "
          "8,000 tokens-per-minute limit was respected. The model provider used for every call was recorded."),
    ("h3", "6.4.2 Results"),
    ("table", "t_mml", "Results on Mathematics for Machine Learning (417 pages)",
     ["Measure", "Result"],
     [
         ["Upload to ready (parse, chunk, embed, index)", "128 s; indexed after 123 s"],
         ["Chunks produced", "1,226"],
         ["Answers given with a correct page cited", "19 / 22"],
         ["Answers containing all expected key terms", "17 / 19 (the other 2 correct, given as formulas)"],
         ["Correctly declined (not found in the excerpts)", "1 / 22 (Definition 6.13, see 6.4.3)"],
         ["Failed with a provider error", "2 / 22"],
         ["Median answer time / slowest answer", "3.7 s / 61.4 s"],
         ["Unanswerable questions correctly declined", "7 / 8 (1 provider error, no wrong answer)"],
         ["Explain with AI: usable explanation", "2 / 3 (1 provider error)"],
         ["Model calls in the run: Groq", "77 succeeded, 9 failed"],
         ["Model calls in the run: Gemini fallback", "5 succeeded, 4 failed"],
     ], [3.75, 2.5]),
    ("h3", "6.4.3 Discussion"),
    ("p", "Every answer the system gave cited a correct page: 19 of 19. Two answers did not contain every "
          "expected term, but both were correct: the orthogonal matrix was defined by AA\u1d40 = I = A\u1d40A, and "
          "Bayes' theorem was given as p(x | y) = p(y | x) p(x) / p(y), which a word-matching check cannot "
          "credit. All seven unanswerable questions that reached the model were declined with no sources, so "
          "the system did not invent an answer once. Explanations took between 1 and 9 seconds and each "
          "contained four key points and an example. One weakness showed: the formula line was classified as "
          "code, because it held only symbols and an equation number; the explanation was still correct."),
    ("p", "The two numbered references were not answered, for the reason found in Section 6.3: the passages "
          "holding Example 4.5 and Definition 6.13 were not retrieved. For Definition 6.13 the model said that "
          "the excerpts did not contain it rather than guessing."),
    ("p", "The four failed calls all came from provider quotas, not from the application. By the end of the run "
          "the free Groq plan's daily allowance of 200,000 tokens was used up, and the free Gemini fallback "
          "had reached its daily request limit, so the last calls had no model to go to. The application "
          "handled this as designed: it showed an error with a retry hint instead of an answer, and nothing "
          "wrong was shown to the user. The questions asked in the application earlier the same day, before "
          "the quota was used, were all answered (Section 6.5). The result is still a real limit of "
          "free-tier hosting and is recorded in Section 6.6."),

    ("h2", "6.5 Worked example: studying from the textbook"),
    ("p", "A team member used EchoLearn on Mathematics for Machine Learning as a student would and exported the "
          "chat. Asked to define the rank of a matrix, the system answered with the number of linearly "
          "independent rows or columns, gave a small example and cited page 53. Asked to explain eigenvalues and "
          "eigenvectors for a beginner, it gave the eigenvalue equation Ax = \u03bbx (page 111) and then worked "
          "through the book's Example 4.5 step by step: the characteristic polynomial, the eigenvalues 2 and 5, "
          "and an eigenvector for each, citing pages 111 to 113. A follow-up, \"How is PCA connected to "
          "eigenvectors?\", linked the covariance matrix, its eigen-decomposition and the projection onto the "
          "top eigenvectors, citing pages 340 to 349. \"What does conjugate prior mean?\" was answered from "
          "Definition 6.13 on page 214, and a question on gradient descent explained the update rule and the "
          "effect of a step size that is too small or too large, from pages 234 to 238. Two questions with no "
          "answer in the book, the author's favourite football team and what the book says about ChatGPT, "
          "were both declined."),

    ("h2", "6.6 Known issues and limitations"),
    ("ul", [
        "No user study. We have not measured whether students learn more with EchoLearn. The questionnaire in "
        "Appendix C is ready for such a study.",
        "One document, one language. The evaluations use one English textbook. Results on handwritten "
        "notes, slides or Urdu documents are not measured.",
        "Numbered labels in text. References such as \"Example 4.5\" or \"Definition 6.13\" are not pinned by "
        "the reference lookup, and missing spaces in some PDFs' extracted text weaken keyword search for them.",
        "Generated material is not scored. The correctness of generated quizzes, flashcards and practice papers "
        "relies on the verification steps described in Chapter 4; we did not measure how often they are wrong.",
        "Speech and OCR quality are not measured. Transcription accuracy depends on audio quality and accent, and "
        "scanned pages are limited by a time budget.",
        "Reference lookup targets bracketed markers. Items numbered in other styles (for example \"Q7)\" or "
        "\"7.\") are found by keyword search but not pinned.",
        "Provider limits. On the free plan used, the answer model allows 8,000 tokens per minute and 200,000 "
        "tokens per day, and the Gemini fallback only a small number of requests per day. The textbook "
        "evaluation reached both daily limits, so a deployment for many students needs a paid plan.",
        "Single-instance assumptions. The keyword index and the rate limiter are held in the memory of one "
        "process. Running several backend instances would duplicate the index and share no rate-limit state.",
    ]),

    # ---------------------------------------------------------------- Chapter 7
    ("h1", "Chapter 7: Conclusion and Future Work"),
    ("h2", "7.1 Summary of work"),
    ("p", "EchoLearn was built to answer a simple frustration: the answer is somewhere in the student's own "
          "files, and the tools that could find it either guess or cost money. The result is a web and mobile "
          "application in which a student uploads documents of many kinds, asks questions in text or voice, and "
          "gets answers with the pages they came from. Documents can be read inside the application, and any "
          "selected word, sentence or formula can be explained in simple terms. The same material feeds quizzes, "
          "flashcards scheduled with SM-2, a study plan, a guided tutor, revision sheets and practice papers, "
          "and explanations can be requested in Urdu or Roman Urdu."),
    ("p", "The main technical contribution is the retrieval pipeline. A purely semantic search could not find a "
          "numbered item, so the system combines vector search, keyword search and reference lookup, merges the "
          "rankings, and follows a passage across a page break. This raised the retrieval of exact passages in a "
          "417-page textbook from 23 of 60 to 60 of 60 at a cost of about one "
          "millisecond per query. On the same book, processed in about two minutes, every answer the system "
          "gave cited a correct page, and every question without an answer in the book was declined."),
    ("h2", "7.2 Evaluation of objectives"),
    ("p", "Going back to the objectives in Chapter 1: the full-stack application, with web, mobile and "
          "administration clients, was built and is deployable on free hosting. The processing of PDF, Office, "
          "text, CSV, image, audio and video files, including OCR and transcription, is implemented. Answers are "
          "produced by retrieval-augmented generation with page or timestamp citations, and the system declines "
          "when the information is missing. Quizzes, SM-2 flashcards, study plans, revision sheets and practice "
          "papers are generated from the uploaded material, and the tutor mode with its hint ladder is "
          "implemented, and so is the document reader with explanations of selected text. Voice input, spoken "
          "answers, a cloned voice recorded with consent, and Urdu or Roman Urdu explanations are available. Accounts, "
          "plans with limits and the administration console are complete. The testing objective was met for the "
          "core logic (76 automated tests, all passing), for retrieval and for answers on a real textbook; it was not met for user outcomes, as explained in Section 6.6. The "
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
    ("h3", "7.3.4 Make every status change explicit"),
    ("p", "Several bugs came from statuses whose allowed changes were only implied: a session that could be "
          "reopened, a job left \"processing\" forever after a restart, a document retried while still being "
          "parsed. Writing the transitions down in one place and marking interrupted jobs as failed at start-up "
          "removed a whole class of problems that were hard to see in testing."),
    ("h3", "7.3.5 Test the deployed configuration"),
    ("p", "Two failures appeared only online: a vector store that local testing never used, and a voice provider "
          "that reached its account limit. An administrator page that runs each step on the live server turned "
          "a vague \"upload failed\" into a precise cause within one click."),
    ("h3", "7.3.6 Keep engines pure"),
    ("p", "Writing the tutor as an engine with no database access made it testable and made failures cheap, "
          "because state is saved after each step. The same split between logic and storage made the SM-2 and "
          "quota code easy to test."),
    ("h2", "7.4 Future work"),
    ("h3", "7.4.1 Urdu-native retrieval"),
    ("p", "Documents and questions in Urdu script need a multilingual embedding model and a tokeniser that "
          "handles Urdu for the keyword index. Today the Urdu support is an explanation layer over English "
          "retrieval."),
    ("h3", "7.4.2 Lookup of labelled items"),
    ("p", "Extending the reference lookup from bracketed markers to labels such as Example 4.5, Definition 6.13, "
          "Theorem 2 or Section 3.1, and repairing words that the PDF extractor joins together, so that a "
          "question that names a numbered item in a textbook finds it directly."),
    ("h3", "7.4.3 A larger evaluation set"),
    ("p", "A set of questions written by students, including paraphrased and multi-step ones, over several "
          "subjects, with a reranking model compared against the current fusion."),
    ("h3", "7.4.4 A user study"),
    ("p", "A short study with students preparing for a real exam, comparing quiz scores and time spent with and "
          "without the application."),
    ("h3", "7.4.5 Shared state and paid model capacity"),
    ("p", "Moving the rate limiter and the keyword index to a shared store, so that more than one backend "
          "process can run, and moving the answer model to a paid tier so that daily token limits do not stop "
          "a class of students mid-session."),
    ("h3", "7.4.6 Payments and teacher tools"),
    ("p", "Online checkout for the paid plan, and class-level analytics that show a teacher which topics are "
          "hard without exposing individual students' files."),
    ("h2", "7.5 Final remarks"),
    ("p", "The most useful finding of the project came from a failure: a simple question about a numbered item "
          "returned \"couldn't find this\", and that forced us to measure what we had only assumed. EchoLearn is "
          "not finished in the way a commercial product is, but it does what it set out to do, and the parts "
          "that do not work yet are written down in this report."),
]

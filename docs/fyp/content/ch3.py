"""Chapter 3: Literature review."""

BLOCKS = [
    ("h1", "Chapter 3: Literature Review"),
    ("h2", "3.1 Introduction"),
    ("p", "This chapter looks at the work that EchoLearn builds on. It starts with the tools students already use "
          "to study from documents, then covers the research behind retrieval-augmented generation, the use of "
          "large language models in education, and the learning-science findings that justify quizzes, spacing and "
          "tutoring. The last part describes the technical frameworks we chose and why. {tbl:litreview} collects the "
          "main sources."),

    ("h2", "3.2 Existing tools for studying from documents"),
    ("p", "Three kinds of tools overlap with what EchoLearn does. Document-chat tools such as ChatPDF [[chatpdf]] "
          "and Google's NotebookLM [[notebooklm]] let a user load sources and ask questions about them. Flashcard "
          "tools such as Quizlet [[quizlet]] and Anki [[anki]] help with memorising. General chatbots answer "
          "almost anything but are not tied to a particular document. Our comparison is based on what each tool "
          "is mainly designed to do and not on a feature-by-feature audit, which would be out of date within a "
          "few months."),
    ("h3", "3.2.1 The grounding gap"),
    ("p", "A general chatbot answers from its training data. For a question about a student's own lecture notes "
          "that is the wrong source: the notes may use a lecturer's own terminology, a different numbering or "
          "recent material the model never saw. Document-chat tools address this by retrieving passages first. "
          "What we found missing in practice was handling of references. Students ask for \"hadith 240\", "
          "\"question 7\" or \"page 12\", and a system that searches only by meaning treats the number as a "
          "nearly meaningless token. Chapter 6 measures this problem on a real collection."),
    ("h3", "3.2.2 The practice gap"),
    ("p", "Finding an answer is not the same as learning it. Flashcard tools handle repetition well, but the "
          "student has to write the cards. Document-chat tools handle lookup, but the conversation ends when the "
          "answer is read. EchoLearn connects the two: the same indexed pages are used to generate quizzes, "
          "flashcards that return on a schedule, a study plan with a daily target, and a tutor that asks before "
          "it tells."),

    ("h2", "3.3 Retrieval-augmented generation"),
    ("p", "Lewis et al. [[lewis2020]] combined a pretrained sequence-to-sequence model with a dense vector index "
          "of Wikipedia and showed that generation conditioned on retrieved passages was more factual on "
          "knowledge-intensive tasks than the same model alone. This is the architecture EchoLearn follows, with "
          "the student's documents in place of Wikipedia."),
    ("p", "Retrieval itself comes in two families. Sparse methods such as BM25 score a passage by how many of the "
          "query's words it contains, weighted by how rare each word is and normalised for passage length "
          "[[robertson2009]]. Dense methods encode the query and the passage into vectors with a neural encoder and "
          "compare them; Karpukhin et al. [[karpukhin2020]] showed that a dense retriever can beat BM25 on "
          "open-domain question answering. The two behave differently. Dense retrieval matches meaning and "
          "survives paraphrase, but it is weak on exact strings, numbers and rare names. BM25 is the opposite. "
          "Karpukhin et al. themselves reported that BM25 stayed stronger on a dataset where the questions share "
          "many words with the passage."),
    ("p", "Because the weaknesses differ, systems often use both and merge the rankings. Reciprocal rank fusion "
          "[[cormack2009]] does this without any training: each list contributes 1/(k + rank) to a passage's "
          "score, with k = 60 in the original paper, and the passages are sorted by the sum. EchoLearn uses this "
          "method to combine the vector search with a keyword search. The embedding model it uses is all-MiniLM-"
          "L6-v2, a sentence-transformer [[reimers2019]] built on the distilled MiniLM architecture [[wang2020]], "
          "which produces 384-dimensional vectors and is small enough to run on a CPU."),

    ("h2", "3.4 Large language models in education"),
    ("p", "Large language models rest on the transformer architecture [[vaswani2017]]. Kasneci et al. [[kasneci2023]] "
          "surveyed their use in education and described both the opportunities (personalised explanation, "
          "feedback, content generation) and the risks (over-reliance, bias, and factual errors). Mollick and "
          "Mollick [[mollick2023]] described seven ways of using AI in teaching, including as tutor, coach and "
          "tool, with example prompts. Both lines of work support using a model as an assistant while keeping the "
          "student responsible for checking the result."),
    ("p", "The main technical risk is hallucination, where a model produces fluent text that is not supported by "
          "its input or by fact [[ji2023]]. In education the cost of an invented detail is high because the student "
          "may memorise it. Grounding the answer in retrieved passages and letting the system refuse are the two "
          "mitigations EchoLearn relies on."),
    ("h3", "3.4.1 Open-weight models served through Groq"),
    ("p", "The answer model in EchoLearn is gpt-oss-120b and the smaller gpt-oss-20b handles query rewriting, "
          "relevance grading and follow-up suggestions. These are open-weight reasoning models released under "
          "the Apache 2.0 licence [[openai2025]], and Groq serves them through a hosted API with low latency "
          "[[groq]]. We chose them because they are free to use at student scale and because the same models can "
          "later be self-hosted if the platform outgrows the hosted free tier. Gemini is configured as a fallback "
          "for when the primary call fails or hits a rate limit."),
    ("h3", "3.4.2 Prompting for grounded answers"),
    ("p", "The system prompt tells the model to use only the supplied excerpts, to say so when the answer is not "
          "there, to match the depth of the answer to the question, to cite pages, and to reply in the language "
          "of the question. We also found that short, explicit rules about numbered items were needed: books such "
          "as hadith collections print several numbers on one entry (for example \"[386] 240 - (153)\"), and "
          "without a rule the model confused them. The prompt is reproduced in Appendix B."),

    ("h2", "3.5 Learning science behind the study tools"),
    ("p", "Three findings from cognitive psychology shaped the study features. The first is the testing effect: "
          "retrieving information from memory improves long-term retention more than studying it again "
          "[[roediger2006]]. This is why EchoLearn generates quizzes and questions-first tutoring and not only "
          "summaries. The second is the spacing effect: reviews spread over time work better than the same "
          "reviews massed together [[cepeda2006]], which is a consequence of the forgetting curve first described "
          "by Ebbinghaus [[ebbinghaus1885]]. The SM-2 algorithm [[wozniak1990]] turns this into a schedule by "
          "growing the interval after each successful recall and resetting it after a failure. EchoLearn "
          "implements SM-2 for its daily flashcard review."),
    ("p", "The third is tutoring. Bloom reported that students taught one-to-one performed about two standard "
          "deviations better than students in a conventional classroom [[bloom1984]]. A later review found that "
          "computer tutors which give feedback at the level of individual steps came close to human tutors "
          "[[vanlehn2011]]. The tutor mode in EchoLearn follows that pattern: it asks a question, checks the "
          "student's answer against the passages, and offers hints in graded steps before it gives the answer."),

    ("h2", "3.6 Speech and language support"),
    ("p", "Lecture recordings are converted to text with Whisper [[radford2022]], an encoder-decoder transformer "
          "trained on 680,000 hours of labelled audio, running through the faster-whisper implementation "
          "[[fasterwhisper]] with 8-bit weights on the CPU. Answers are read aloud with Piper [[piper]], a local "
          "neural text-to-speech system. For Urdu and Roman Urdu the application does not retrieve in those "
          "languages; it first answers in English from the documents and then produces an explanation in the "
          "requested language, which keeps retrieval quality unchanged and makes the extra step easy to cache "
          "and limit."),

    ("h2", "3.7 Technical frameworks and tools"),
    ("h3", "3.7.1 FastAPI"),
    ("p", "FastAPI [[fastapi]] is a Python web framework built on type hints. Request and response bodies are "
          "validated automatically and an OpenAPI description is generated, which was useful for checking the "
          "size of the API during this project (147 endpoints). Python was the natural choice because the PDF, "
          "OCR, speech and embedding libraries are all available there."),
    ("h3", "3.7.2 Next.js and React"),
    ("p", "The web client uses Next.js [[nextjs]] with React. Pages are organised by route groups, which let the "
          "authentication pages, the main application and the administration console share layouts without "
          "sharing code that they should not. Server-sent events are used to stream the answer token by token."),
    ("h3", "3.7.3 PostgreSQL and vector stores"),
    ("p", "PostgreSQL [[postgres]] stores users, documents, chats, study data and logs. It supports JSON columns, "
          "which we use for quiz questions, plan limits and citations without giving up relational constraints "
          "elsewhere. Embeddings go into a separate vector store: Chroma [[chroma]] on the local disk during "
          "development, or Qdrant [[qdrant]] in the cloud when the host's disk is not persistent. A selector "
          "module chooses the backend from an environment variable, and the two share one interface."),
    ("h3", "3.7.4 LangGraph"),
    ("p", "The question-answering flow is written as a small LangGraph [[langgraph]] state graph with nodes for "
          "understanding the query, retrieving, grading and answering. The graph form keeps the control flow "
          "explicit. The streaming endpoint runs the same nodes by hand so that tokens can be sent while they are "
          "generated."),

    ("h2", "3.8 Structured literature review table"),
    ("p", "{tbl:litreview} summarises the key sources, what they found, their limits, and how each one relates "
          "to this project."),
    ("table", "litreview", "Structured literature review summary",
     ["Source", "Area", "Key finding", "Limitation", "Relevance to EchoLearn"],
     [
         ["Lewis et al. (2020) [[lewis2020]]", "Retrieval-augmented generation",
          "Conditioning generation on retrieved passages improves factual accuracy on knowledge tasks.",
          "Evaluated on Wikipedia, not on personal study material.",
          "Basis of the document-grounded answer pipeline."],
         ["Karpukhin et al. (2020) [[karpukhin2020]]", "Dense retrieval",
          "Dense retrievers can outperform BM25 on open-domain question answering.",
          "Needs training data; BM25 remained stronger where questions share words with passages.",
          "Supports the vector search; motivates adding keyword search."],
         ["Robertson and Zaragoza (2009) [[robertson2009]]", "Sparse retrieval",
          "BM25 ranks by term frequency, term rarity and passage length.",
          "Matches words, not meaning.",
          "Used for keyword and exact-number search."],
         ["Cormack et al. (2009) [[cormack2009]]", "Rank fusion",
          "Reciprocal rank fusion merges rankings without training and beat several alternatives.",
          "Treats all input rankings as equally useful.",
          "Merges dense and keyword results."],
         ["Ji et al. (2023) [[ji2023]]", "Hallucination",
          "Survey of how and why generated text can be unsupported by its input.",
          "Mitigations are partial.",
          "Motivates grounding and refusal."],
         ["Kasneci et al. (2023) [[kasneci2023]]", "LLMs in education",
          "Describes opportunities and risks of LLMs for learning.",
          "Conceptual; limited measured outcomes.",
          "Frames the assistant as support, with the student checking sources."],
         ["Roediger and Karpicke (2006) [[roediger2006]]", "Testing effect",
          "Retrieval practice improves long-term retention more than restudying.",
          "Laboratory studies with short texts.",
          "Basis for quizzes and questions-first tutoring."],
         ["Cepeda et al. (2006) [[cepeda2006]]", "Spacing effect",
          "Distributed practice improves recall compared with massed practice.",
          "Optimal gap depends on the time until the test.",
          "Basis for SM-2 flashcard scheduling."],
         ["VanLehn (2011) [[vanlehn2011]]", "Tutoring systems",
          "Step-level computer tutors approach the effectiveness of human tutors.",
          "Mostly structured domains such as physics.",
          "Model for hint ladder in tutor mode."],
         ["Radford et al. (2022) [[radford2022]]", "Speech recognition",
          "Large-scale weakly supervised training gives robust speech recognition.",
          "Accuracy drops on noisy or accented audio.",
          "Transcribes lectures and video for search."],
     ], [1.2, 0.95, 1.55, 1.3, 1.3]),
]

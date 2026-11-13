"""Chapter 1 (Introduction) and Chapter 2 (SDG alignment)."""

BLOCKS = [
    ("h1", "Chapter 1: Introduction"),
    ("h2", "1.1 Background"),
    ("p", "A student rarely studies from one clean source. A single course usually comes with a textbook of several "
          "hundred pages, a few slide decks, a recorded lecture, a photo of the whiteboard, and last year's paper in "
          "a different format again. When revision time arrives, most of the effort goes into finding things: where "
          "the lecturer defined a term, which page held that table, what the third step of a process was. The "
          "reading itself is the easy part."),
    ("p", "General-purpose chatbots look like an answer to this, and many students already use them that way. The "
          "trouble is that a chatbot answers from what it learned in training, not from the student's own course "
          "material. When it does not know, it often produces something that sounds right anyway, which the "
          "research literature calls hallucination [[ji2023]]. For coursework that is a real problem, because the "
          "student has no quick way to check the claim against a page."),
    ("p", "Retrieval-augmented generation (RAG) is the usual technical answer. Instead of asking the model to "
          "remember, the system first looks up the relevant passages in a document collection and gives them to the "
          "model together with the question [[lewis2020]]. The answer can then be tied to a page, and the system "
          "can say so when nothing relevant was found."),
    ("p", "EchoLearn is a web and mobile application built around that idea. A student uploads their own files "
          "(PDF, Word, PowerPoint, text, spreadsheets, images, audio and video, or a link to an online video), and "
          "the system reads them, indexes them and lets the student ask questions in plain language. Every answer "
          "comes with the pages it was drawn from. On top of this chat, EchoLearn adds the things a student does "
          "after finding an answer: quizzes, flashcards that come back on a schedule, a guided tutor, a day-by-day "
          "study plan, revision sheets and practice papers, with support for voice and for explanations in Urdu "
          "and Roman Urdu."),

    ("h2", "1.2 Problem statement"),
    ("p", "Students who study from their own collections of material face four connected problems."),
    ("ol", [
        "Finding things is slow. Keyword search in a PDF viewer only works if the student remembers the exact "
        "words, and it does not work at all across several files, a scanned page or a lecture recording.",
        "Ordinary AI chat cannot be trusted with coursework. It answers from general training data, may invent "
        "details, and gives no page to check against.",
        "Reading is passive. Educational research has shown for a long time that testing yourself and spacing "
        "revision over days works better than rereading [[roediger2006]], [[cepeda2006]], but few students have the "
        "time to turn their own notes into quizzes and schedules.",
        "Language is a barrier for many students in Pakistan. The material is usually in English, while the "
        "student thinks more comfortably in Urdu or Roman Urdu. Explanations are available, but not tied to the "
        "student's own pages.",
    ]),
    ("p", "Existing tools each cover part of this. Some let you chat with a document, some make flashcards, and "
          "some build study schedules, but we could not find one that keeps the answers tied to the student's own "
          "pages and also carries on into practice, review and planning. EchoLearn tries to do both in one place."),

    ("h2", "1.3 Aims and objectives"),
    ("p", "The aim of the project was to build a study assistant that answers only from the student's own documents, "
          "shows where each answer came from, and helps the student practise what they read. The work was split into "
          "the following objectives."),
    ("ul", [
        "Build a full-stack application with a Next.js web client, a FastAPI backend and a PostgreSQL database, "
        "plus a Flutter mobile client for the main features.",
        "Process PDF, Word, PowerPoint, text, CSV, image, audio and video files, including scanned pages (OCR) and "
        "recordings (speech to text), and index them for search.",
        "Answer questions with retrieval-augmented generation and attach page or timestamp citations; decline to "
        "answer when the documents do not contain the information.",
        "Generate quizzes, flashcards with SM-2 spaced repetition, study plans, revision sheets and practice papers "
        "from the uploaded material.",
        "Provide a tutor mode that asks questions first and gives hints in steps instead of the answer.",
        "Support voice input and spoken answers, and explanations in Urdu and Roman Urdu.",
        "Add accounts, plans with usage limits, and an administration console for users, limits and moderation.",
        "Test the core logic automatically and measure the retrieval quality on a real document collection.",
    ]),

    ("h2", "1.4 Scope of the project"),
    ("p", "EchoLearn is a study tool for students working from material they already have. It handles English "
          "documents best. Answers can be explained again in Urdu or Roman Urdu, but the document text itself is "
          "indexed with an English embedding model. The system is limited to what the uploaded files contain: it "
          "does not browse the web and does not add facts from outside the documents."),
    ("p", "The project does not include real-time collaboration between students, integration with a learning "
          "management system, or online payment. The subscription plans exist in the database and are enforced by "
          "the backend, but moving a user to a paid plan is done by an administrator for now. Generated practice "
          "papers are study aids built from the student's own material and a past-paper structure; the application "
          "never presents them as predictions of a real exam."),

    ("h2", "1.5 Significance of the project"),
    ("p", "The first benefit is trust. Because each answer points to a page, a student can open the source and "
          "judge it, which is the habit a student should have with any AI output. The second is time: the quiz, "
          "flashcard and planning work that students usually skip is generated from the same files in a few "
          "seconds. The third is cost. The system runs on free-tier hosting and on open-weight models served by "
          "Groq, so the same design can be offered to students who cannot pay for commercial study tools."),
    ("p", "The retrieval design is not tied to one subject. We tested it on seven volumes of a religious text, but "
          "the same approach (meaning-based search combined with keyword and reference lookup) applies to law "
          "reports, lecture notes or technical manuals, where users also ask for \"section 12\" or \"page 40\" and "
          "expect that exact place."),

    ("h2", "1.6 Report organization"),
    ("p", "Chapter 2 relates the project to the United Nations Sustainable Development Goals. Chapter 3 reviews the "
          "existing tools and the research behind retrieval-augmented generation, LLMs in education and spaced "
          "repetition. Chapter 4 sets out the requirements, architecture, database and API design. Chapter 5 "
          "describes how each part was implemented and the problems we ran into. Chapter 6 reports the tests and a "
          "measured comparison of retrieval methods. Chapter 7 concludes with lessons learned and future work. The "
          "references and appendices follow."),

    # ------------------------------------------------------------------ Chapter 2
    ("h1", "Chapter 2: Sustainable Development Goals (SDG) Alignment and Impact"),
    ("h2", "2.1 Introduction to Sustainable Development Goals"),
    ("p", "The Sustainable Development Goals are 17 goals adopted by the United Nations in the 2030 Agenda in 2015 "
          "[[un2015]]. They cover poverty, health, education, inequality, climate and institutions, and they give "
          "projects a common vocabulary for describing who benefits. EchoLearn is a learning tool, so its main link "
          "is to education. It also touches inequality and innovation, because who can afford good study support "
          "differs a lot between students, and because the project is a working example of applied AI."),

    ("h2", "2.2 Selected SDGs relevant to EchoLearn"),
    ("h3", "2.2.1 Primary SDG: SDG 4 -- Quality education"),
    ("p", "SDG 4 asks for inclusive and equitable quality education and lifelong learning opportunities for all "
          "[[un2015]]. One-to-one tutoring has long been known to produce much larger learning gains than "
          "classroom teaching [[bloom1984]], yet most students cannot get it. EchoLearn does not replace a teacher, "
          "but it gives every student a patient assistant that works from their own course material, asks them "
          "questions and explains things again when asked."),
    ("h3", "2.2.2 Secondary SDG: SDG 10 -- Reduced inequalities"),
    ("p", "Study support is unevenly distributed. A student with money can pay for a tutor, a private academy or a "
          "paid learning app. A student without it often has only the textbook. EchoLearn has a free Starter plan "
          "with real limits (for example five documents and thirty questions per five hours) that is still useful "
          "for a course. The Urdu and Roman Urdu explanations also lower the language barrier for students who study "
          "in English-medium programmes but think in another language."),
    ("h3", "2.2.3 Secondary SDG: SDG 9 -- Industry, innovation, and infrastructure"),
    ("p", "SDG 9 includes upgrading technological capabilities and encouraging innovation. EchoLearn is a small "
          "but complete example: document processing, a vector index, a language model and a web application "
          "assembled from open-source parts and run on free hosting. The design decisions (for instance running "
          "the embedding model on the CPU through ONNX so that a 512 MB host is enough) are documented in this "
          "report so that other students can reuse them."),

    ("h2", "2.3 Project-to-SDG mapping explanation"),
    ("h3", "2.3.1 Problem addressed"),
    ("p", "Students lose time looking for passages in their own material, and the AI tools that could help either "
          "invent answers or cost money. Students from lower-income backgrounds feel this most, because they have "
          "fewer alternatives."),
    ("h3", "2.3.2 How EchoLearn supports sustainability"),
    ("p", "The system is designed to be cheap to run. The embedding model, the speech recogniser and the text-to-"
          "speech voice all run on the CPU inside the backend process, so there is no per-request cost for them. "
          "The only paid-by-usage services are the language models, and the application uses a small model for "
          "cheap steps such as query rewriting and relevance grading, keeping the larger model for the final "
          "answer. Per-plan quotas keep one user from using a disproportionate share of a free service."),
    ("h3", "2.3.3 Expected societal contribution"),
    ("p", "If students spend less time hunting through files and more time practising recall, the same hours of "
          "study should give better results. The effect we can claim with evidence at this stage is narrower: the "
          "retrieval measurements in Chapter 6 show that the assistant can locate the exact passage a student asks "
          "for. A study of learning outcomes with real students would be the next step."),

    ("h2", "2.4 SDG targets and indicators alignment"),
    ("p", "{tbl:sdg_targets} maps specific SDG targets to the parts of EchoLearn that address them."),
    ("table", "sdg_targets", "SDG target alignment for EchoLearn",
     ["SDG Target", "Target Description", "EchoLearn Contribution"],
     [
         ["SDG 4.1", "Free, equitable and quality education leading to effective learning outcomes.",
          "A free plan with a document-grounded assistant, quizzes and review gives students structured practice "
          "without a fee."],
         ["SDG 4.3", "Equal access to affordable and quality technical, vocational and tertiary education.",
          "Lowers the cost of studying at university level by turning a student's own material into a study tool."],
         ["SDG 4.4", "Increase the number of youth and adults with relevant skills.",
          "Study plans, tutor mode and spaced review help students retain subject knowledge for exams and work."],
         ["SDG 9.5", "Enhance scientific research and upgrade technological capabilities.",
          "A documented, working application of retrieval-augmented generation on open-weight models."],
         ["SDG 10.2", "Promote the inclusion of all irrespective of economic or other status.",
          "Free tier, Urdu and Roman Urdu explanations and voice support reduce economic and language barriers."],
     ], [1.0, 2.55, 2.7]),

    ("h2", "2.5 Expected impact and benefits"),
    ("h3", "2.5.1 Social impact"),
    ("p", "Students who study alone, for instance those who live far from a university or cannot attend an "
          "academy, get something close to a study partner that has read all of their notes. Because the answer "
          "always comes with the page, they also practise the habit of checking a claim against a source."),
    ("h3", "2.5.2 Economic impact"),
    ("p", "A private tutor is a recurring cost for a family. A free plan that covers a single course, and a modest "
          "paid plan for heavy users, shift some of that cost away. For institutions, the Institution plan "
          "removes the document and message limits and raises the file size limit to 200 MB, which suits large "
          "lecture recordings."),
    ("h3", "2.5.3 Technological impact"),
    ("p", "The project shows how a RAG system can be assembled from open-source components on very limited "
          "hardware, and it records the problems met on the way (memory limits, rate limits, retrieval of numbered "
          "references). Those notes are useful to any group who builds a similar system."),

    ("h2", "2.6 Stakeholders and beneficiaries"),
    ("table", "stakeholders", "EchoLearn stakeholders and benefits",
     ["Stakeholder", "Role", "Benefit from EchoLearn"],
     [
         ["Students", "Primary users", "Cited answers, quizzes, flashcards, plans and tutor sessions from their "
                                       "own files."],
         ["Teachers and lecturers", "Indirect users", "Can recommend a tool that students use on the material the "
                                                       "teacher supplied."],
         ["Educational institutions", "Institutional users", "A study tool with higher limits, an admin console "
                                                             "and moderation features."],
         ["Students with limited resources", "Equity beneficiaries", "Free access to a study assistant and to "
                                                                     "explanations in their own language."],
         ["Developers and researchers", "Technical community", "A documented example of a hybrid retrieval "
                                                               "pipeline on open-weight models."],
         ["Administrators", "Platform operators", "Tools to manage users, plans, limits and reported content."],
     ], [1.8, 1.45, 3.0]),

    ("h2", "2.7 Ethical and sustainability considerations"),
    ("h3", "2.7.1 Data privacy"),
    ("p", "EchoLearn stores a user's name, email address, uploaded files and chat history. Passwords are stored "
          "only as bcrypt hashes [[bcrypt]]. Sessions use short-lived JSON Web Tokens [[jwt]]. Every document and "
          "every vector chunk is tagged with the owning user, and queries are filtered by that user, so one "
          "student's material is not searched by another. Students should know that the passages used to answer a "
          "question are sent to an external model provider (Groq, or Gemini when Groq is unavailable). A "
          "production deployment would need a privacy policy and a data retention rule that fits local law."),
    ("h3", "2.7.2 Ethical AI usage"),
    ("p", "The system is built to say \"I couldn't find this\" instead of guessing, and it shows no sources next to "
          "such an answer so that unrelated pages are not mistaken for support. Practice papers are framed as study "
          "aids and never as predictions, and a generated question is checked against the passage it cites and "
          "dropped if the passage does not support it. Explanations in Urdu are checked for facts that were not "
          "in the English answer, and flagged if any are found. These checks reduce errors but do not remove "
          "them, and every revision sheet carries a note asking the student to verify it against the source "
          "documents."),
    ("h3", "2.7.3 Long-term sustainability"),
    ("p", "The project depends on free tiers: the hosted model API has a tokens-per-minute cap (8,000 tokens per "
          "minute for the answer model on the plan we used), and the free web host has limited memory and sleeps "
          "when idle. That is acceptable for a student project but would not scale. The plan and quota system is "
          "the path to sustainability: heavier users can be moved to a paid plan, and limits are changed from the "
          "admin console without a code change."),

    ("h2", "2.8 SDG mapping summary table"),
    ("table", "sdg_summary", "SDG mapping summary for EchoLearn",
     ["Project Component", "SDG", "Target", "Contribution"],
     [
         ["Cited document chat (RAG)", "SDG 4", "4.1, 4.3", "Reliable answers from the student's own material."],
         ["Quizzes, flashcards, study plans", "SDG 4", "4.1, 4.4", "Active recall and spaced revision are "
                                                                   "generated automatically."],
         ["Tutor mode", "SDG 4", "4.1", "One-to-one style questioning and hints at no extra cost."],
         ["Urdu / Roman Urdu explanations, voice", "SDG 10", "10.2", "Reduces language and literacy barriers."],
         ["Free plan and quota system", "SDG 10", "10.2", "Free access with fair-use limits."],
         ["Open-source stack on free hosting", "SDG 9", "9.5", "A reproducible example of applied AI on "
                                                              "limited hardware."],
     ], [2.0, 0.7, 0.9, 2.65]),

    ("h2", "2.9 Future scope for SDG enhancement"),
    ("p", "Three extensions would strengthen the alignment. First, a full interface in Urdu, not only translated "
          "explanations, together with an embedding model that handles Urdu documents directly. Second, an "
          "offline-capable version that runs a small model on the device, for students with unreliable internet. "
          "Third, anonymised learning analytics that let teachers see which topics their whole class finds hard, "
          "without exposing any individual student's files."),
]

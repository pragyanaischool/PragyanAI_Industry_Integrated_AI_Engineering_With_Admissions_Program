
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import streamlit as st

from components.header import render_header
from utils.pdf_utils import render_flipbook
from utils.config import get_setting
from services.rag_engine import create_vector_store
from services.groq_service import answer_from_brochure


# ---------------------------------------------------------
# 1. APPLICATION CONFIGURATION
# ---------------------------------------------------------

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"

DEFAULT_PDF = ASSETS / "pragyanai_ai_engineering_brochure.pdf"
DEFAULT_FLYER = ASSETS / "pragyanai_program_flyer.png"
SYLLABUS_EXCEL = ASSETS / "Syllabus.xlsx"
UPCOMING_BATCH_EXCEL = ASSETS / "Upcoming_Batch.xlsx"
PROGRAM_FLOW_IMAGE = ASSETS / "Program_Flow.png"

LINKEDIN_PROFILE = (
    "https://www.linkedin.com/in/sateesh-ambesange-3020185/"
)

LINKEDIN_COMPANY = (
    "https://www.linkedin.com/company/"
    "pragyan-smartai-technology-llp/"
)

# Your Google Forms responder URL
DEFAULT_GOOGLE_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSc1ww3fzIWqOKlcfQC-baIh3PmVxxRAXKzAQvMDIOnxtJ5PAg/"
    "viewform?usp=dialog"
)

st.set_page_config(
    page_title="PragyanAI | 8-Semester AI Engineering Skill Program",
    page_icon="🤖",
    layout="wide"
)


# ---------------------------------------------------------
# 2. GOOGLE FORM URL HANDLING
# ---------------------------------------------------------

def get_google_form_embed_url():
    """
    Read the Google Form URL from Streamlit Secrets.
    Validate the responder URL and convert it into an embed URL.

    Accepts:
    https://docs.google.com/forms/d/e/FORM_ID/viewform

    Also accepts query parameters such as:
    ?usp=dialog
    """

    form_url = (
        get_setting("GOOGLE_FORM_EMBED_URL")
        or get_setting("GOOGLE_FORM_URL")
        or DEFAULT_GOOGLE_FORM_URL
    )

    form_url = str(form_url).strip()

    # Handle accidental Markdown link formatting
    if "](" in form_url and form_url.endswith(")"):
        form_url = form_url.split("](", 1)[1][:-1].strip()

    parsed = urlparse(form_url)

    valid_url = (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "docs.google.com"
        and parsed.path.startswith("/forms/d/e/")
        and parsed.path.endswith("/viewform")
    )

    if not valid_url:
        return None

    # Preserve existing query parameters and add embedded=true
    query_params = parse_qs(parsed.query)
    query_params["embedded"] = ["true"]

    embed_url = urlunparse((
        "https",
        "docs.google.com",
        parsed.path,
        "",
        urlencode(query_params, doseq=True),
        ""
    ))

    return embed_url


def render_google_eoi_form():
    """Display the Google Expression of Interest form."""

    st.markdown("### Student Registration")
    st.write(
        "Register your interest in the PragyanAI Industry-Integrated AI Engineering Program. "
        "The learning journey begins from the 1st semester and progresses through all 8 semesters. Complete the form below."
    )

    embed_url = get_google_form_embed_url()

    if not embed_url:
        st.error(
            "Invalid Google Forms responder URL. "
            "Please check GOOGLE_FORM_URL in Streamlit Secrets."
        )
        return

    st.components.v1.iframe(
        embed_url,
        height=1150,
        scrolling=True
    )

    st.caption(
        "If the embedded form does not load, "
        "open the form directly using the link below."
    )

    direct_url = embed_url.replace("&embedded=true", "")
    direct_url = direct_url.replace("?embedded=true", "")

    st.link_button(
        "Open Google EOI Form",
        direct_url
    )


# ---------------------------------------------------------
# 3. DATA AND MEDIA HELPERS
# ---------------------------------------------------------

def read_excel_sheet(path, sheet_name, header=0):
    """Read an Excel worksheet safely; return None if unavailable."""
    if not path.exists():
        return None
    try:
        import pandas as pd
        return pd.read_excel(path, sheet_name=sheet_name, header=header)
    except Exception as exc:
        st.error(f"Unable to read {path.name} / {sheet_name}: {exc}")
        return None


def render_dataframe(dataframe):
    """Display a non-empty dataframe with a friendly empty state."""
    if dataframe is None:
        st.info("This information file is not available in the assets folder.")
    elif dataframe.empty:
        st.info("No records are currently available in this worksheet.")
    else:
        st.dataframe(dataframe, use_container_width=True, hide_index=True)


def get_youtube_video_id(url):
    """Extract a YouTube video ID from watch, short, embed or Shorts URLs."""
    parsed = urlparse(str(url).strip())
    host = parsed.netloc.lower().split(":")[0]

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) > 1 else ""
        else:
            video_id = ""
    else:
        video_id = ""

    # YouTube IDs are 11 characters.
    return video_id if len(video_id) == 11 else None


def get_program_video_urls():
    """
    Read YouTube URLs from Streamlit Secrets.
    Configure YOUTUBE_VIDEO_URLS as a list or a newline/comma-separated string.
    """
    configured = get_setting("YOUTUBE_VIDEO_URLS")
    if not configured:
        # Default PragyanAI program video supplied by the user.
        return []

    if isinstance(configured, (list, tuple)):
        return [str(item).strip() for item in configured if str(item).strip()]

    return [
        item.strip().strip('"').strip("'")
        for item in str(configured).replace(",", "\n").splitlines()
        if item.strip()
    ]


# ---------------------------------------------------------
# 4. HEADER AND SIDEBAR
# ---------------------------------------------------------

render_header()

with st.sidebar:

    st.markdown("### PragyanAI Program Portal")

    st.markdown("---")

    st.markdown("### Contact PragyanAI")

    st.write("☎ +91 97410 07422")

    st.write("✉ sateesh.ambesange@pragyanai.com")

    st.write("🌐 www.pragyanai.com")

    st.markdown("---")

    st.caption(
        "Grow with Gyan · Engineering the Complete AI Professional"
    )


# ---------------------------------------------------------
# 5. LOAD DEFAULT PROGRAM MATERIALS
# ---------------------------------------------------------

if not DEFAULT_FLYER.exists():
    st.warning(
        "Program flyer image not found. "
        "Please check the assets folder."
    )

# Validate the brochure before passing it to PyMuPDF / the RAG engine.
# A zero-byte, Git LFS pointer, HTML error page, or incorrectly uploaded
# asset must not crash the rest of the Streamlit application.
pdf_bytes = None
vector_store = None

if not DEFAULT_PDF.exists():
    st.warning(
        "Program brochure PDF not found at "
        f"{DEFAULT_PDF.relative_to(ROOT)}. The flipbook and brochure chatbot "
        "will be unavailable until the valid PDF is uploaded to the assets folder."
    )
else:
    try:
        candidate_pdf = DEFAULT_PDF.read_bytes()

        if not candidate_pdf:
            raise ValueError("The brochure file is empty (0 bytes).")

        if not candidate_pdf.startswith(b"%PDF-"):
            raise ValueError(
                "The file does not have a valid PDF header. "
                "Check that the actual PDF was uploaded, not a Git LFS pointer or HTML page."
            )

        # Confirm that the PDF can be opened and contains at least one page.
        import fitz
        with fitz.open(stream=candidate_pdf, filetype="pdf") as brochure_doc:
            if brochure_doc.page_count < 1:
                raise ValueError("The brochure PDF contains no pages.")

        pdf_bytes = candidate_pdf

    except Exception as exc:
        st.warning(
            "The program brochure could not be validated. The rest of the "
            "application will continue, but the flipbook and brochure chatbot "
            "will remain unavailable until assets/pragyanai_ai_engineering_brochure.pdf "
            f"is replaced with a valid PDF. Details: {exc}"
        )

# Prepare the brochure knowledge base only when a valid PDF is available.
if pdf_bytes is not None:
    with st.spinner("Preparing the program knowledge base…"):
        try:
            vector_store = create_vector_store(pdf_bytes)
        except Exception as exc:
            vector_store = None
            st.warning(
                "The brochure chatbot could not be initialized. Other program "
                "portal features remain available. Check the brochure and RAG "
                f"configuration. Details: {exc}"
            )


# ---------------------------------------------------------
# 5. MAIN NAVIGATION TABS
# ---------------------------------------------------------

tabs = st.tabs([
    "1. Flyer & Introduction",
    "2. Program Flipbook",
    "3. Syllabus & Program Flow",
    "4. Upcoming Programs",
    "5. Program Videos",
    "6. Ask Chatbot",
    "7. Expression of Interest",
    "8. What Customers Say"
])


# =========================================================
# TAB 1: FLYER AND PROGRAM INTRODUCTION
# =========================================================

with tabs[0]:

    st.markdown(
        '<div class="section-title">'
        'Engineering the Complete AI Professional'
        '</div>',
        unsafe_allow_html=True
    )

    # Display default flyer from assets folder
    if DEFAULT_FLYER.exists():

        st.image(
            str(DEFAULT_FLYER),
            use_container_width=True
        )

    st.markdown("### Program Introduction")

    st.write(
        "PragyanAI’s Industry-Integrated AI Engineering Program is a college-industry "
        "partnership designed to build industry-ready engineers across the complete "
        "four-year B.E./B.Tech journey — from Semester 1 to Semester 8. Students learn "
        "academic foundations at college, gain hands-on industry exposure through "
        "PragyanAI programs every semester, build real-world projects and portfolios, "
        "and progress to full industry immersion during the 7th and 8th semesters. "
        "The program combines structured skill development, mentor guidance, "
        "deployment, hackathons, research and product-building."
    )

    metrics = st.columns(4)
    metric_values = ["8 Semesters", "Every Semester", "10 Skill Tracks", "7th–8th"]
    metric_labels = [
        "Complete B.E./B.Tech Journey",
        "Industry Exposure at PragyanAI",
        "Progressive Technical Curriculum",
        "Final-Year Industry Immersion"
    ]

    for col, value, label in zip(metrics, metric_values, metric_labels):
        col.markdown(
            f"""
            <div class="metric">
                <strong>{value}</strong>
                {label}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("### Key Program Highlights")
    highlights = [
        "An 8-semester industry-integrated learning journey, starting from the 1st semester",
        "15 days of PragyanAI industry exposure every semester, as illustrated in the program brochure",
        "Semester-wise progression from AI foundations and Python to data analytics, GenAI, LLM applications, Agentic AI, data engineering, industry projects and deployment",
        "10 progressive technical skill tracks covering Python & Data Wrangling; Data Science & EDA; Business Intelligence; Machine Learning & MLOps; Advanced ML & GenAI; Deep Learning & Computer Vision; NLP & Voice AI; Generative AI & RAG; Autonomous Multi-Agent Systems; and End-to-End MVP Deployment",
        "Hands-on learning through real-world problems, guided tasks, major projects, GitHub portfolio development and live cloud deployment",
        "A 15-day virtual hackathon to turn learning into team-based, real-world problem-solving and product development",
        "Final-year industry immersion during Semesters 7 and 8, with work on real industry projects, production-grade solutions, research and innovation",
        "Mentorship and guidance from industry experts, with opportunities to build a startup, pursue research or access placement pathways",
        "Designed for engineering students from Semester 1; learning depth and project complexity increase as students progress through the semesters"
    ]
    for highlight in highlights:
        st.markdown(f"- {highlight}")

    st.markdown("### Eight-Semester Industry-Integrated Journey")
    semester_data = [
        ("Semester 1", "AI Foundations, Data & Tools",
         "Build the foundation in AI, data and essential tools. Begin hands-on learning and understand industry expectations."),
        ("Semester 2", "Python, Data & Problem Solving",
         "Strengthen Python programming, data handling and structured problem-solving through practical assignments."),
        ("Semester 3", "Data Analytics",
         "Work with data analysis, exploratory data analysis, statistics, visualisation and business-oriented datasets."),
        ("Semester 4", "GenAI, LLMs & Applications",
         "Explore Generative AI, large language models and practical AI application development."),
        ("Semester 5", "Agentic AI & Data Engineering",
         "Progress into agentic AI workflows, data engineering and more advanced applied systems."),
        ("Semester 6", "Industry Projects & Deployment",
         "Build, integrate and deploy industry-oriented projects, strengthening portfolio and production skills."),
        ("Semester 7", "Full Industry Immersion",
         "Participate in full-year industry immersion activities, work on real industry problems and build production-grade solutions."),
        ("Semester 8", "Full Industry Immersion & Career Pathways",
         "Continue industry projects, research and innovation, product development, startup exploration and placement preparation.")
    ]

    semester_columns = st.columns(2)
    for index, (heading, focus, description) in enumerate(semester_data):
        with semester_columns[index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.markdown(f"**{focus}**")
                st.write(description)

    st.markdown("### PragyanAI Skill Sprint PRO")
    st.write(
        "The brochure presents Skill Sprint PRO as a focused mini career accelerator: "
        "10 days of intensive offline bootcamp followed by a 15-day virtual hackathon. "
        "The sprint emphasizes outcome-driven execution, hands-on tasks, major projects, "
        "GitHub portfolio evidence and mandatory cloud deployment."
    )

    sprint_cols = st.columns(3)
    sprint_metrics = [
        ("10 Days", "Offline Bootcamp"),
        ("15 Days", "Virtual Hackathon"),
        ("60+ Hours", "Intensive Learning")
    ]
    for col, (value, label) in zip(sprint_cols, sprint_metrics):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    st.markdown("### Project-Based Learning Engine")
    st.write(
        "The program follows a progressive execution cycle: "
        "Learn → Build → Deploy → Compete → Showcase. During the Skill Sprint PRO, "
        "students complete 10 hands-on tasks and work on two major projects — "
        "one guided assignment and one independent hackathon project. The 15-day "
        "virtual hackathon includes team-based problem solving, mentor interactions, "
        "submission, online demonstration and jury evaluation. Each project is "
        "expected to produce demonstrable proof of work through a clean GitHub "
        "repository, documentation, screenshots and a live deployed application."
    )

    st.markdown("### Student Outcomes & Career Pathways")
    outcome_cols = st.columns(3)
    outcomes = [
        ("Industry-Ready Skills", "Progressive technical skills, real-world problem-solving and mentor-guided execution."),
        ("Portfolio & Deployed Apps", "GitHub repositories, working prototypes, major projects and cloud-hosted applications."),
        ("Career & Innovation Pathways", "Placement readiness, startup development, research, higher education and industry exposure.")
    ]
    for col, (heading, description) in zip(outcome_cols, outcomes):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(description)

    st.markdown("---")

    # Founder profile
    st.markdown(
        "### Sateesh Ambesange | Founder & CEO, PragyanAI"
    )

    col1, col2 = st.columns([1, 2])

    with col1:

        st.markdown("**NITK Alumni**")

        st.markdown("**25+ Years**")

        st.caption(
            "Product experience · Technology leadership · "
            "Serial entrepreneurship"
        )

    with col2:

        st.write(
            "Stanford Ignite / Seed Spark · "
            "IIMA – Business Strategy Communication · "
            "SLP Fellow. "
            "Industry experience includes Intel, Samsung, "
            "Philips and SanDisk."
        )

        st.link_button(
            "View Sateesh Ambesange on LinkedIn",
            LINKEDIN_PROFILE
        )

        st.link_button(
            "Visit PragyanAI LinkedIn Company Page",
            LINKEDIN_COMPANY
        )

    st.caption(
        "Contact: +91 97410 07422 · "
        "sateesh.ambesange@pragyanai.com · "
        "www.pragyanai.com"
    )


# =========================================================
# TAB 2: PROGRAM FLIPBOOK
# =========================================================

with tabs[1]:

    st.markdown(
        '<div class="section-title">'
        'View the Complete Program Brochure'
        '</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "Browse the complete PragyanAI program brochure "
        "using the page-turn controls."
    )

    if pdf_bytes is not None:
        render_flipbook(pdf_bytes)
    else:
        st.info(
            "The brochure flipbook is temporarily unavailable. Upload a valid "
            "PDF as assets/pragyanai_ai_engineering_brochure.pdf."
        )


# =========================================================
# TAB 3: SYLLABUS AND PROGRAM FLOW
# =========================================================

with tabs[2]:

    st.markdown(
        '<div class="section-title">Syllabus & Program Flow</div>',
        unsafe_allow_html=True
    )

    st.markdown("### Program Architecture")
    st.write(
        "**Four-year B.E./B.Tech journey | 8 semesters | Industry integration from Semester 1.** "
        "The brochure describes 15 days of PragyanAI industry exposure every semester "
        "through Semesters 1–6, followed by full industry immersion in Semesters 7–8. "
        "The exact college timetable and implementation calendar are coordinated with "
        "each participating institution."
    )

    architecture_cols = st.columns(4)
    architecture = [
        ("8", "Semesters"),
        ("15 Days", "PragyanAI exposure each semester (Sem 1–6)"),
        ("10", "Technical skill tracks"),
        ("2", "Final-year immersion semesters")
    ]
    for col, (value, label) in zip(architecture_cols, architecture):
        col.metric(label, value)

    if PROGRAM_FLOW_IMAGE.exists():
        st.subheader("Industry-Integrated Program Flow")
        st.image(
            str(PROGRAM_FLOW_IMAGE),
            caption="PragyanAI Industry-Integrated AI Engineering Program – semester-wise learning and final-year industry immersion",
            use_container_width=True
        )
    else:
        st.info(
            "Program flow image not found. If available, place it at "
            "assets/Program_Flow.png."
        )

    st.markdown("### Eight-Semester Learning Journey")
    semester_journey = [
        ("Semester 1", "AI Foundations, Data & Tools", "Build foundations and early industry exposure."),
        ("Semester 2", "Python, Data & Problem Solving", "Develop programming, data and problem-solving capabilities."),
        ("Semester 3", "Data Analytics", "Apply analytics, statistics, EDA and visualisation."),
        ("Semester 4", "GenAI, LLMs & Applications", "Build practical applications with Generative AI and LLMs."),
        ("Semester 5", "Agentic AI & Data Engineering", "Develop agentic workflows and data engineering skills."),
        ("Semester 6", "Industry Projects & Deployment", "Build and deploy industry-oriented projects."),
        ("Semester 7", "Full Industry Immersion", "Work on real industry projects and production-grade solutions."),
        ("Semester 8", "Full Industry Immersion", "Continue industry work, research, innovation and career pathways.")
    ]
    for semester, focus, outcome in semester_journey:
        with st.expander(f"{semester} — {focus}"):
            st.write(outcome)
            if semester in ("Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"):
                st.write("Brochure model: 15 days of PragyanAI industry exposure during the semester.")
            else:
                st.write("Brochure model: Full industry immersion during the final year.")

    st.markdown("### Ten Technical Skill Tracks")
    skill_groups = [
        ("1. Python & Data Wrangling", "Core Python, OOP, Pandas, NumPy, SQL/NoSQL, regular expressions, data cleaning and automation."),
        ("2. Data Science & EDA", "Statistics, descriptive and inferential analysis, hypothesis testing, multivariate EDA and visualisation."),
        ("3. Business Intelligence", "Data transformation, data modelling, KPI design, dashboard visualisation and storytelling."),
        ("4. Machine Learning & MLOps", "Data processing, modelling, AutoML, explainable AI and deployment."),
        ("5. Advanced ML & GenAI", "Recommendation systems, time-series forecasting, association rule mining and GenAI integration."),
        ("6. Deep Learning & Computer Vision", "ANN, CNN, transfer learning, image classification, segmentation and YOLO object detection."),
        ("7. NLP & Voice AI Systems", "Text processing, transformers, chatbots, speech input/output and voice-enabled applications."),
        ("8. Generative AI & RAG Architectures", "Prompting, embeddings, vector databases, LLM APIs, RAG and grounded responses."),
        ("9. Autonomous Multi-Agent Systems", "Orchestrator, researcher, writer and reviewer agents; workflow automation and agent collaboration."),
        ("10. End-to-End MVP Deployment", "Frontend, FastAPI backend, AI/ML engine, databases and cloud deployment.")
    ]
    skill_cols = st.columns(2)
    for index, (skill, description) in enumerate(skill_groups):
        with skill_cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{skill}**")
                st.caption(description)

    st.markdown("### Skill Sprint PRO — 25-Day Execution Model")
    sprint_blueprint = [
        ("10-Day Offline Bootcamp", "60+ hours of intensive learning, 10 hands-on tasks, daily diagnostics and practical implementation."),
        ("15-Day Virtual Hackathon", "Team-based ideation, mentor interactions, project development, online demos and jury evaluation."),
        ("Mandatory Proof of Work", "Clean GitHub repository, README, code, screenshots, project documentation and cloud-hosted live application."),
        ("Major Project Outcomes", "One guided assignment project and one independent hackathon project.")
    ]
    for heading, description in sprint_blueprint:
        with st.expander(heading):
            st.write(description)

    st.markdown("### Deployment & Technology Stack")
    st.write(
        "The brochure emphasizes mandatory cloud deployment using platforms such as "
        "Streamlit Cloud, Hugging Face Spaces, Render or AWS. The illustrated full-stack "
        "architecture includes a frontend, FastAPI backend, AI/ML/GenAI/agent engine, "
        "PostgreSQL or MongoDB database and cloud hosting."
    )

    st.divider()

    if not SYLLABUS_EXCEL.exists():
        st.error("Syllabus.xlsx not found in the assets folder.")
    else:
        try:
            import pandas as pd
            workbook = pd.ExcelFile(SYLLABUS_EXCEL)
            available_sheets = workbook.sheet_names
        except Exception as exc:
            available_sheets = []
            st.error(f"Unable to open Syllabus.xlsx: {exc}")

        if available_sheets:
            syllabus_tabs = st.tabs(available_sheets)
            for syllabus_tab, sheet_name in zip(syllabus_tabs, available_sheets):
                with syllabus_tab:
                    st.subheader(sheet_name)
                    sheet_data = read_excel_sheet(
                        SYLLABUS_EXCEL, sheet_name, header=3
                    )
                    render_dataframe(sheet_data)
        else:
            st.info(
                "No worksheets were found in Syllabus.xlsx. "
                "Please check the workbook and its assets path."
            )


# =========================================================
# TAB 4: UPCOMING PROGRAMS

with tabs[3]:

    st.markdown(
        '<div class="section-title">Upcoming AI Engineering Programs</div>',
        unsafe_allow_html=True
    )

    st.write(
        "The Industry-Integrated AI Engineering Program is designed as an eight-semester "
        "journey. The brochure describes 15 days of PragyanAI industry exposure in "
        "each of Semesters 1–6, followed by full industry immersion in Semesters 7–8. "
        "Implementation dates are coordinated with each participating college."
    )

    st.subheader("Program Schedule")

    with st.container(border=True):
        st.markdown("### Eight-Semester Program Journey")
        st.markdown("**Program:** PragyanAI AI Engineering Skill Program")
        st.markdown("**Availability:** Semester-wise from Semester 1 through Semester 8")
        st.markdown("**Eligible students:** B.E./B.Tech students across all eight semesters")
        st.markdown("**Delivery:** College learning + 15-day PragyanAI exposure in Semesters 1–6 + final-year industry immersion")
        st.markdown("**Commencement:** Semester-wise, aligned with the participating college academic calendar")
        st.markdown("**Status:** College-wise planning / upcoming")
        st.caption(
            "The college and PragyanAI will coordinate semester-wise dates, student cohorts, "
            "industry exposure activities and final-year immersion arrangements."
        )

    st.info(
        "The program journey begins in Semester 1 and is designed to continue through "
        "Semester 8, with increasing technical depth and industry responsibility."
    )


# TAB 5: PROGRAM VIDEOS
# =========================================================

with tabs[4]:

    st.markdown(
        '<div class="section-title">PragyanAI Program Videos</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Watch verified introductions, learning demonstrations, "
        "project walkthroughs and other PragyanAI videos for this program."
    )

    video_urls = get_program_video_urls()

    if not video_urls:
        st.info(
            "No program video has been configured yet. Add verified video "
            "links for this 8-Semester Industry-Integrated AI Engineering Program using "
            "YOUTUBE_VIDEO_URLS in Streamlit Secrets."
        )
        st.code(
            'YOUTUBE_VIDEO_URLS = [\n'
            '  "https://www.youtube.com/watch?v=VIDEO_ID_1",\n'
            '  "https://youtu.be/VIDEO_ID_2"\n'
            ']',
            language="toml"
        )
    else:
        valid_video_count = 0
        for video_number, video_url in enumerate(video_urls, start=1):
            video_id = get_youtube_video_id(video_url)
            if not video_id:
                st.warning(f"Video {video_number}: invalid YouTube URL skipped.")
                continue

            valid_video_count += 1
            st.subheader(f"Program Video {valid_video_count}")
            st.video(f"https://www.youtube.com/watch?v={video_id}")
            st.caption(f"Source: {video_url}")

        if valid_video_count == 0:
            st.warning("No valid YouTube video links were found.")


# =========================================================
# TAB 6: ASK CHATBOT
# =========================================================

with tabs[5]:

    st.markdown(
        '<div class="section-title">'
        'Ask PragyanAI – Program Assistant'
        '</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Ask a basic question or type your own question "
        "about the program."
    )

    # Load FAQ data
    faq_path = ROOT / "data" / "faq.json"

    if faq_path.exists():

        faq_items = json.loads(
            faq_path.read_text(encoding="utf-8")
        )

        with st.expander(
            "Basic Frequently Asked Questions",
            expanded=True
        ):

            for item in faq_items:

                with st.expander(item["q"]):
                    st.write(item["a"])

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    # User question
    question = st.chat_input(
        "Ask about the 8-semester Industry-Integrated AI Engineering Program, skill tracks, hackathon, projects or industry immersion…"
    )

    if question:

        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):

            with st.spinner(
                "Searching the program brochure…"
            ):

                try:

                    if vector_store is None:
                        raise RuntimeError(
                            "The brochure knowledge base is unavailable."
                        )

                    reply = answer_from_brochure(
                        question,
                        vector_store
                    )

                except Exception as exc:

                    reply = (
                        "Unable to generate an answer right now. "
                        "Please check the Groq API configuration "
                        "and application logs."
                    )

                    st.error(str(exc))

            st.markdown(reply)

        st.session_state.messages.append({
            "role": "assistant",
            "content": reply
        })

    # Clear conversation
    if st.button("Clear Chat History"):

        st.session_state.messages = []

        st.rerun()


# =========================================================
# TAB 7: EXPRESSION OF INTEREST
# =========================================================

with tabs[6]:

    st.markdown(
        '<div class="section-title">'
        'Expression of Interest – Student Registration'
        '</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Register your interest in the PragyanAI Industry-Integrated AI Engineering Program. "
        "The program is designed as an 8-semester journey, beginning in the 1st semester "
        "and progressing toward full industry immersion in the 7th and 8th semesters."
    )

    st.write(
        "Please complete the Google Form below. "
        "Your response will be recorded in the connected "
        "Google Form response spreadsheet."
    )

    render_google_eoi_form()


# =========================================================
# TAB 8: TESTIMONIALS AND CUSTOMER FEEDBACK
# =========================================================

with tabs[7]:

    st.markdown(
        '<div class="section-title">'
        'What Customers & Students Say'
        '</div>',
        unsafe_allow_html=True
    )

    st.write(
        "The following learner and industry feedback is reproduced from the brochure "
        "and reflects earlier PragyanAI training engagements; it is not a "
        "guarantee of an individual placement outcome in this program."
    )

    # Student feedback
    st.markdown("#### Student Feedback")

    with st.container(border=True):

        st.markdown(
            "**Akshata – ECE background, "
            "Lingraj Appa Engineering College, Bidar**"
        )

        st.write(
            "Akshata describes completing a PragyanAI training program covering "
            "Python, machine learning, deep learning and data visualization. "
            "She credits the practical learning and mentorship with helping "
            "her secure a Junior AI Engineer position at SynthLinx."
        )

    with st.container(border=True):

        st.markdown(
            "**Isharani – Guru Nanak Dev Engineering College, Bidar**"
        )

        st.write(
            "Isharani describes training in Python, machine learning, deep learning "
            "and Streamlit-based web development, along with hands-on projects "
            "and internship experience. She reports securing a Junior AI "
            "Engineer position at SynthLinx Private Limited."
        )

    # Industry feedback
    st.markdown("#### Industry Feedback")

    with st.container(border=True):

        st.markdown("**SynthLinx – Letter of Appreciation**")

        st.write(
            "The brochure includes a company appreciation "
            "letter recognizing PragyanAI graduates’ training "
            "and contribution in Data Science, Machine Learning, "
            "Deep Learning and Generative AI."
        )

    st.caption(
        "Source: PragyanAI program brochure, "
        "student testimonials and company feedback pages."
    )

    st.markdown("---")

    # Google Reviews
    st.markdown("### Google Reviews")

    review_url = get_setting("GOOGLE_REVIEW_URL")

    business_url = get_setting(
        "GOOGLE_BUSINESS_PROFILE_URL"
    )

    if review_url:

        st.link_button(
            "Read PragyanAI Google Reviews",
            review_url
        )

    else:

        st.info(
            "Google Review link has not been configured yet. "
            "Add GOOGLE_REVIEW_URL in Streamlit Secrets."
        )

    if business_url:

        st.link_button(
            "Open PragyanAI Google Business Profile",
            business_url
        )


# =========================================================
# 6. FOOTER
# =========================================================

st.markdown("---")

st.markdown(
    """
    <div style="
        text-align:center;
        color:#6b6280;
        font-size:13px;
        line-height:1.8;
        padding:12px 0;
    ">
        <strong>© PragyanAI · Pragyan SmartAI Technology LLP</strong>
        <br>
        Grow with Gyan · Engineering the Complete AI Professional
        <br>
        <a href="https://pragyanai.com" target="_blank">
            www.pragyanai.com
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

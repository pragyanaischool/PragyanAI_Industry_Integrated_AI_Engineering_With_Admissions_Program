
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
        "Register your interest in the PragyanAI 24-Month AI Engineering Skill Program "
        "and its semester-based full-time offline bootcamps. Complete the form below."
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
        "PragyanAI’s 24-Month AI Engineering Skill Program is an "
        "institution-integrated, project-based learning program for "
        "engineering students from 1st to 8th semester. It is delivered "
        "through four full-time, offline, on-campus bootcamps of 10 days "
        "each, aligned with the participating college’s academic calendar. "
        "Students build capabilities across eight technical skill areas, "
        "complete 40 projects, contribute to three research papers and "
        "develop one integrated AI product."
    )

    # Program metrics — brochure-aligned
    metrics = st.columns(4)
    metric_values = ["24 Months", "40 Days", "8", "40"]
    metric_labels = [
        "Overall Program Duration",
        "Total Offline On-Campus Training",
        "Technical Skill Areas",
        "Projects"
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
        "Four semesters aligned with the institutional academic calendar; "
        "each semester includes one 10-day, full-time offline bootcamp",
        "Two technical skill areas are addressed in each semester, covering "
        "Python + Data, DS + BI, Advanced ML, DL + CV, NLP, GenAI + RAG, "
        "Agentic AI, and MLOps + Products",
        "40 projects across eight application domains: 32 instructor-guided "
        "projects and 8 independent student projects",
        "Three formal research paper tracks: Data Science & ML; Deep Learning, "
        "Computer Vision & NLP; and Generative AI & Agentic AI",
        "One final integrated AI product / deployed application",
        "20% theory and 80% practical implementation, using a "
        "problem-led, hands-on project-based learning model",
        "Build demonstrable GitHub portfolios, working prototypes, "
        "technical documentation and live project demonstrations",
        "Eligibility: engineering students from any of the 8 semesters (1st–8th); "
        "recommended CGPA of 7.0+ and basic Python proficiency, with learning level "
        "and prerequisites adapted to the semester cohort"
    ]
    for highlight in highlights:
        st.markdown(f"- {highlight}")

    st.markdown("### Core Bootcamp Curriculum Structure")
    semester_data = [
        ("Bootcamp Track 1", "Python + Data | DS + BI",
         "Python, Data Engineering, Data Science and Business Intelligence. "
         "Indicative tools: Python, Pandas, PostgreSQL, Streamlit and Power BI."),
        ("Bootcamp Track 2", "Advanced ML | DL + CV",
         "Advanced Machine Learning, Deep Learning and Computer Vision. "
         "Indicative tools: Scikit-learn, XGBoost, PyTorch and YOLO."),
        ("Bootcamp Track 3", "NLP | GenAI + RAG",
         "Natural Language Processing, Generative AI, LLMs and Retrieval-Augmented "
         "Generation. Indicative tools: Hugging Face, LangChain and ChromaDB."),
        ("Bootcamp Track 4", "Agentic AI | MLOps + Products",
         "Agentic AI, multi-agent systems, MLOps and product engineering. "
         "Indicative tools: LangGraph, CrewAI, FastAPI and Docker.")
    ]

    semester_columns = st.columns(2)
    for index, (heading, skills, description) in enumerate(semester_data):
        with semester_columns[index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.markdown(f"**{skills}**")
                st.write(description)

    st.markdown("### Project-Based Learning Engine")
    st.write(
        "Each bootcamp uses a practical execution cycle: "
        "Problem → Theory → Tools → Code → Experiment → Demo. "
        "Students then move from problem definition and design through "
        "building, testing and deployment to a final defend-style review."
    )

    st.markdown("### Research & Integrated Product Outcomes")
    outcome_cols = st.columns(3)
    outcomes = [
        ("3 Research Papers", "Formal academic manuscripts; publication is subject to external peer review."),
        ("8 Independent Projects", "One independent student project for each technical skill area."),
        ("1 Integrated AI Product", "A complete, deployable AI application demonstrating cross-skill integration.")
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
        "**Institution-integrated AI Engineering Skill Program | Open to all 8 semesters.** "
        "Program opportunities are planned every semester, with dates, cohort level "
        "and delivery schedule coordinated with each participating college. "
        "The core curriculum is organized into four bootcamp tracks, each designed "
        "as a 10-day full-time, on-campus learning experience."
    )

    architecture_cols = st.columns(4)
    architecture = [
        ("8", "Eligible semesters"),
        ("Every semester", "Program availability"),
        ("8", "Technical skill areas"),
        ("40", "Total projects")
    ]
    for col, (value, label) in zip(architecture_cols, architecture):
        col.metric(label, value)

    if PROGRAM_FLOW_IMAGE.exists():
        st.subheader("Skill Program Execution Flow")
        st.image(
            str(PROGRAM_FLOW_IMAGE),
            caption="PragyanAI AI Engineering Skill Program – four 10-day semester bootcamps",
            use_container_width=True
        )
    else:
        st.info(
            "Program flow image not found. If available, place it at "
            "assets/Program_Flow.png."
        )

    st.markdown("### Eight Technical Skill Areas")
    skill_groups = [
        ("1. Python + Data", "Python programming, data engineering and data workflows"),
        ("2. DS + BI", "Data science, business intelligence and dashboards"),
        ("3. Advanced ML", "Advanced machine learning and model development"),
        ("4. DL + CV", "Deep learning and computer vision"),
        ("5. NLP", "Natural language processing"),
        ("6. GenAI + RAG", "Generative AI, LLMs and retrieval-augmented generation"),
        ("7. Agentic AI", "Agentic workflows and multi-agent systems"),
        ("8. MLOps + Products", "MLOps, deployment and AI product engineering")
    ]
    skill_cols = st.columns(2)
    for index, (skill, description) in enumerate(skill_groups):
        with skill_cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{skill}**")
                st.caption(description)

    st.markdown("### Core Bootcamp Curriculum Blueprint")
    semester_blueprint = [
        ("Bootcamp Track 1", "Python + Data; DS + BI",
         "Python, Data Engineering, Data Science and Business Intelligence.",
         "Python, Pandas, PostgreSQL, Streamlit, Power BI"),
        ("Bootcamp Track 2", "Advanced ML; DL + CV",
         "Advanced Machine Learning, Deep Learning and Computer Vision.",
         "Scikit-learn, XGBoost, PyTorch, YOLO"),
        ("Bootcamp Track 3", "NLP; GenAI + RAG",
         "Natural Language Processing, Generative AI, LLMs and RAG.",
         "Hugging Face, LangChain, ChromaDB"),
        ("Bootcamp Track 4", "Agentic AI; MLOps + Products",
         "Agentic AI, multi-agent systems, MLOps and product engineering.",
         "LangGraph, CrewAI, FastAPI, Streamlit, Docker, GitHub, MLflow")
    ]
    for semester, skills, focus, tools_list in semester_blueprint:
        with st.expander(f"{semester} — {skills}"):
            st.write(f"**Curriculum focus:** {focus}")
            st.write(f"**Indicative technology stack:** {tools_list}")

    st.markdown("### Project Portfolio")
    project_cols = st.columns(3)
    project_items = [
        ("32", "Instructor-Guided Projects"),
        ("8", "Independent Student Projects"),
        ("40", "Total Projects")
    ]
    for col, (value, label) in zip(project_cols, project_items):
        col.metric(label, value)

    st.write(
        "The portfolio spans eight application domains. Projects are planned across the program and aligned to the student cohort. Each independent project "
        "requires students to identify a dataset, design the solution architecture, "
        "implement the code and upload the work to GitHub."
    )

    st.markdown("### Research Track & Integrated Product")
    st.write(
        "Research Paper 1: Data Science & Machine Learning.  "
        "Research Paper 2: Deep Learning, Computer Vision & NLP.  "
        "Research Paper 3: Generative AI & Agentic AI."
    )
    st.caption(
        "Research workflow: Identify Gap → Literature Review → Methodology → "
        "Data Collection → Experimentation → Compare Approaches → Manuscript → "
        "Review → Delivery. Publication is subject to external peer review."
    )
    st.write(
        "**Integrated Product:** one final deployed AI application, developed by "
        "combining the skills, tools and project experience gained across the program tracks."
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
        "PragyanAI programs are available every semester for engineering students "
        "from any semester — 1st through 8th. Commencement dates, cohort level, "
        "timetable and delivery arrangements are finalized with each participating "
        "college based on its academic calendar."
    )

    st.subheader("Program Schedule")

    with st.container(border=True):
        st.markdown("### Every Semester")
        st.markdown("**Program:** PragyanAI AI Engineering Skill Program")
        st.markdown("**Availability:** Each semester, subject to college coordination")
        st.markdown("**Eligible students:** All engineering students from 1st to 8th semester")
        st.markdown("**Delivery:** Offline, on-campus, project-based bootcamps")
        st.markdown("**Commencement:** As per the participating college academic calendar")
        st.markdown("**Status:** College-wise planning / upcoming")
        st.caption(
            "The college and PragyanAI will confirm the semester-wise schedule, "
            "student cohort, duration, registration process and program track."
        )

    st.info(
        "There is no restriction to only any of the 8 semesters students. "
        "Students from any of the eight engineering semesters may participate."
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
            "links for this 24-Month AI Engineering Skill Program using "
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
        "Ask about the AI Engineering Skill Program, all-semester eligibility, bootcamp tracks, skills, projects or institutional fees…"
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
        "Register your interest in the PragyanAI 24-Month AI Engineering Skill Program "
        "and its semester-wise offline bootcamps available to students from all 8 semesters."
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

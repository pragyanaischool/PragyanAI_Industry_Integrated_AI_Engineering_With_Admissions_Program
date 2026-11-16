
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
    page_title="PragyanAI | Industry-Integrated AI Engineering Program",
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
        "The programme offers one focused technical skill area in each semester, supported by practical learning and projects."
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
        "Grow with Gyan · Industry-Integrated AI Engineering Program · July 2027 Admission Cycle"
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
        st.image(str(DEFAULT_FLYER), use_container_width=True)


    st.markdown("## The AI World – A New Era of Engineering Careers")
    st.write(
        "Artificial Intelligence is transforming healthcare, banking, manufacturing, "
        "education, agriculture, transportation and software development. The next "
        "generation of engineers will build intelligent systems, develop AI applications, "
        "automate workflows and create products powered by AI."
    )
    ai_cols = st.columns(3)
    for col, (heading, body) in zip(ai_cols, [
        ("AI is changing every industry", "Data-driven decisions, intelligent automation, computer vision and conversational systems are becoming part of modern business."),
        ("Engineering roles are evolving", "Engineers increasingly need programming, data, machine learning, GenAI, integration and deployment capabilities."),
        ("Build, not just consume", "Learn to design, implement, test, document and demonstrate working AI solutions.")
    ]):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)
    st.info("**Our message:** Don’t just graduate with an engineering degree. Graduate with the ability to build AI-powered solutions.")

    st.markdown("## Engineering Admission – Start Your AI Career Journey")
    st.write(
        "Your engineering admission should be more than a college seat. PragyanAI "
        "complements regular B.E./B.Tech academic learning with a structured, semester-wise "
        "AI Engineering Skill Development Programme."
    )
    admission_cols = st.columns(3)
    for col, (heading, body) in zip(admission_cols, [
        ("For Students", "Learn one focused AI skill area every semester and build a portfolio of practical work."),
        ("For Parents", "See clear learning milestones, project evidence and progressive technical development."),
        ("For Colleges", "Strengthen practical AI engineering education alongside the existing university curriculum.")
    ]):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("## Colleges – Bring Practical AI Engineering to Your Campus")
    st.write(
        "PragyanAI collaborates with engineering institutions to introduce structured "
        "AI skill development through semester-wise curriculum, trainers, practical labs, "
        "assignments, hackathons, project reviews and portfolio development. This programme "
        "supplements the college curriculum; it does not replace university requirements."
    )
    college_cols = st.columns(2)
    with college_cols[0]:
        st.markdown("#### College Coordinates")
        for item in ["Student batches and onboarding", "Academic calendar and timetable", "Classroom / laboratory access", "Faculty coordinator and student communication"]:
            st.markdown(f"- {item}")
    with college_cols[1]:
        st.markdown("#### PragyanAI Provides")
        for item in ["Eight-semester skill roadmap", "Trainers, mentors and practical sessions", "10-day offline bootcamp + 15-day virtual hackathon", "Assignments, projects, assessments and portfolio guidance"]:
            st.markdown(f"- {item}")

    st.markdown("## Why PragyanAI – Industry-Integrated AI Engineering Programme")
    st.write(
        "The PragyanAI model connects college-based academic learning with structured "
        "industry-relevant skill development, real-world projects, mentorship and career "
        "pathways. The objective is to help students build practical capability throughout "
        "their engineering journey instead of postponing industry readiness until after graduation."
    )

    value_cols = st.columns(4)
    brochure_metrics = [
        ("500+", "Lab hours"),
        ("100+", "Projects"),
        ("8+", "Hackathons"),
        ("6+", "Technical seminars")
    ]
    for col, (value, label) in zip(value_cols, brochure_metrics):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    tool_col, pathway_col = st.columns(2)
    with tool_col:
        with st.container(border=True):
            st.metric("100+", "Tools")
            st.write(
                "Exposure to relevant programming languages, AI/ML frameworks, "
                "development platforms, industry tools and deployment technologies."
            )
    with pathway_col:
        with st.container(border=True):
            st.markdown("#### Three Career Pathways")
            st.write("Employment · Entrepreneurship · Deep Research")

    st.markdown("### The PragyanAI Industry-Integration Model")
    integration_cols = st.columns(3)
    integration_cards = [
        ("Learn in College", "Build academic foundations through the university B.E./B.Tech curriculum."),
        ("Build at PragyanAI", "Participate in structured skill development, practical labs, projects and mentoring."),
        ("Work on Real Industry Problems", "Apply skills to industry-oriented projects, product development and professional workflows.")
    ]
    for col, (heading, body) in zip(integration_cols, integration_cards):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### Semester-Wise Industry Exposure & Four-Year Outcomes")
    st.write(
        "Students participate in 15 days of PragyanAI-led industry exposure every semester. "
        "Across the four-year B.E./B.Tech journey, they progressively learn, practise, build "
        "projects and develop a portfolio. The final outcome is guided towards one of three "
        "pathways: a job track, research and higher education, or startup development."
    )
    exposure = st.columns(3)
    for col, (value, label) in zip(exposure, [
        ("15 Days", "Industry exposure every semester"),
        ("Semesters 1–6", "Learn, practise and build"),
        ("4 Years", "Progressive engineering journey")
    ]):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    st.markdown("### Final-Year Outcomes – Three Pathways")
    outcome_cols = st.columns(3)
    final_year_outcomes = [
        ("Job Track", "Role-specific technical skills, project portfolio, coding practice, mock interviews, employer engagement and placement preparation."),
        ("Research & Higher Education", "Advanced technical projects, research problem exploration, experimentation, paper and publication support, and preparation for M.S., Ph.D. or other higher studies."),
        ("Startup", "Problem discovery, MVP development, innovation challenges, product validation, business-model guidance and startup ecosystem connections.")
    ]
    for col, (heading, body) in zip(outcome_cols, final_year_outcomes):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### Progressive Technical Skill Pyramid")
    pyramid_cols = st.columns(4)
    pyramid = [
        ("Foundation", "Python, advanced Python, NumPy, Pandas, APIs and programming foundations."),
        ("Analysis", "Data Science, data visualisation, statistics, Business Intelligence, Excel, Tableau and Big Data."),
        ("Intelligence", "Machine Learning, Advanced ML, Deep Learning, Computer Vision, NLP and LLMs."),
        ("Autonomy", "Generative AI, Agentic AI, multi-agent systems and MVP product development.")
    ]
    for col, (heading, body) in zip(pyramid_cols, pyramid):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### Three Career Pathways – Beyond Generic Placements")
    pathway_cols = st.columns(3)
    pathways = [
        ("Employment", "Role-specific skills, mock interviews, employer engagement and coding tests for roles such as Data Analyst, ML Engineer and GenAI Developer."),
        ("Entrepreneurship", "Problem discovery, MVP development, innovation challenges, business-model guidance and startup development."),
        ("Deep Research", "Advanced technical projects, experimentation, paper and publication support, patent exploration and higher-education preparation.")
    ]
    for col, (heading, body) in zip(pathway_cols, pathways):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### Performance-Based Placement Readiness")
    st.write(
        "The brochure describes a transparent placement-readiness framework built around "
        "four demonstrated inputs: technical competency, demonstrated execution through "
        "assigned projects and portfolios, professional discipline, and interview readiness "
        "supported by mock-interview feedback. The brochure positions 100% placement as a "
        "target for performing students; actual outcomes depend on meeting the stated "
        "readiness requirements and employer selection."
    )

    st.markdown("### College – Three Key Pains Solved")
    st.write(
        "PragyanAI’s institutional partnership is designed to help colleges address "
        "three connected challenges: attracting and enrolling students, delivering "
        "industry-relevant practical skills, and improving student career outcomes "
        "while strengthening the college brand."
    )
    pain_cols = st.columns(3)
    college_pains = [
        (
            "1. Admissions & Seat Utilisation",
            "Support the college in attracting and converting student enquiries into admissions. "
            "Plan an intake model around 60-seat or 120-seat options, subject to the college’s "
            "capacity, programme design and mutually agreed targets.",
            ["60-Seat Model", "120-Seat Model"]
        ),
        (
            "2. Industry-Relevant Skilling",
            "Provide structured AI Engineering skill development aligned with evolving industry "
            "tools, technologies and workflows through practical labs, projects, mentoring, "
            "hackathons and portfolio development.",
            ["Practical AI Skills", "Projects & Mentoring"]
        ),
        (
            "3. Jobs, Startups & College Brand",
            "Help students work towards job opportunities, startup creation or research pathways. "
            "Showcase student projects, prototypes, achievements and outcomes to strengthen "
            "the college’s visibility, reputation and industry engagement.",
            ["Job & Career Support", "Startup & Research Outcomes"]
        )
    ]
    for col, (heading, body, tags) in zip(pain_cols, college_pains):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)
                for tag in tags:
                    st.caption(f"• {tag}")

    st.markdown("### A Win-Win Institutional Partnership")
    partner_cols = st.columns(2)
    with partner_cols[0]:
        st.markdown("#### College Responsibilities")
        for item in [
            "Provide laboratory infrastructure and internet access",
            "Coordinate admissions and student onboarding",
            "Appoint admission coordinators and nominate faculty mentors",
            "Manage institutional coordination and fee collection"
        ]:
            st.markdown(f"- {item}")
    with partner_cols[1]:
        st.markdown("#### PragyanAI Responsibilities")
        for item in [
            "Design industry-relevant curriculum",
            "Deliver expert trainers and mentors",
            "Conduct hackathons, assessments and project reviews",
            "Provide programme marketing collateral",
            "Support placement and employer engagement"
        ]:
            st.markdown(f"- {item}")

    st.caption(
        "The programme metrics and delivery model above are reproduced from the supplied "
        "PragyanAI brochure. They describe programme targets and the proposed institutional "
        "model, not guaranteed individual student outcomes."
    )

    st.markdown("## Programme Flow – From Admission to AI Engineering Portfolio")
    for heading, body in [
        ("1. Engineering Admission", "Student joins a B.E./B.Tech programme at a collaborating college."),
        ("2. Programme Orientation", "Introduction to the eight-semester AI Engineering skill journey."),
        ("3. Semester Skill", "One dedicated technical skill area is assigned to the semester."),
        ("4. 10-Day Offline Bootcamp", "Concepts, tools, guided labs, coding practice and assignment development."),
        ("5. Guided Assignment Project", "Trainer-guided application of the semester skill to a defined problem."),
        ("6. 15-Day Virtual Hackathon", "Problem selection, team collaboration, mentoring, implementation and testing."),
        ("7. Independent Hackathon Project", "Student or team builds and presents an independent solution."),
        ("8. Proof of Work & Review", "GitHub, README, report, screenshots, demo and project evaluation."),
        ("9. Portfolio Development", "Semester evidence is consolidated into a progressive technical portfolio."),
        ("10. Next-Semester Progression", "Students advance to the next skill area with greater technical depth.")
    ]:
        with st.expander(heading):
            st.write(body)

    st.markdown("## Programme-Level Targets")
    cols = st.columns(4)
    for col, (value, label) in zip(cols, [
        ("1000+", "Engagement hours"), ("100+", "Real-world projects"),
        ("60–100", "Software tools"), ("3–6", "Industry-ready MVPs")
    ]):
        with col:
            with st.container(border=True):
                st.metric(label, value)
    st.caption("Programme-level targets from the promotional material; actual delivery should be tracked through programme records and student submissions.")

    st.markdown("### Program Introduction")
    st.write(
        "PragyanAI’s AI Engineering Skill Development Program is designed to build "
        "progressive technical capability across the four-year B.E./B.Tech journey. "
        "The programme is structured into eight semesters, with exactly one focused "
        "technical skill area assigned to each semester. Students learn through "
        "structured instruction, hands-on practice, assignments, mini-projects, "
        "major projects and portfolio development. The programme does not include "
        "a separate industry-immersion component; the emphasis is on semester-wise "
        "skill development and demonstrable project outcomes."
    )

    metrics = st.columns(4)
    metric_values = ["4 Years", "500+ Hours", "100+ Projects", "100+ Tools"]
    metric_labels = [
        "B.E./B.Tech Journey",
        "Practical Lab Engagement",
        "Hands-on Project Portfolio",
        "Industry-Relevant Technology Stack"
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
        "Eight-semester AI skill development journey aligned with the B.E./B.Tech academic progression.",
        "Exactly one dedicated technical skill area in each semester.",
        "Progressive curriculum from Python and data foundations to autonomous multi-agent systems and AI product deployment.",
        "Skill Sprint PRO execution model: 10-day intensive offline bootcamp followed by a 15-day virtual hackathon.",
        "Hands-on learning through guided exercises, assignments, mini-projects, case studies and practical implementation.",
        "Two major project outcomes: one guided assignment project and one independent hackathon project.",
        "Mandatory proof of work through GitHub repositories, project documentation, screenshots, demonstrations and cloud deployment.",
        "Increasing technical depth and project complexity from Semester 1 through Semester 8."
    ]
    for highlight in highlights:
        st.markdown(f"- {highlight}")

    st.markdown("### Eight-Semester Skill Progression")
    semester_data = [
        ("Semester 1", "Python & Data Wrangling",
         "Core Python, OOP, Pandas, NumPy, SQL/NoSQL, regular expressions, data cleaning and automation."),
        ("Semester 2", "Data Science & EDA",
         "Statistics, descriptive and inferential analysis, hypothesis testing, multivariate EDA and data visualisation."),
        ("Semester 3", "Business Intelligence",
         "Data transformation, data modelling, KPI design, dashboard visualisation and business storytelling."),
        ("Semester 4", "Machine Learning, Advanced ML & MLOps",
         "Data processing, classification, regression, clustering, AutoML, explainable AI, recommendation systems, forecasting and deployment."),
        ("Semester 5", "Deep Learning & Computer Vision",
         "ANN, CNN, transfer learning, image classification, segmentation and YOLO-based object detection."),
        ("Semester 6", "NLP & Voice AI Systems",
         "Text processing, transformers, chatbots, speech-to-text, text-to-speech and voice-enabled applications."),
        ("Semester 7", "Generative AI & RAG Architectures",
         "Prompt engineering, embeddings, vector databases, LLM APIs, retrieval-augmented generation and grounded AI assistants."),
        ("Semester 8", "Autonomous Multi-Agent Systems & AI Product Deployment",
         "Agent orchestration, workflow automation, frontend/backend integration, databases and end-to-end MVP deployment.")
    ]

    semester_columns = st.columns(2)
    for index, (heading, skill, description) in enumerate(semester_data):
        with semester_columns[index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.markdown(f"**{skill}**")
                st.write(description)

    st.markdown("### How the Programme Builds Engineering Ability")
    st.write(
        "The programme is designed as a progressive learning-to-practice pathway. "
        "Students begin with engineering and programming foundations, apply concepts "
        "to practical tasks, work with industry-relevant tools, solve real-world problems, "
        "and progressively build, test and present working applications. The emphasis is "
        "on demonstrated capability—not only course completion."
    )

    ability_steps = [
        ("1. Learn the Foundations", "Build strong foundations in programming, data structures, Python, data handling and the concepts required for the semester’s skill area."),
        ("2. Practise with Tools", "Use relevant frameworks, platforms, datasets and development tools through guided demonstrations, coding exercises and practical labs."),
        ("3. Apply to Real Problems", "Translate concepts into solutions for practical problem statements, case studies and industry-oriented challenges."),
        ("4. Build and Improve", "Develop working prototypes and applications, integrate components, debug, test and improve the solution with mentor feedback."),
        ("5. Demonstrate Capability", "Present the work, explain technical decisions, show implementation evidence and reflect on areas for improvement."),
        ("6. Progress to the Next Level", "Use the learning evidence and feedback to strengthen capability and take on more advanced skills in the next semester.")
    ]
    for heading, description in ability_steps:
        with st.expander(heading):
            st.write(description)

    st.markdown("### Continuous Evaluation – Measure Progress, Not Just Attendance")
    st.write(
        "Evaluation is intended to happen throughout the learning journey. Students receive "
        "feedback at multiple checkpoints so that gaps can be identified early and addressed "
        "through additional practice, mentoring and improvement."
    )
    evaluation_cols = st.columns(4)
    evaluation_points = [
        ("Knowledge", "Concept understanding, quizzes and technical discussions"),
        ("Practical Skills", "Coding exercises, lab tasks and tool usage"),
        ("Execution", "Project milestones, implementation and problem-solving"),
        ("Professional Readiness", "Participation, discipline, communication and presentation")
    ]
    for col, (heading, detail) in zip(evaluation_cols, evaluation_points):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(detail)

    st.markdown("#### Continuous Evaluation Cycle")
    evaluation_cycle = [
        ("Baseline", "Understand each student’s starting point and prerequisite readiness."),
        ("Practice & Checkpoints", "Review exercises, lab performance, assignments and technical understanding."),
        ("Mentor Feedback", "Provide actionable feedback on strengths, gaps and next steps."),
        ("Improvement", "Give students opportunities to correct, practise again and improve their work."),
        ("Semester Review", "Review accumulated evidence of skills, projects and professional readiness.")
    ]
    for heading, description in evaluation_cycle:
        with st.expander(heading):
            st.write(description)

    st.markdown("### PragyanAI Skill Passport – A Record of Demonstrated Capability")
    st.write(
        "The Skill Passport is a proposed student-facing record that brings together "
        "evidence of learning and achievement across the engineering journey. It helps "
        "students, mentors and colleges see what a learner can demonstrate, what has been "
        "completed and which capabilities need further development."
    )
    passport_cols = st.columns(3)
    passport_sections = [
        ("Skills & Tools", "Semester skill areas, technologies, frameworks and tools practised."),
        ("Evidence of Work", "GitHub links, project records, lab tasks, demos, reports and presentations."),
        ("Progress & Feedback", "Evaluation checkpoints, mentor feedback, improvement actions and readiness indicators.")
    ]
    for col, (heading, detail) in zip(passport_cols, passport_sections):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(detail)

    st.markdown("#### What a Skill Passport Can Contain")
    passport_items = [
        "Student profile, college, branch and semester",
        "Semester-wise skill map and learning milestones",
        "Tools, technologies and frameworks used",
        "Practical lab and assignment completion records",
        "Project links, GitHub repositories and demonstration evidence",
        "Assessment results and mentor feedback",
        "Presentation, communication and teamwork evidence",
        "Career pathway interests: Employment, Entrepreneurship or Deep Research"
    ]
    for item in passport_items:
        st.markdown(f"- {item}")

    st.info(
        "**Outcome:** A progressive, evidence-based profile of each student’s engineering "
        "capability that can support internship applications, placement preparation, "
        "startup exploration and research or higher-education applications."
    )

    st.markdown("### Mandatory Proof of Work")
    proof_items = [
        "GitHub repository with organized source code",
        "README with problem statement, setup instructions and solution overview",
        "Project report or technical documentation",
        "Screenshots or recorded demonstration",
        "Working application or prototype, with deployment link where applicable",
        "Final presentation and project review"
    ]
    for item in proof_items:
        st.markdown(f"- {item}")

    st.markdown("### Student Outcomes & Career Pathways")
    outcome_cols = st.columns(3)
    outcomes = [
        ("Technical Skills", "Semester-wise technical depth, practical implementation and problem-solving."),
        ("Portfolio & Projects", "Guided and independent projects, GitHub evidence, demonstrations and deployed prototypes."),
        ("Career Readiness", "A stronger technical portfolio for internships, placements, research and product innovation.")
    ]
    for col, (heading, description) in zip(outcome_cols, outcomes):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(description)

    st.markdown("---")
    st.markdown("### Sateesh Ambesange | Founder & CEO, PragyanAI")
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
        "**Four-year B.E./B.Tech journey | 8 semesters | One dedicated skill area per semester.** "
        "The programme progresses through eight focused skill areas. Each semester has "
        "one primary skill focus, supported by hands-on practice, assignments and project work. "
        "The brochure describes 15 days of PragyanAI industry exposure each semester in Semesters 1–6, followed by full-year industry immersion in Semesters 7–8."
    )

    architecture_cols = st.columns(4)
    architecture = [
        ("8", "Semesters"),
        ("1", "Skill area per semester"),
        ("8", "Total skill areas"),
        ("25 Days", "Skill Sprint PRO model")
    ]
    for col, (value, label) in zip(architecture_cols, architecture):
        col.metric(label, value)

    if PROGRAM_FLOW_IMAGE.exists():
        st.subheader("Eight-Semester Program Flow")
        st.image(
            str(PROGRAM_FLOW_IMAGE),
            caption="PragyanAI AI Engineering Skill Development Program – one focused skill area in each semester",
            use_container_width=True
        )
    else:
        st.info(
            "Program flow image not found. If available, place the approved image at "
            "assets/Program_Flow.png."
        )

    st.markdown("### One Skill Area Per Semester")
    semester_journey = [
        ("Semester 1", "Python & Data Wrangling",
         "Core Python, OOP, Pandas, NumPy, SQL/NoSQL, data cleaning and automation."),
        ("Semester 2", "Data Science & EDA",
         "Statistics, hypothesis testing, multivariate EDA and visualisation."),
        ("Semester 3", "Business Intelligence",
         "Data transformation, data modelling, KPI design, dashboards and storytelling."),
        ("Semester 4", "Machine Learning, Advanced ML & MLOps",
         "Predictive modelling, AutoML, recommendation systems, time-series analysis, explainable AI and deployment."),
        ("Semester 5", "Deep Learning & Computer Vision",
         "ANN, CNN, transfer learning, image classification, segmentation and object detection."),
        ("Semester 6", "NLP & Voice AI Systems",
         "Transformers, text processing, chatbots, speech input/output and voice applications."),
        ("Semester 7", "Generative AI & RAG Architectures",
         "Prompting, embeddings, vector databases, LLM APIs and RAG applications."),
        ("Semester 8", "Autonomous Multi-Agent Systems & AI Product Deployment",
         "Multi-agent orchestration, workflow automation, full-stack integration and deployed MVPs.")
    ]
    for semester, skill, detail in semester_journey:
        with st.expander(f"{semester} — {skill}"):
            st.write(detail)
            st.write(
                "Semester focus: one dedicated technical skill area, delivered through "
                "structured learning, practical exercises and project-based assessment."
            )

    st.markdown("### How Students Build Practical AI Engineering Ability")
    capability_framework = [
        ("Foundation", "Understand core concepts and develop programming, data and mathematical foundations."),
        ("Guided Practice", "Practise with relevant tools, libraries, platforms and datasets through structured labs."),
        ("Applied Problem-Solving", "Work on case studies and real-world problem statements that require analysis and solution design."),
        ("Build & Integrate", "Develop working applications, connect components, debug, test and refine implementations."),
        ("Demonstrate & Communicate", "Present technical work, explain design choices and maintain evidence of implementation."),
        ("Progressive Advancement", "Build on previous-semester capability and move towards advanced AI, GenAI, Agentic AI and product development.")
    ]
    capability_cols = st.columns(2)
    for index, (heading, description) in enumerate(capability_framework):
        with capability_cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(description)

    st.markdown("### Continuous Evaluation Framework")
    st.write(
        "The brochure’s performance framework identifies four important dimensions: "
        "technical competency, demonstrated execution, professional discipline and "
        "interview readiness. These can be monitored through continuous checkpoints "
        "across the semesters rather than only through a final examination."
    )
    assessment_matrix = [
        ("Technical Competency", "Concept checks, coding exercises, practical demonstrations and technical problem-solving."),
        ("Demonstrated Execution", "Completion and quality of assigned work, project milestones and portfolio evidence."),
        ("Professional Discipline", "Attendance, participation, timely submissions, collaboration and learning commitment."),
        ("Interview / Presentation Readiness", "Technical explanations, presentations, mock interviews and feedback-based improvement.")
    ]
    for heading, description in assessment_matrix:
        with st.expander(heading):
            st.write(description)

    st.markdown("#### Evaluation Touchpoints")
    touchpoints = st.columns(4)
    for col, (heading, description) in zip(touchpoints, [
        ("Entry", "Baseline and readiness check"),
        ("Ongoing", "Labs, exercises and mentor feedback"),
        ("Milestones", "Project and skill demonstrations"),
        ("Semester End", "Portfolio and readiness review")
    ]):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.caption(description)

    st.markdown("### Student Skill Passport")
    st.write(
        "Maintain a semester-wise Skill Passport as a consolidated record of each "
        "student’s learning journey. The passport should be updated as evidence is "
        "reviewed and verified by the trainer, mentor or programme coordinator."
    )
    skill_passport_table = [
        ("Skill Area", "Semester skill and competency checklist"),
        ("Tools & Technologies", "Tools, libraries, platforms and frameworks used"),
        ("Practical Evidence", "Lab exercises, coding tasks and implementation records"),
        ("Projects & Portfolio", "Project summary, GitHub URL, demo and documentation"),
        ("Evaluation", "Checkpoint results, feedback and improvement actions"),
        ("Professional Skills", "Communication, teamwork, discipline and presentation"),
        ("Career Direction", "Employment, Entrepreneurship or Deep Research pathway")
    ]
    for heading, detail in skill_passport_table:
        with st.expander(heading):
            st.write(detail)

    st.caption(
        "The Skill Passport is a recommended programme implementation mechanism. "
        "Its format, verification process and digital or printed delivery can be finalized "
        "by PragyanAI and the participating college."
    )

    st.markdown("### Project Deliverables")
    deliverables = [
        "Problem statement and project objectives",
        "Dataset / input data description and preprocessing approach, where relevant",
        "Source code and reproducible project structure",
        "Implementation results, testing and evaluation",
        "GitHub repository and README documentation",
        "Screenshots, demo video or live demonstration",
        "Final presentation and review"
    ]
    for item in deliverables:
        st.markdown(f"- {item}")

    st.markdown("### Technology Stack & Deployment")
    st.write(
        "The technology stack is selected according to the semester skill and project. "
        "It may include Python, Jupyter/Google Colab, Pandas, NumPy, Scikit-learn, "
        "TensorFlow/PyTorch, OpenCV, NLP/LLM frameworks, databases, Streamlit, Gradio, "
        "FastAPI and suitable cloud hosting. Deployment requirements are finalized "
        "according to the project scope and available platform."
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
# TAB 4: JULY 2027 ADMISSION CYCLE, STUDENT & COLLEGE EOI
# =========================================================

with tabs[3]:

    st.markdown(
        '<div class="section-title">Upcoming Programme – July 2027 Admission Cycle</div>',
        unsafe_allow_html=True
    )
    st.success("Admission cycle commencement: July 2027")

    st.markdown("## Why Colleges Should Partner with PragyanAI")
    st.write(
        "PragyanAI’s Industry-Integrated AI Engineering Programme is designed as a "
        "long-term college growth partnership—not only a technical course. It brings "
        "admissions support, industry-relevant skilling, career pathways and institutional "
        "brand-building together."
    )

    college_value_cols = st.columns(3)
    college_value = [
        (
            "1. Admissions & Seat Utilisation",
            "Support targeted student admissions and help colleges plan seat utilisation "
            "through mutually agreed intake models such as 60-seat and 120-seat cohorts. "
            "The brochure positions PragyanAI as an admissions and differentiation partner."
        ),
        (
            "2. Industry-Relevant Skilling",
            "Connect the B.E./B.Tech academic foundation with practical AI and technology "
            "skills, real-world projects, industry tools, workflows and mentor guidance "
            "throughout the engineering journey."
        ),
        (
            "3. Career Outcomes & College Brand",
            "Help students progress towards employment, entrepreneurship or deep research. "
            "Showcase projects, prototypes, student achievements and outcomes to strengthen "
            "the college’s reputation, visibility and industry engagement."
        )
    ]
    for col, (heading, body) in zip(college_value_cols, college_value):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### A Partnership That Addresses Three College Pains")
    pain_rows = [
        ("Admissions", "Attract quality student enquiries and support agreed seat allocation / utilisation targets."),
        ("Skill & Quality Gap", "Add practical, industry-relevant AI skills, projects, tools and exposure alongside the university curriculum."),
        ("Placements & Career Outcomes", "Build pathways for jobs, startups and higher education / research while creating visible student outcomes.")
    ]
    for title, detail in pain_rows:
        with st.expander(title, expanded=True):
            st.write(detail)

    st.markdown("## Why Parents Should Consider an Industry-Integrated Programme")
    st.write(
        "A conventional engineering degree provides the academic foundation. Parents may "
        "also want to understand how their child will gain practical experience, build "
        "technical confidence and prepare for opportunities before graduation. The "
        "PragyanAI model is designed to bring structured industry exposure and applied "
        "learning into the engineering journey."
    )

    parent_cols = st.columns(2)
    with parent_cols[0]:
        st.markdown("#### Typical Conventional Learning Path")
        for item in [
            "Primary emphasis on university subjects and academic examinations",
            "Industry exposure may happen mainly through occasional visits or a late internship",
            "Students may need to independently find practical projects and current tools",
            "Industry expectations and job-readiness gaps may become clearer near graduation",
            "Career preparation can become concentrated in the final semesters"
        ]:
            st.markdown(f"- {item}")
    with parent_cols[1]:
        st.markdown("#### PragyanAI Industry-Integrated Path")
        for item in [
            "University curriculum continues as the academic foundation",
            "15 days of PragyanAI industry exposure every semester, as described in the brochure",
            "Hands-on learning, real-world projects, industry tools and mentor guidance",
            "Progressive portfolio and practical capability built across the degree",
            "Final-year full industry immersion pathway in Semesters 7–8, as described in the brochure"
        ]:
            st.markdown(f"- {item}")

    st.markdown("### Programme Comparison – What Is Different?")
    st.markdown(
        "| Dimension | Typical Conventional Programme | PragyanAI Industry-Integrated Model |\n"
        "|---|---|---|\n"
        "| Academic foundation | University B.E./B.Tech curriculum | University curriculum remains the foundation |\n"
        "| Industry connection | Often limited or dependent on individual initiative | Structured industry exposure every semester |\n"
        "| Practical learning | Labs and projects vary by institution | Hands-on labs, real-world projects and mentor guidance |\n"
        "| Tools & workflows | May focus on prescribed academic tools | Exposure to industry-relevant tools and workflows |\n"
        "| Portfolio | Often assembled by students independently | Progressive project and portfolio development |\n"
        "| Final-year pathway | Internship / job search / higher studies | Full-year industry immersion pathway with job, startup and research options |\n"
        "| Career direction | Often primarily placement-oriented | Employment, Entrepreneurship and Deep Research pathways |"
    )
    st.caption(
        "This is a high-level programme-model comparison based on the brochure’s "
        "contrast between conventional engineering learning and PragyanAI’s integrated "
        "approach. Actual college curricula and student experiences vary."
    )

    st.markdown("### Three Outcomes Students Can Work Towards")
    pathway_cols = st.columns(3)
    student_pathways = [
        ("Job Track", "Role-specific skills, technical portfolio, coding tests, mock interviews and employer engagement."),
        ("Research & Higher Education", "Advanced projects, research problem exploration, experimentation, publication support and higher-study preparation."),
        ("Startup", "Problem discovery, MVP development, innovation challenges, business-model guidance and startup ecosystem connections.")
    ]
    for col, (heading, body) in zip(pathway_cols, student_pathways):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {heading}")
                st.write(body)

    st.markdown("### Programme at a Glance")
    glance_cols = st.columns(4)
    for col, (value, label) in zip(glance_cols, [
        ("4 Years", "B.E./B.Tech journey"),
        ("8 Semesters", "Progressive skill development"),
        ("15 Days", "Industry exposure every semester"),
        ("3 Pathways", "Job · Research · Startup")
    ]):
        with col:
            with st.container(border=True):
                st.metric(label, value)

    st.markdown("---")
    st.markdown("## Express Your Interest – July 2027 Admission Cycle")
    st.write(
        "Students, parents and colleges can express interest in the July 2027 cycle. "
        "Submit an expression of interest to receive programme details, admission updates "
        "or information about institutional collaboration."
    )
    eoi_cta_cols = st.columns(3)
    with eoi_cta_cols[0]:
        st.markdown("#### Students")
        st.write("Explore the eight-semester AI Engineering journey and register your interest.")
        st.button(
            "Student EOI – Continue Below",
            key="student_eoi_jump",
            use_container_width=True,
            on_click=lambda: st.session_state.update({"open_student_eoi": True})
        )
    with eoi_cta_cols[1]:
        st.markdown("#### Parents")
        st.write("Understand the learning model, industry exposure and career pathways.")
        st.button(
            "Parent Enquiry – Continue Below",
            key="parent_eoi_jump",
            use_container_width=True,
            on_click=lambda: st.session_state.update({"open_student_eoi": True})
        )
    with eoi_cta_cols[2]:
        st.markdown("#### Colleges")
        st.write("Discuss admissions, skilling, career outcomes and a campus partnership.")
        st.button(
            "College EOI – Continue Below",
            key="college_eoi_jump",
            use_container_width=True,
            on_click=lambda: st.session_state.update({"open_college_eoi": True})
        )

    st.markdown("---")
    student_tab, college_tab, enrolled_tab = st.tabs([
        "EOI – Students to Enroll", "EOI – Colleges to Enroll", "Colleges Enrolled"
    ])

    with student_tab:
        if st.session_state.get("open_student_eoi", False):
            st.info("You selected the student / parent expression of interest section.")
        st.markdown("### Student Expression of Interest")
        st.write(
            "Students can express interest in joining the PragyanAI AI Engineering Skill "
            "Development Programme for the July 2027 cycle and receive programme information "
            "and admission updates."
        )
        st.markdown("**What students can expect**")
        for item in [
            "Eight-semester AI skill roadmap", "Practical learning and hands-on assignments",
            "10-day offline bootcamp", "15-day virtual hackathon",
            "Guided and independent project development", "GitHub portfolio and proof-of-work guidance"
        ]:
            st.markdown(f"- {item}")
        render_google_eoi_form()

    with college_tab:
        if st.session_state.get("open_college_eoi", False):
            st.info("You selected the college expression of interest section.")
        st.markdown("### College Expression of Interest")
        st.write(
            "Engineering colleges interested in offering structured practical AI Engineering "
            "skill development can submit an institutional expression of interest for July 2027."
        )
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**College collaboration may include**")
            for item in [
                "Semester-wise programme planning", "Student batch and academic calendar coordination",
                "Faculty coordinator nomination", "Classroom / lab scheduling",
                "Offline bootcamp delivery", "Virtual hackathon and project reviews"
            ]:
                st.markdown(f"- {item}")
        with col2:
            st.markdown("**Suggested institutional EOI details**")
            for item in [
                "College / institution name", "City, state and university affiliation",
                "Principal / HOD / coordinator contact", "Departments and eligible branches",
                "Expected student strength", "Preferred implementation timeline"
            ]:
                st.markdown(f"- {item}")
        college_form_url = get_setting("COLLEGE_EOI_FORM_URL")
        if college_form_url:
            st.link_button("Submit College EOI", str(college_form_url))
        else:
            st.info(
                "College EOI form link is not configured. Add COLLEGE_EOI_FORM_URL "
                "in Streamlit Secrets when the institutional Google Form is ready."
            )
        st.markdown("**For partnership discussions:** +91 97410 07422 · sateesh.ambesange@pragyanai.com")

    with enrolled_tab:
        st.markdown("### List of Colleges Enrolled")
        repo_url = (
            "https://github.com/pragyanaischool/"
            "PragyanAI_Industry_Integrated_AI_Engineering_With_Admissions_Program"
        )
        st.write("Use the admissions programme repository as the reference source for current college enrolment information.")
        st.link_button("Open College Enrolment Repository", repo_url)
        college_file = ASSETS / "Colleges_Enrolled.xlsx"
        if college_file.exists():
            try:
                import pandas as pd
                xls = pd.ExcelFile(college_file)
                sheet_name = "Colleges Enrolled" if "Colleges Enrolled" in xls.sheet_names else xls.sheet_names[0]
                df = pd.read_excel(college_file, sheet_name=sheet_name).dropna(how="all")
                if df.empty:
                    st.info("The college enrolment workbook is present but contains no records.")
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.warning(f"Unable to read assets/Colleges_Enrolled.xlsx: {exc}")
        else:
            st.info(
                "To show college names directly in this portal, add "
                "assets/Colleges_Enrolled.xlsx. Use a 'Colleges Enrolled' worksheet "
                "or the first worksheet for the list."
            )

    st.markdown("---")
    st.caption(
        "July 2027 is the planned admission cycle. Final eligibility, college participation, "
        "batch size, fees, schedule and delivery arrangements are subject to confirmation "
        "with participating institutions."
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
            "links for this Industry-Integrated AI Engineering Program using "
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
        "Ask about the AI Engineering programme, eight-semester skills, Skill Sprint PRO, projects and July 2027 admission…"
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
        "The programme offers one dedicated technical skill area in each semester, supported by practical learning and projects."
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
        Grow with Gyan · Industry-Integrated AI Engineering Program · July 2027 Admission Cycle
        <br>
        <a href="https://pragyanai.com" target="_blank">
            www.pragyanai.com
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

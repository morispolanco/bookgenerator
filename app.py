import streamlit as st
import requests
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from io import BytesIO
import re

# Function to clean Markdown
def clean_markdown(text):
    """Remove Markdown special characters."""
    text = re.sub(r'[#*_`]', '', text)
    return text.strip()

# Function to process lists and replace dashes with em dashes
def process_lists(text):
    """Replace list dashes with em dashes and ensure proper paragraph breaks."""
    lines = text.split('\n')
    processed_lines = []
    in_list = False

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith('-'):
            processed_line = stripped_line.replace('-', '—', 1)
            processed_lines.append(processed_line)
            in_list = True
        else:
            if in_list:
                processed_lines.append("")  # Add a paragraph break after lists
                in_list = False
            processed_lines.append(stripped_line)

    return '\n\n'.join(processed_lines)

# Function to remove unnecessary comments
def remove_unnecessary_comments(text):
    """Remove common comment-like phrases from the generated text."""
    patterns = [
        r"¡.*!",  # Exclamation phrases
        r"Aquí está el capítulo \d+",  # "Here is chapter X"
        r"Este capítulo trata sobre",  # "This chapter deals with..."
        r"En este capítulo",  # "In this chapter..."
        r"El objetivo de este capítulo",  # "The goal of this chapter..."
        r"Vamos a explorar",  # "Let's explore..."
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(.*?\)", "", text)  # Remove parentheses with content
    text = re.sub(r"\n{3,}", "\n\n", text)  # Remove excessive line breaks
    return text.strip()

# Function to format titles based on language rules
def format_title(title, language):
    """Capitalize titles according to language-specific rules."""
    if language.lower() == "spanish":
        words = title.split()
        formatted_words = [words[0].capitalize()] + [word.lower() for word in words[1:]]
        return " ".join(formatted_words)
    else:
        return title.title()

# Function to generate a chapter using Google Gemini
def generate_chapter(api_key, topic, audience, chapter_number, language, table_of_contents="", specific_instructions="", is_intro=False, is_conclusion=False):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    if is_intro:
        message_content = f"Write an introduction about {topic} for {audience}. Use 500-800 words."
    elif is_conclusion:
        message_content = f"Write conclusions about {topic} for {audience}. Use 500-800 words."
    else:
        message_content = f"Write chapter {chapter_number} about {topic} for {audience}. Use at least 2500 words."

    if table_of_contents:
        message_content += f" Follow this structure: {table_of_contents}"
    if specific_instructions:
        message_content += f" {specific_instructions}"

    data = {
        "contents": [{"role": "user", "parts": [{"text": message_content}]}],
        "generationConfig": {
            "temperature": 1,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 8192,
            "responseMimeType": "text/plain"
        }
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        content = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Error generating the chapter.")
    except Exception as e:
        st.error(f"Error generating chapter {chapter_number}: {str(e)}")
        content = "Error generating the chapter."

    cleaned_content = clean_markdown(content)
    cleaned_content = remove_unnecessary_comments(cleaned_content)
    return cleaned_content

# Function to add page numbers to the Word document
def add_page_numbers(doc):
    for section in doc.sections:
        footer = section.footer
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run()
        fldChar = OxmlElement('w:fldChar')
        fldChar.set(qn('w:fldCharType'), 'begin')
        instrText = OxmlElement('w:instrText')
        instrText.set(qn('xml:space'), 'preserve')
        instrText.text = "PAGE"
        fldChar2 = OxmlElement('w:fldChar')
        fldChar2.set(qn('w:fldCharType'), 'end')
        run._r.append(fldChar)
        run._r.append(instrText)
        run._r.append(fldChar2)

# Function to create a Word document
def create_word_document(chapters, title, author_name, author_bio, language):
    doc = Document()

    # Page size and margins
    section = doc.sections[0]
    section.page_width = Inches(5.5)
    section.page_height = Inches(8.5)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(0.8)

    # Title
    formatted_title = format_title(title, language)
    title_paragraph = doc.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_paragraph.add_run(formatted_title)
    title_run.bold = True
    title_run.font.size = Pt(14)
    title_run.font.name = "Times New Roman"

    # Author name
    if author_name:
        author_paragraph = doc.add_paragraph()
        author_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        author_run = author_paragraph.add_run(author_name)
        author_run.font.size = Pt(12)
        author_run.font.name = "Times New Roman"
        doc.add_page_break()

    # Author bio
    if author_bio:
        bio_paragraph = doc.add_paragraph("Author Information")
        bio_paragraph.style = "Heading 2"
        bio_paragraph.runs[0].font.size = Pt(11)
        bio_paragraph.runs[0].font.name = "Times New Roman"
        doc.add_paragraph(author_bio).style = "Normal"
        doc.add_page_break()

    # Chapters
    for i, chapter in enumerate(chapters, 1):
        chapter_title_text = f"Chapter {i}" if language.lower() != "spanish" else f"Capítulo {i}"
        formatted_chapter_title = format_title(chapter_title_text, language)
        chapter_title = doc.add_paragraph(formatted_chapter_title)
        chapter_title.style = "Heading 1"
        chapter_title.runs[0].font.size = Pt(12)
        chapter_title.runs[0].font.name = "Times New Roman"

        processed_chapter = process_lists(chapter)
        paragraphs = processed_chapter.split('\n\n')
        for para_text in paragraphs:
            para_text = para_text.replace('\n', ' ').strip()
            paragraph = doc.add_paragraph(para_text)
            paragraph.style = "Normal"
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.space_after = Pt(0)
            for run in paragraph.runs:
                run.font.size = Pt(11)
                run.font.name = "Times New Roman"

        doc.add_page_break()

    add_page_numbers(doc)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Streamlit configuration
st.set_page_config(page_title="Automatic Book Generator", page_icon="📚")

# Title and sidebar
st.title("📚 Automatic Book Generator")
st.sidebar.header("📖 How does this app work?")
st.sidebar.markdown("""
This application generates non-fiction books in `.docx` format based on a topic and target audience.
**Steps to use it:**
1. Enter the book's topic.
2. Specify the target audience.
3. Provide an optional table of contents.
4. Write optional specific instructions.
5. Select the number of chapters desired (maximum 20).
6. Choose the book's language.
7. Decide whether to include an introduction, conclusions, author name, and author profile.
8. Click "Generate Book".
9. Download the generated file.
""")
st.sidebar.markdown("""
---
**📝 Text correction in 24 hours**  
👉 [Hablemos Bien](https://hablemosbien.org)
""")

# Validate API key
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("Please configure the API key in Streamlit secrets.")
    st.stop()
api_key = st.secrets["GOOGLE_API_KEY"]

# User inputs
topic = st.text_input("📒 Book Topic:")
audience = st.text_input("🎯 Target Audience:")
table_of_contents = st.text_area("📚 Optional Table of Contents:", placeholder="Provide a table of contents for longer chapters.")
specific_instructions = st.text_area("📝 Optional Specific Instructions:", placeholder="Provide specific instructions for the book.")
num_chapters = st.slider("🔢 Number of Chapters", min_value=1, max_value=20, value=5)
include_intro = st.checkbox("Include Introduction", value=True)
include_conclusion = st.checkbox("Include Conclusions", value=True)
author_name = st.text_input("🖋️ Author Name (optional):")
author_bio = st.text_area("👤 Author Profile (optional):", placeholder="Brief professional description or biography.")
languages = ["English", "Spanish", "French", "German", "Chinese", "Japanese", "Russian", "Portuguese", "Italian", "Arabic", "Medieval Latin", "Koine Greek"]
selected_language = st.selectbox("🌐 Choose the book's language:", languages)

# Generate book button
if 'chapters' not in st.session_state:
    st.session_state.chapters = []

if st.button("🚀 Generate Book"):
    if not topic or not audience:
        st.error("Please enter a valid topic and target audience.")
        st.stop()

    chapters = []

    # Generate introduction
    if include_intro:
        st.write("⏳ Generating introduction...")
        intro_content = generate_chapter(api_key, topic, audience, 0, selected_language.lower(), table_of_contents, specific_instructions, is_intro=True)
        chapters.append(intro_content)
        with st.expander("🌟 Introduction"):
            st.write(intro_content)

    # Generate main chapters
    progress_bar = st.progress(0)
    for i in range(1, num_chapters + 1):
        st.write(f"⏳ Generating chapter {i}...")
        chapter_content = generate_chapter(api_key, topic, audience, i, selected_language.lower(), table_of_contents, specific_instructions)
        word_count = len(chapter_content.split())
        while word_count < 2500:  # Ensure minimum word count
            additional_content = generate_chapter(api_key, topic, audience, i, selected_language.lower(), table_of_contents, specific_instructions)
            chapter_content += "\n\n" + additional_content
            word_count = len(chapter_content.split())
        chapters.append(chapter_content)
        with st.expander(f"📖 Chapter {i} ({word_count} words)"):
            st.write(chapter_content)
        progress_bar.progress(i / num_chapters)

    # Generate conclusions
    if include_conclusion:
        st.write("⏳ Generating conclusions...")
        conclusion_content = generate_chapter(api_key, topic, audience, 0, selected_language.lower(), table_of_contents, specific_instructions, is_conclusion=True)
        chapters.append(conclusion_content)
        with st.expander("🔚 Conclusions"):
            st.write(conclusion_content)

    st.session_state.chapters = chapters

# Download options
if st.session_state.chapters:
    st.subheader("⬇️ Download Options")
    word_file = create_word_document(st.session_state.chapters, topic, author_name, author_bio, selected_language.lower())
    st.download_button(
        label="📥 Download in Word",
        data=word_file,
        file_name=f"{topic}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

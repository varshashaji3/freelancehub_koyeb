import fitz  # PyMuPDF
import spacy
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from io import BytesIO
from .models import Document, Template  # Adjust import based on your project structure

# Load spaCy's English NLP model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Download the model if it isn't found
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Function to clean unnecessary icons and whitespace
def clean_text(text):
    text = text.replace('\uf0b7', '')  # Remove unnecessary icons
    text = text.strip()
    return text

# Step 1: Extract text from PDF resume
def extract_text_from_pdf(pdf_stream):
    pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
    text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text()
    return text

# Step 2: Process resume text to extract structured information using NLP
def process_resume_text(resume_text):
    doc = nlp(resume_text)
    headings = ["Experience", "Education", "Technical Skills", "Personal Skills", "Projects", "Certifications", "Achievements", "Hobbies", "Internships", "Contact"]
    extracted_info = {heading: "" for heading in headings}
    current_heading = None

    for line in resume_text.split("\n"):
        line = clean_text(line)
        line_lower = line.lower()

        # Check if the line is a section heading
        if any(line_lower.startswith(heading.lower()) for heading in headings):
            current_heading = next(heading for heading in headings if line_lower.startswith(heading.lower()))
        elif current_heading:
            extracted_info[current_heading] += line + "\n"

    return extracted_info

def parse_internships(internships_text):
    internships_entries = []
    entries = internships_text.split('•')  # Split on bullet points
    
    for entry in entries:
        if entry.strip():
            lines = entry.strip().split('|')  # Split by '|'
            if len(lines) >= 3:
                job_title = lines[0].strip()
                duration = lines[1].strip()
                start_date = lines[2].strip() if len(lines) > 2 else ""
                location = lines[3].strip() if len(lines) > 3 else ""
                
                description = f"{job_title} | {duration} | {start_date} {location}"
                internships_entries.append({"details": description})
    
    return internships_entries

def parse_experience(experience_text):
    # Example parsing logic
    if not experience_text:
        return []  # Return an empty list if no experience is found

    experiences = []
    # Split the text into individual experiences (assuming bullet points)
    for exp in experience_text.split('\n•'):
        parts = exp.split('|')
        if len(parts) >= 4:  # Ensure there are enough parts
            experiences.append({
                'job_title': parts[0].strip(),
                'company_name': parts[1].strip(),
                'start_date': parts[2].strip(),
                'end_date': parts[3].strip(),
                'description': parts[4].strip() if len(parts) > 4 else ''
            })
    return experiences

def parse_education(education_text):
    education_entries = []
    entries = re.split(r'\n(?=\•)', education_text)  # Split on new lines followed by a bullet point

    for entry in entries:
        if entry.strip():
            lines = entry.split('\n')
            degree = ""
            institution = ""
            university_board = ""
            description = ""

            if len(lines) > 0:
                degree = lines[0].strip()
            if len(lines) > 1:
                institution = lines[1].strip()
            if len(lines) > 2:
                university_board = lines[2].strip()
            if len(lines) > 3:
                description = ' '.join(line.strip() for line in lines[3:])

            if degree and institution and university_board:
                education_entries.append({
                    "degree": degree,
                    "institution": institution,
                    "university_board": university_board,
                    "description": description
                })

    return education_entries

def parse_achievements(achievements_text):
    achievement_entries = [clean_text(ach).strip() for ach in achievements_text.split('\n\n') if ach.strip()]
    return achievement_entries

def parse_projects(projects_text):
    project_entries = [clean_text(proj).strip() for proj in projects_text.split('\n\n') if proj.strip()]
    return project_entries

def parse_skills(skills_text):
    # Example parsing logic
    if not skills_text:
        return []  # Return an empty list if no skills are found

    # Split skills by '|', strip whitespace, and return as a list
    return [skill.strip() for skill in skills_text.split('|') if skill.strip()]

# Parsing contact details such as phone, email, and links (e.g., LinkedIn)
def parse_contact(contact_text):
    contact_details = {
        "email": "",
        "phone": "",
        "linkedin": "",
        "other_links": [],
        "address": ""
    }


    # Extract email address
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', contact_text)
    if email_match:
        contact_details["email"] = email_match.group(0)

    # Extract phone number (assuming a standard format)
    phone_match = re.search(r'(\+?\d{1,3})?\s?-?\(?\d{2,4}?\)?\s?\d{3,4}[\s-]?\d{3,4}', contact_text)
    if phone_match:
        contact_details["phone"] = phone_match.group(0)

    # Extract LinkedIn profile
    linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+', contact_text)
    if linkedin_match and linkedin_match.group(0) not in contact_details["other_links"]:
        contact_details["linkedin"] = linkedin_match.group(0)
        print("Extracted LinkedIn:", contact_details["linkedin"])

    
    address_lines = []
    for line in contact_text.splitlines():
        line = line.strip()
        if line and not (line.startswith('+') or re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line) or 'linkedin.com' in line):
            address_lines.append(line)

    contact_details["address"] = ', '.join(address_lines).strip()

    return contact_details


def calculate_accuracy(extracted_info, ground_truth):
    correct_predictions = 0
    total_predictions = 0

    # Compare Experience
    total_predictions += len(ground_truth['Experience'])
    correct_predictions += sum(1 for exp in extracted_info['Experience'] if exp in ground_truth['Experience'])
    print(f"Experience - Correct: {correct_predictions}, Total: {total_predictions}")

    # Compare Education
    if 'Education' in extracted_info and 'Education' in ground_truth:
        total_education_gt = len(ground_truth['Education'])  # Total from ground truth
        total_predictions += total_education_gt  # Add to total predictions count

        for edu, gt in zip(extracted_info['Education'], ground_truth['Education']):
            # Check if both edu and gt are dictionaries
            if isinstance(edu, dict) and isinstance(gt, dict):
                # Check if both have 'degree' and 'institution' keys
                if ('degree' in edu and 'degree' in gt and
                    'institution' in edu and 'institution' in gt):
                    # Compare degree and institution values
                    if (edu['degree'].strip().lower() == gt['degree'].strip().lower() and
                        edu['institution'].strip().lower() == gt['institution'].strip().lower()):
                        correct_predictions += 1
    else:
        print("Error: 'Education' key is missing in either extracted_info or ground_truth")

    print(f"Education - Correct: {correct_predictions}, Total: {total_predictions}")

    # Compare Achievements
    total_predictions += len(ground_truth['Achievements'])
    for ach in extracted_info['Achievements']:
        if ach.strip() in (gt.strip() for gt in ground_truth['Achievements']):
            correct_predictions += 1
    print(f"Achievements - Correct: {correct_predictions}, Total: {total_predictions}")

    # Compare Projects
    total_predictions += len(ground_truth['Projects'])
    for proj in extracted_info['Projects']:
        if proj.strip() in (gt.strip() for gt in ground_truth['Projects']):
            correct_predictions += 1
    print(f"Projects - Correct: {correct_predictions}, Total: {total_predictions}")

    # Compare Skills
    total_predictions += len(ground_truth['Technical Skills'])
    for skill in extracted_info['Technical Skills']:
        if skill.strip() in (gt.strip() for gt in ground_truth['Technical Skills']):
            correct_predictions += 1
    print(f"Skills - Correct: {correct_predictions}, Total: {total_predictions}")

    if (extracted_info['Contact']['email'].strip() == ground_truth['Contact']['email'].strip() and
            extracted_info['Contact']['phone'].strip() == ground_truth['Contact']['phone'].strip() and
            extracted_info['Contact']['address'].strip() == ground_truth['Contact']['address'].strip()): 
        correct_predictions += 1
    print(f"Contact - Correct: {correct_predictions}, Total: {total_predictions}")

    # Calculate accuracy
    accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
    return accuracy

# Function to print extracted information as JSON
def print_extracted_info_as_json(extracted_info):
    extracted_info["Experience"] = parse_experience(extracted_info.get("Experience", ''))
    extracted_info["Education"] = parse_education(extracted_info.get("Education", ''))
    extracted_info["Achievements"] = parse_achievements(extracted_info.get("Achievements", ''))
    extracted_info["Projects"] = parse_projects(extracted_info.get("Projects", ''))
    extracted_info["Technical Skills"] = parse_skills(extracted_info.get("Technical Skills", ''))
    extracted_info["Personal Skills"] = parse_skills(extracted_info.get("Personal Skills", ''))
    extracted_info["Contact"] = parse_contact(extracted_info.get("Contact", ''))

    json_data = json.dumps(extracted_info, indent=4)
    print("Extracted Resume Information (JSON):")
    print(json_data)

# Function to print ground truth data as JSON
def print_ground_truth_as_json(ground_truth):
    json_data = json.dumps(ground_truth, indent=4)
    print("Ground Truth Data (JSON):")
    print(json_data)

# Ground truth data based on extracted information
ground_truth_data = {
    "Experience": [],  # No experience entries in the extracted info
    "Education": [
        {
            "degree": "• MCA (Integrated) | 2020 - 2025",
            "institution": "Amal Jyothi College of Engineering (Autonomous)",
            "university_board": "A P J Abdul Kalam Technological University",
            "description": "8.79 CGPA"
        },
        {
            "degree": "• Standard XII | 2018 - 2020",
            "institution": "Govt. Higher Secondary School, Edakkunnam",
            "university_board": "Board Of Higher Secondary Examination Kerala, India",
            "description": "84 percentage"
        },
        {
            "degree": "• Standard X (SSLC) | 2018",
            "institution": "Assumption High School, Palambra",
            "university_board": "Board of Public Examination, Kerala, India",
            "description": "97 percentage"
        }
    ],
    "Technical Skills": [
        "MS Office (Word, Excel, Power Point)",
        "HTML",
        "CSS",
        "JavaScript",
        "PHP",
        "Django",
        "Python",
        "C",
        "C++",
        "Java",
        "Laravel",
        "R",
        "SQL",
        "NoSQL"
    ],
    "Personal Skills": [
        "Quick learner",
        "Adaptive",
        "Punctual",
        "Communication Skills",
        "Leadership",
        "Time Management"
    ],
    "Projects": [
        "\u2022 Jingle Joy | Online platform for buying Christmas related products with add to cart\nfunctionality.\nDjango | SQLite | HTML | CSS | jQuery | Bootstrap",
        "Tuneify | Platform for music streaming, liked songs, playlist creation, and\npersonalized genre/language recommendations.\nPHP | MongoDB | HTML | CSS | jQuery | Bootstrap",
        "Quillify | Website for buying journal supplies with add to cart functionality.\nLaravel | MySQL | HTML | CSS | jQuery | Bootstrap",
        "Bakers Delight | Online platform for bakery shop management system with\npayment integration and ordering.\nPHP | MySQL | HTML | CSS | JS | AJAX | jQuery"
    ],
    "Certifications": [
        "\u2022 Full Stack Web Development with Flask | LinkedIn learning | June 2024",
        "\u2022 Django Essentials | LinkedIn learning | May 2024",
        "\u2022 Cloud Computing | NPTEL | October 2023",
        "\u2022 AWS Academy Cloud Foundations | AWS Academy | September 2021"
    ],
    "Achievements": [
        "\u2022\nParticipated in old-school hackathon\n| hosted by Init() IT Association at\nAmal Jyothi College of Engineering |\nFebruary 2024",
        "\u2022\nParticipated in Code girls 2021 | An\nindustrial exposure program for girl\nstudents organized by women cell,\nDepartment\nof\nComputer\nApplications, Amal Jyothi College of\nEngineering | May 2021",
        "\u2022\nManager honor for Semester 1 to 2\nand 5 to 7",
        "\u2022\nPrinciple honor for semester 3 and 4"
    ],
   
    "Internships": [
        {
            "details": "Web Development | 1 month | January 2023\nExposys Data Labs, Bengaluru"
        },
        {
            "details": "App Development in Flutter | 1 month | July 2024\nNezuware, Noida, Uttar Pradesh"
        }
    ],
    "Contact": {
        "email": "varshamariyashaji2002@gmail.com",
        "phone": "+91 8078107428",
        "linkedin": "",
        "address": "Perumpalliyazhathu(H), Koovappally P.O, Kanjirappally, Kerala, India, 686518"
    }
}

# Example usage
if __name__ == "__main__":
    pdf_path = r'C:\Users\LENOVO\Downloads\Varsha Shaji_INT MCA_Amal Jyothi College.pdf'  # Replace with the actual path to your PDF file
    resume_text = extract_text_from_pdf(pdf_path)
    extracted_info = process_resume_text(resume_text)
    
    # Print extracted information as JSON
    print_extracted_info_as_json(extracted_info)

    print_ground_truth_as_json(ground_truth_data)

    accuracy = calculate_accuracy(extracted_info, ground_truth_data)
    print("\n\n\n")
    print(f"Accuracy: {accuracy:.2f}%")
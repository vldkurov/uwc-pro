import os
import sys

import django
import pandas as pd
from django.db import transaction
from google.cloud import translate_v2 as translate

# Django setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

# Import models and utilities
from populate.clear_tables import clear_tables
from locations.models import Division, Branch, Person, Phone, Email

# Initialize the Google Translate client
translate_client = translate.Client()

DIVISION_TITLE = "The Association of Ukrainians in Great Britain"
CSV_FILE = "../data/locations.csv"


def translate_text(text, target_language="uk"):
    if not text:
        return ""
    result = translate_client.translate(text, target_language=target_language)
    return result["translatedText"]


def safe_strip(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


# Paths to data
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, CSV_FILE)
data = pd.read_csv(file_path)

# Get or create Division
division, created = Division.objects.get_or_create(title=DIVISION_TITLE)
if created:
    print(f"Division '{DIVISION_TITLE}' created.")
else:
    print(f"Found Division: {division.title}")

# Clear tables related to the division
clear_tables(DIVISION_TITLE)

# Process CSV data
for _, row in data.iterrows():
    title_en = safe_strip(row.get("Branch Name"))

    if not title_en:
        print(f"Skipping row with empty Branch Name: {row}")
        continue

    address_en = safe_strip(row.get("Address"))
    postcode = safe_strip(row.get("Postcode"))
    other_details_en = safe_strip(row.get("Other Details"))

    # Translate fields to Ukrainian
    title_uk = translate_text(title_en, "uk")
    address_uk = translate_text(address_en, "uk")
    other_details_uk = translate_text(other_details_en, "uk")

    def process_person(name, role):
        if name:
            parts = name.split(" ", 1)
            first_name = parts[0] if len(parts) > 0 else ""
            last_name = parts[1] if len(parts) > 1 else ""

            first_name_uk = translate_text(first_name, "uk")
            last_name_uk = translate_text(last_name, "uk")

            person, _ = Person.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
            )
            person.first_name_uk = first_name_uk
            person.last_name_uk = last_name_uk
            person.save()
            return person
        return None

    branch_chair = process_person(safe_strip(row.get("Branch Chair")), "Chair")
    branch_secretary = process_person(
        safe_strip(row.get("Branch Secretary")), "Secretary"
    )

    try:
        with transaction.atomic():
            branch, created = Branch.objects.get_or_create(
                division=division,
                title=title_en,
                defaults={
                    "title_uk": title_uk,
                    "address_en": address_en,
                    "address_uk": address_uk,
                    "postcode": postcode,
                    "other_details_en": other_details_en,
                    "other_details_uk": other_details_uk,
                    "branch_chair": branch_chair,
                    "branch_secretary": branch_secretary,
                },
            )

            if not created:
                print(f"Branch '{title_en}' already exists, updating fields...")
                branch.title_uk = title_uk
                branch.address_en = address_en
                branch.address_uk = address_uk
                branch.postcode = postcode
                branch.other_details_en = other_details_en
                branch.other_details_uk = other_details_uk
                branch.branch_chair = branch_chair
                branch.branch_secretary = branch_secretary
                branch.save()

            # Add phone numbers
            phone_numbers = row.get("Phone Number", "")
            if pd.notna(phone_numbers):
                for phone in str(phone_numbers).split(";"):
                    phone_cleaned = phone.strip().replace(".0", "")
                    if phone_cleaned:
                        Phone.objects.get_or_create(branch=branch, number=phone_cleaned)

            # Add email addresses
            emails = safe_strip(row.get("Email"))
            if emails:
                for email in emails.split(";"):
                    email_cleaned = safe_strip(email)
                    if email_cleaned:
                        Email.objects.get_or_create(branch=branch, email=email_cleaned)

            print(f"Branch '{title_en}' successfully processed!")
    except Exception as e:
        print(f"Error processing branch '{title_en}': {e}")

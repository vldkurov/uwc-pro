import os
import sys

import django
import pandas as pd
from django.db import transaction
from google.cloud import translate_v2 as translate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

from populate.clear_tables import clear_tables
from locations.models import Division, Branch, Person, Phone, Email

translate_client = translate.Client()

DIVISION_TITLE = "UKRAINIAN AUTOCEPHALOUS ORTHODOX CHURCH PARISHES"
CSV_FILE = "../data/orthodox_churches.csv"

def translate_text(text, target_language="uk"):
    if not text:
        return ""
    result = translate_client.translate(text, target_language=target_language)
    return result["translatedText"]


def safe_strip(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, CSV_FILE)
data = pd.read_csv(file_path)

division, created = Division.objects.get_or_create(title=DIVISION_TITLE)
if created:
    print(f"Division '{DIVISION_TITLE}' created.")
else:
    print(f"Found Division: {division.title}")

clear_tables(DIVISION_TITLE)

for _, row in data.iterrows():
    title_en = safe_strip(row.get("Branch Name"))

    if not title_en:
        print(f"Skipping row with empty Branch Name: {row}")
        continue

    address_en = safe_strip(row.get("Address"))
    postcode = safe_strip(row.get("Postcode"))
    title_uk = translate_text(title_en, "uk")
    address_uk = translate_text(address_en, "uk")

    parish_priest_name = safe_strip(row.get("Parish Priest"))
    if parish_priest_name:
        parts = parish_priest_name.split(" ", 1)
        first_name_en = parts[0] if len(parts) > 0 else ""
        last_name_en = parts[1] if len(parts) > 1 else ""
        parish_priest, _ = Person.objects.get_or_create(
            first_name=first_name_en, last_name=last_name_en
        )
    else:
        parish_priest = None

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
                    "parish_priest": parish_priest,
                },
            )

            if not created:
                print(f"Branch '{title_en}' already exists, updating fields...")
                branch.title_uk = title_uk
                branch.address_en = address_en
                branch.address_uk = address_uk
                branch.postcode = postcode
                branch.parish_priest = parish_priest
                # branch.save()
                branch.save(
                    update_fields=[
                        "title_uk",
                        "address_en",
                        "address_uk",
                        "postcode",
                        "parish_priest",
                    ]
                )

            phone_numbers = row.get("Phone number", "")
            if pd.notna(phone_numbers):
                for phone in str(phone_numbers).split(";"):
                    phone_cleaned = phone.strip().replace(".0", "")
                    if phone_cleaned:
                        Phone.objects.get_or_create(branch=branch, number=phone_cleaned)

            emails = safe_strip(row.get("Email"))
            if emails:
                for email in emails.split(";"):
                    email_cleaned = safe_strip(email)
                    if email_cleaned:
                        Email.objects.get_or_create(branch=branch, email=email_cleaned)

            print(f"Branch '{title_en}' successfully processed!")
    except Exception as e:
        print(f"Error processing branch '{title_en}': {e}")

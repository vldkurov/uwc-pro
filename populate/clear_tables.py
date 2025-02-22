import os
import sys

import django
from django.db.models import Q

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

from locations.models import Phone, Email, Branch, Person, Division


def clear_tables(division_title):
    """
    Clears tables for a specific division only. Removes related Phone, Email, and Branch records.
    Person objects are only deleted if they are exclusively linked to the specified division.
    :param division_title: The title of the division for which records will be cleared.
    """
    try:
        # Find the specified division
        division = Division.objects.get(title=division_title)
        print(f"Clearing data for Division: {division.title}...")

        # Get branches linked to this division
        branches = Branch.objects.filter(division=division)

        # Delete related phones and emails
        Phone.objects.filter(branch__in=branches).delete()
        Email.objects.filter(branch__in=branches).delete()

        # Collect IDs of branch_chairs, parish_priests, and branch_secretaries linked to this division's branches
        branch_chairs = branches.values_list("branch_chair_id", flat=True)
        parish_priests = branches.values_list("parish_priest_id", flat=True)
        branch_secretaries = branches.values_list("branch_secretary_id", flat=True)

        # Delete branches
        branches.delete()

        # Combine IDs of all linked Persons
        linked_person_ids = (
            set(branch_chairs).union(set(parish_priests)).union(set(branch_secretaries))
        )

        # Check if the linked Persons are associated with other branches
        for person_id in linked_person_ids:
            if not Branch.objects.filter(
                Q(branch_chair_id=person_id)
                | Q(parish_priest_id=person_id)
                | Q(branch_secretary_id=person_id)
            ).exists():
                Person.objects.filter(id=person_id).delete()

        print(f"Tables cleared for Division: {division.title}.")
    except Division.DoesNotExist:
        print(f"Division with title '{division_title}' does not exist.")


# Main execution with division passed as a parameter
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clear_tables.py '<division_title>'")
    else:
        division_title = sys.argv[1]
        clear_tables(division_title)

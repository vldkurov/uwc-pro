import os
import sys

import django


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uwc_proto.settings")
django.setup()

from locations.models import Branch


branches = Branch.objects.all()

for branch in branches:
    try:
        print(f"Processing branch: {branch.title_en}")
        branch.geocode()
        branch.save()
        print(f"Geolocation updated for: {branch.title_en}")
    except Exception as e:
        print(f"Error updating geolocation for {branch.title_en}: {e}")

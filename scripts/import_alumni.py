import sys
import os
import django
import csv
import json


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from django.conf import settings
from alumni.gsuite_adapter import DateSheetsAdapter

# Load alumni settings
try:
    ALUMNI_SETTINGS = json.loads(settings.ALUMNI_SETTINGS)
    AUTH, SHEET = ALUMNI_SETTINGS.get("auth", {}), ALUMNI_SETTINGS.get("sheet")
except Exception as e:
    print("Error while loading alumni settings:", e)
    sys.exit(1)

MEMBER_SHEET_NAME = "members"  # Should match the sheet name

def main(csv_path):
    client = DateSheetsAdapter(AUTH, SHEET, MEMBER_SHEET_NAME)
    audit_client = DateSheetsAdapter(AUTH, SHEET, "audit_log")
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Adjust these fields to match your sheet columns
            data = [
                row.get("il") or "",  # or generate if needed
                row.get("Förnamn"),
                row.get("Efternamn"),
                row.get("Adress (hem)"),
                row.get("Postnummer (hem)"),
                row.get("Ort (hem)"),
                row.get("Land (hem)"),
                row.get("Arbetsplats"),
                row.get("Avd/tjänst"),
                row.get("Mobil"),
                row.get("E-post"),
                row.get("TFiF-medlem"),
                row.get("Får kontaktas"),
                row.get("Inskriven på KTF/MNF/KT/FNT"),
                row.get("Blivit medlem"),
                row.get("Uppgifterna uppdaterade"),
                1, # Set everyone as paid when importing
                0,
                row.get("Medlemskap"),
            ]
            client.append_row(data)
            print(f"Added alumni: {row.get('Förnamn')} {row.get('Efternamn')}")
            audit_client.append_row([
                "IMPORT",
                json.dumps(row),
            ])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_alumni.py <csv_file>")
        sys.exit(1)
    main(sys.argv[1])
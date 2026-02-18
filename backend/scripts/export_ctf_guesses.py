import sys
import os
from io import StringIO
import django


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from ctf.models import Guess

member_mask = "***********"

ctf_id = sys.argv[1]

guesses_per_flag = {}
total_guesses = 0

with StringIO() as output:
    guesses = Guess.objects.filter(ctf=ctf_id).all()
    for guess in guesses:
        guesses_per_flag[guess.flag] = guesses_per_flag.get(guess.flag, 0) + 1
        total_guesses += 1
        output.write(f"FLAG: {guess.flag} USER: {member_mask} INPUT: {guess.guess}\n")

    output.write(f"\n\nTotal guesses: {total_guesses}\n\n")
    for flag, count in guesses_per_flag.items():
        output.write(f"FLAG: {flag} - Number of inputs: {count}\n")

    print(output.getvalue())


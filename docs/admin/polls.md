# Polls Admin Guide

## Purpose
Run quick votes or questionnaires for members. Each poll ("Fråga") contains multiple answer choices and optional restrictions on who may participate.

## Access
1. Log into `/admin`.
2. Open **Polls › Questions** (`/admin/polls/question/`).

## Create a Poll
1. Click **Add question**.
2. Fill in the fields:
   - **Fråga** – the question text shown at `/polls/<id>/`.
   - **Valmöjligheter** – pick who can vote:
     - *Vem som helst* – open to everyone.
     - *Endast medlemmar* – requires login.
     - *Ordinarie medlemmar* – only ordinary members (permission profile 2).
     - *Endast röstberättigade* – ordinary members with an active subscription.
     - Members whose profile has no voting rights (for example SF *Extra medlem*) are excluded from the last two options but may still join polls open to all members.
   - **Flerval** – allow selecting multiple answers. If enabled, optionally set **Antal flerval som krävs** to force exactly N picks.
   - **Publiceras** – timestamp when the poll should become visible. Leave empty to keep it hidden, or pick a future time to schedule publication; a past time publishes immediately.
   - **Visa resultat** – enable public results at `/polls/<id>/results/`.
   - **Avsluta röstande** – locks the poll (even admins cannot reopen without editing).
3. Save the question to reveal the inline **Choices** table.

## Add Answer Choices
1. In the **Choices** inline, click **Add another Choice** for each option.
2. Enter the visible text. Vote counts are read-only.
3. Save when all options have been added.

## Restrict a Poll to a Meeting
On an association that installs the `attendance` app (`date`), the poll page has a **Närvarokrav** section below the choices, on the add page as well as on a saved poll. Pick an **Närvaroevenemang** and save. From then on the poll accepts a vote only from somebody who is in that meeting's room at the moment they vote: a member whose newest check-in there is an arrival. A member who has checked out, a member who has not arrived yet, and an anonymous visitor are all refused with "Du måste vara närvarande på mötet för att rösta.".

Leave the section empty and the poll keeps the ordinary rules from **Valmöjligheter**. A poll belongs to at most one meeting, so the section holds a single row. Presence is read when the vote is submitted and nothing about it is stored on the vote, so a member who leaves the room afterwards can no longer vote, while the votes already counted stay counted.

An attached poll is no longer a dead end for the participant. A signed-in member who is not in the room sees the meeting's name and a button, **Ange koden och checka in**, which opens that meeting's check-in page and carries the poll along, so a successful check-in lands them back on the poll. A signed-in member the meeting counts as present reads "Du är närvarande på <meeting>." instead, with no button. A visitor who is not signed in is sent to the login page with the poll as the page to return to, and is told that voting needs a signed-in member and presence: a guest cannot vote by checking in, because the room list is keyed on a member. A wrong code, a lockout and an "already present" conflict all keep the poll in the check-in form, so a participant who mistypes the code still comes back to the poll after a second attempt. A poll with no **Närvarokrav** row shows none of this.

On an association that does not install `attendance` (every association except `date`), the section is not rendered at all: there is no meeting to pick and no meeting to check against, and every poll keeps the rules from **Valmöjligheter**. The poll list (`/admin/polls/question/`) has a **Närvaroevenemang** column on `date`, showing the meeting an attached poll belongs to and a dash for a poll with none; that column does not exist on the other associations either.

Somebody who checks in and never checks out still counts as present, so a poll attached to that meeting keeps accepting their vote after it has ended. Stop the poll with **Avsluta röstande** when the vote is over, and remind people to press **Gå ut** if you want the room list itself to be exact.

## Monitor Votes
- The **Röstare** inline lists individual members who voted. It’s read-only to avoid tampering (only superusers may delete entries).
- On a poll with a **Närvarokrav** row, the poll page carries two read-only lines among its own fields, above the lists of choices, voters and the meeting: **Närvarande i mötet nu** is how many the meeting counts as present at this moment, and **Har röstat** is how many have voted so far. Both are read when the page is loaded, so reload to see them move.
- Use the list filter (`pub_date`) or search bar to find older polls.

That pair is what to read while a vote is running. The poll accepts a vote only from somebody who is present, so a turnout below the headcount means somebody who is in the room has not voted yet: wait a little longer, or ask the room for the remaining votes before you stop the poll. The two numbers are equal when everybody the site counts as present has voted. Both lines are absent on a poll with no **Närvarokrav** row, and on an association that does not install the `attendance` app.

## Testing the Poll
1. Visit `/polls/` to confirm the question appears (only published questions show up).
2. Click the poll to test the voting flow with a member account that matches the restriction level.
3. Share the `/polls/<id>/results/` URL if results are public.

## Tips
- Keep polls short—long multiple-choice instructions can be moved into the content of the page that links to the poll.
- When ending a vote, tick **Avsluta röstande** instead of clearing **Publiceras**; this preserves historical visibility while blocking new submissions.

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
   - **Flerval** – allow selecting multiple answers. If enabled, optionally set **Antal flerval som krävs** to force exactly N picks.
   - **Publicera** – unchecked polls stay hidden.
   - **Visa resultat** – enable public results at `/polls/<id>/results/`.
   - **Avsluta röstande** – locks the poll (even admins cannot reopen without editing).
3. Save the question to reveal the inline **Choices** table.

## Add Answer Choices
1. In the **Choices** inline, click **Add another Choice** for each option.
2. Enter the visible text. Vote counts are read-only.
3. Save when all options have been added.

## Monitor Votes
- The **Röstare** inline lists individual members who voted. It’s read-only to avoid tampering (only superusers may delete entries).
- Use the list filter (`pub_date`) or search bar to find older polls.

## Testing the Poll
1. Visit `/polls/` to confirm the question appears (only published questions show up).
2. Click the poll to test the voting flow with a member account that matches the restriction level.
3. Share the `/polls/<id>/results/` URL if results are public.

## Tips
- Keep polls short—long multiple-choice instructions can be moved into the content of the page that links to the poll.
- When ending a vote, tick **Avsluta röstande** instead of unpublishing; this preserves historical visibility while blocking new submissions.

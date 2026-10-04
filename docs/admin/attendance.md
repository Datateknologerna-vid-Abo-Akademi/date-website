# Attendance Admin Guide

## What this is for
The attendance list is the digital replacement for the paper list at a meeting. You create an event, the site gives it a public page, and the participants check themselves in and out with a short code that the site shows you on a staff-only page and rotates by itself. Nobody has to be checked in by an editor, and no paper has to be passed around, so a room with a screen or a projector can run the whole thing from the site.

The list is a record of who was in the room at a meeting. It is not the association's minutes, and it does not replace them.

## Creating an event
1. Open the attendance events list (**Närvaroevenemang**, under **Närvaro** in the sidebar) in `/admin` and use the add button above the list. It shows each event's title, its start and end time and whether guests may check in, opens on the newest event, and can be searched by title or narrowed by date.
2. Fill in:
   - **Titel**: the name the participants see, and the name the admin list shows.
   - **Beskrivning**: one optional line shown under the title.
   - **Slug**: the URL segment. An event with the slug `hostmote` lives at `/attendance/hostmote/`. It has to be unique and can contain only letters, digits, hyphens and underscores, so write `hostmote` rather than `höstmöte`.
   - **Starttid** and **Sluttid**: when the event begins and ends. **Sluttid** is optional. With it, the event leaves the public list once that moment has passed; without it, the event stays on the list until you delete it. A meeting whose end is not known in advance is the ordinary reason to leave it empty: the event page then prints "Slutar: -", the event stays on the public list, and the report labels its headcount differently (see The report after the meeting, and `docs/dev/attendance.md` for what the number is computed from).
   - **Tillåt icke-medlemmar att delta**: ticked (the default) means a visitor without an account sees the check-in form and writes their name. Unticked means the event page asks for a login, and a guest cannot check in at all.
   - **Kodens giltighetsperiod (sekunder)**: how long each code is shown before it rotates. 30 is the default, and the field refuses anything below 1 second, because a period of zero breaks the code calculation. A meeting that needs longer to read or scan the code can be given more; a shorter period is harder to pass on to somebody outside the room.
   - **Kodens genereringsnyckel**: the value the codes are computed from. The site fills in a random one, and you can leave it as it is.
3. Save. The event appears on `/attendance/` immediately, and its page is at `/attendance/<slug>/`.

## Running the check-in at the meeting
1. Open the event's page at `/attendance/<slug>/`, and follow **Till översiktsvyn** near the top. Only staff see that link.
2. The overview page at `/attendance/<slug>/overview` shows the current code in large digits with a QR code below it, and the **Närvarande** list under that. The code and the QR code change every **Kodens giltighetsperiod (sekunder)** seconds, and the page updates itself, list and headcount included, so leave it on a screen where the participants can see or scan it.
3. The overview page is for staff only. An anonymous visitor who opens the address is asked to log in, and a signed-in member who is not staff gets an error page. That is deliberate: the code is the whole check-in control, so the page that shows it stays with the people running the meeting.
4. Read the code from the screen rather than copying it onto a whiteboard or a printout. It is only valid for its window, so anything written down is stale within seconds.

## The headcount in the room
Both the event page and the overview page print how many people are present in the **Närvarande** heading itself, as in "Närvarande: 7". On the event page the number and the list below it are a snapshot from the moment the page was opened, so reload to refresh both. On the overview page they are live: the number moves as people check in and check out, and it is always the length of the list under it, so the heading and the rows cannot disagree.

That number is what to compare a vote against. A poll attached to the meeting accepts a vote only from somebody the site counts as present (see `docs/admin/polls.md`), so while the headcount is higher than the number of votes counted so far, somebody who is in the room has not voted yet. That is the moment to wait a little longer, or to open the poll and read the two numbers side by side.

## Reaching the event page
The site's menus are editor content, not code, so the attendance page reaches them the way any other link does: add a **Static URL** entry (under a **Static Page Nav** category) pointing at `/attendance/`, and it appears in that dropdown. Until such an entry exists, the address is something you give to the participants.

The event list at `/attendance/` is public, and each event has its own address at `/attendance/<slug>/`. The QR code on the overview page is the shortest route to one event: it encodes the event's address as a full link, the kind any phone camera app offers to open, with the current code in it, so a participant who scans it lands on the event page with the code already filled in. Nothing needs to be installed for that, and the page's own **Skanna QR-kod** button reads the same code. The address it carries is the one the overview page is being served from, so open that page at the site's own address, which is where the admin is normally reached anyway: a page opened through an internal server name and not through the site would put that name in the code, and a phone in the room could not follow it. Put the event's address in the meeting invitation if people should be able to find it without the QR code, and remember that a guest still needs **Tillåt icke-medlemmar att delta** ticked to use it.

## Checking people in and out
- A signed-in member opens the event page, types the code (or scans the QR code with a phone camera, which opens the same page with the code prefilled) and presses **Gå in**. The member is recorded as themselves, and the page then shows them as present, with **Gå in** disabled and **Gå ut** ready.
- A visitor without an account types their name in the name box, then the code, and presses **Gå in**. The name is what the list keeps. If **Tillåt icke-medlemmar att delta** is unticked there is no name box, and the page asks the visitor to log in instead.
- Nobody can go in twice or go out when not present. For a signed-in member the button that makes no sense is disabled. For everyone, the server refuses the action with a message on the page instead of writing a row: "Du kan inte gå in i ett evenemang var du redan är närvarande" or "Du kan inte gå ut ur ett evenemang var du inte är närvarande".
- The **Närvarande** list at the bottom of the event page is a snapshot from the moment the page was opened, so reload to see who has arrived since. On the staff overview page the same list is live: it picks up a name as that person checks in and drops it as they check out, next to the code and the QR code, which also update by themselves. The number in the heading is the length of that list, so it is a snapshot on the event page and live on the overview page.
- A guest appears on the overview page under exactly the name they typed. The event page's list adds the marker "(icke-medlem)" after a guest's name; the overview page leaves it off, because that label is the one the live update carries.
- The **Närvarande** list is public on the event page: anyone who can open the page sees who is present, including the names guests typed. Only the change log below it is staff-only.
- A guest's name is remembered from one event to the next, because the name is the whole identity of a guest. Two different people who type the same name share one entry and cannot be told apart, so ask guests for a name that is theirs alone, such as first name and surname.

## The change log
- The event page shows a **Närvaroändringar** list to staff under the attendee list: one line per change, newest first, naming the person, the change in Swedish (**anlände** or **lämnade**) and the date and time in the association's own timezone. It is the same data the attendee list is computed from, so it is what to read when the **Närvarande** snapshot on the event page looks out of date.
- The admin also has a standalone list of all attendance changes across every event, and each event's admin page carries the same rows as a collapsed table at the bottom.
- The change rows can be edited and deleted in the admin like any other row, but deleting one changes who counts as present on the public page, because presence is read from the newest row rather than stored. Treat a manual edit as a correction of last resort, and reload the public page afterwards.

## The report after the meeting
Once the meeting is over, the attendance events list (**Närvaroevenemang**, under **Närvaro**) has a **Rapport** button on every row. It opens a page for that one meeting. Nothing on the page is stored: it is computed from the check-in rows every time it is opened, so there is nothing to maintain and nothing that can go stale.

The page shows the meeting itself (title, description, start and end, slug, whether guests may check in, and whether it has ended), then four numbers:

- **Närvarande vid slutet** or **Närvarande vid sista ändringen**: how many the site counts as in the room. A meeting with a **Sluttid** gets the first label, and the number is read at that end, so a check-in or check-out registered after it is not part of the number. A meeting without one gets the second label, and the number is read after the last check-in or check-out that was registered. It comes from the meeting's own log and not from the clock, so the same log gives the same number whenever the report is opened, which is what makes the page worth printing or filing. `docs/dev/attendance.md` describes both readings.
- **Som mest närvarande**: the largest number in the room at any one moment. That is not stored anywhere, so the page replays the check-ins and check-outs in order to find it.
- **Unika deltagare**: how many different people ever checked in, so somebody who left and came back counts once.
- **Ändringsrader**: how many check-ins and check-outs the meeting has in total, which is the number of rows in the table under these four.

The **Tidslinje** table below is the whole log, oldest first: local time, the name, whether the row is an arrival or a departure, and whether the person is a member or a guest. It is the same data as the **Närvaroändringar** list on the event page, but in the order the meeting actually happened, which is the order to read it in when writing the minutes.

Under that, every poll that was attached to the meeting is printed with its question, whether voting has been ended, each choice with its votes and its share, and three numbers beside each other:

- **Röstsedlar** is the number of ballots: the votes that were cast, counted per choice.
- **Röstande** is the number of signed-in members who voted. A vote from a visitor without an account is not counted here.
- **Närvarande** is the headcount from higher up the page, repeated so it can be compared with the two numbers above it.

Those three can disagree, and the page says why where they are shown. A **Flerval** poll lets one voter tick several choices, so the ballots are then more than the voters. A poll whose **Valmöjligheter** is **Vem som helst** lets one member vote more than once, which inflates the ballots the same way. **Närvarande** being higher than **Röstande** is the ordinary case worth looking for: somebody who was in the room did not vote. While the vote is still running, the poll's own page shows the same pair of numbers (`docs/admin/polls.md`).

## Taking the report away
Two buttons at the top of the report download it:

- **Ladda ner tidslinjen som CSV** is the timeline, one row per check-in or check-out.
- **Ladda ner omröstningarna som CSV** is one row per poll per choice, carrying the votes, the share, the ballots, the voters and the headcount, with the poll and the choice named so that a row still makes sense on its own. The three poll-wide numbers repeat on every row of their poll.

Both files are named after the meeting, for example `narvaro_hostmote_2024-05-01.csv`, and both open directly in Excel. They are written with a semicolon between the columns rather than a comma, because a Swedish Excel reads the comma as the decimal separator; that is deliberate and differs from the invoice export in `docs/admin/billing.md`. The file also starts with a byte-order mark, which is what makes Excel read it as UTF-8, so the "å", "ä" and "ö" in a name stay readable.

## Printing the report
The report prints from the browser's own print dialog, with the usual Ctrl+P (Cmd+P on a Mac). The page carries a print stylesheet, so the printed sheet leaves out the admin's header, user menu, breadcrumbs, sidebar, footer and the report's own download buttons, keeps a table row, a list item and a heading from being cut in half by a page break, and repeats a long table's header row on every page. It does not number the pages, add a header or footer of its own, or make a PDF: that is what a print dialog or a phone's "save as PDF" is for, and the stylesheet deliberately does no more than what is listed above.

To keep a meeting's report for the file, print it while the page is open. The address can also be bookmarked and opened later, because the numbers are computed from the stored rows every time the page is loaded.

## Non-members in the admin
There is no admin page for guests and no guest list to keep tidy. A guest's row is created the first time their name is used on the public check-in form, and it is reused for every later event. So an editor adds a guest by having them check in, not by creating anything. There is no guest record to correct either: a name lives on the change rows and in a shared row that only a developer can rename or delete, and deleting that row removes the name's changes everywhere.

## Deleting events and members
- Deleting an event deletes every attendance change recorded for it, because a change has no meaning outside its event. The guests' names stay, since they are shared between events.
- Deleting a member's account deletes that member's own attendance rows with it. The minutes, not this table, are what outlives a member, so a meeting's record survives even when an account and its attendance history are gone. Export the history first if it has to be kept.

## Permissions
- Being staff is group membership, not a checkbox on the member: the groups named in the site's staff group setting, which for this site are `styrelse`, `admin`, `fotograf` and `rösträknare`, plus superusers.
- Staff status is what shows **Till översiktsvyn**, the code, the QR code, the change log on the event page and the live code and attendee updates on the overview page. It is wider than "the board": a photographer or a vote counter is staff too and can see the code. The app has no smaller permission for the overview page, so keeping a group out of it means changing the staff group list for the site, not unticking something on the member.
- Creating and editing events and change rows in the admin follows the ordinary Django model permissions, so the attendance permissions have to be granted to the group that should create events. Staff status alone lets somebody log in, not edit.
- The report page follows the attendance event view permission, so whoever can open the events list can open a report. The polls on it are a second and separate permission: somebody who may not view questions sees a line saying the polls are hidden instead of the results, and cannot download the poll CSV. The timeline download needs the attendance permission only.

## Troubleshooting
**"Fel kod" is shown over the code box.**
- The code rotated between the participant reading it and pressing the button, and the code they read is now more than one period old. A code keeps working through the period after it is replaced, so somebody who was a few seconds slow is still accepted; anything older than that is not. Read the current code from the overview page and try again.
- Or they are using another event's code. Every event has its own code, so a code shown for a different event never works here. This is the usual mix-up when several events are open at once.
- If somebody scanned the QR code and still sees this, the code changed while they walked to the door. Point them at the current one, or have them scan again.

**The page says "För många felaktiga koder. Försök igen om N sekunder."**
- That browser has entered five wrong codes, so it is locked out for a minute. Nothing was recorded, so ask the participant to wait and try again with the current code. A correct code is refused too while the lockout lasts, which is deliberate.
- The counter lives in that browser's session, so another browser, a private window or clearing cookies starts fresh. Treat it as a speed bump for a fumbling participant or a careless script, not as a security control: what actually keeps people out is the code rotating on the screen.
- If several participants hit it at once, the code they are reading is probably stale. Reload the overview page and check that the code on it is the one in force.

**"Du kan inte gå in i ett evenemang var du redan är närvarande"**
- They are already checked in, usually because the button was pressed twice or the page was opened before they went in. Reload the event page: it shows them as present. Nothing else is needed.
- A guest can also hit this by typing a name that is already checked in, since a name is the whole identity of a guest. Ask them to use a name that is theirs alone.

**"Du kan inte gå ut ur ett evenemang var du inte är närvarande"**
- They have not checked in, or they already checked out. Nothing was written, so reload the event page and press **Gå in** again.

**An event is missing from the public list.**
- Its **Sluttid** has passed. The list shows events that have not ended, so clear or change **Sluttid** if it should be listed again. An event with no **Sluttid** never drops off.
- The event's own page at `/attendance/<slug>/` still works, so a participant who has the link or the QR code can still check in.
- If the page itself is gone, the event was deleted, and its changes went with it.

**The code on the overview page is not changing, or the page says "Anslutningen till servern bröts".**
- The overview page updates over a websocket and retries by itself every few seconds, so the message is the page reporting the gap. The code it shows is the one from when the page was loaded and may be stale, which is what produces "Fel kod" for participants. Reload the page and read the current code from the fresh load. If the message stays, tell a developer, and until then reload the page whenever somebody needs a code.
- The same connection carries the live **Närvarande** list on the overview page, so that list also stands still while the message is shown. A reload brings back both the current code and the current list.

**A participant has no account.**
- They do not need one. If **Tillåt icke-medlemmar att delta** is ticked, they type their name on the event page and check in like anyone else.
- If it is unticked, the event page asks them to log in and a guest cannot check in at all. Tick it and save; the change applies on the next page load, so tick it before the meeting if guests are expected.
- There is nothing to create for them in the admin, and no guest entry to fill in.

**A participant is missing from the Närvarande list even though the change log shows them.**
- On the event page the list is a snapshot, so reload the page. The **Närvarande** list on the staff overview page is live, so a name should appear there without a reload.
- If their newest change is a departure, they are not present, and the log line says **lämnade**.

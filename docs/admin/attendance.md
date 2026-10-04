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
   - **Starttid** and **Sluttid**: when the event begins and ends. **Sluttid** is optional. With it, the event leaves the public list once that moment has passed; without it, the event stays on the list until you delete it.
   - **Tillåt icke-medlemmar att delta**: ticked (the default) means a visitor without an account sees the check-in form and writes their name. Unticked means the event page asks for a login, and a guest cannot check in at all.
   - **Kodens giltighetsperiod (sekunder)**: how long each code is shown before it rotates. 30 is the default, and the field refuses anything below 1 second, because a period of zero breaks the code calculation. A meeting that needs longer to read or scan the code can be given more; a shorter period is harder to pass on to somebody outside the room.
   - **Kodens genereringsnyckel**: the value the codes are computed from. The site fills in a random one, and you can leave it as it is.
3. Save. The event appears on `/attendance/` immediately, and its page is at `/attendance/<slug>/`.

## Running the check-in at the meeting
1. Open the event's page at `/attendance/<slug>/`, and follow **Till översiktsvyn** near the top. Only staff see that link.
2. The overview page at `/attendance/<slug>/overview` shows the current code in large digits with a QR code below it, and the **Närvarande** list under that. The code and the QR code change every **Kodens giltighetsperiod (sekunder)** seconds, and the page updates itself, list included, so leave it on a screen where the participants can see or scan it.
3. The overview page is for staff only. An anonymous visitor who opens the address is asked to log in, and a signed-in member who is not staff gets an error page. That is deliberate: the code is the whole check-in control, so the page that shows it stays with the people running the meeting.
4. Read the code from the screen rather than copying it onto a whiteboard or a printout. It is only valid for its window, so anything written down is stale within seconds.

## Reaching the event page
The site's menus are editor content, not code, so the attendance page reaches them the way any other link does: add a **Static URL** entry (under a **Static Page Nav** category) pointing at `/attendance/`, and it appears in that dropdown. Until such an entry exists, the address is something you give to the participants.

The event list at `/attendance/` is public, and each event has its own address at `/attendance/<slug>/`. The QR code on the overview page is the shortest route to one event: it encodes the event's address as a full link, the kind any phone camera app offers to open, with the current code in it, so a participant who scans it lands on the event page with the code already filled in. Nothing needs to be installed for that, and the page's own **Skanna QR-kod** button reads the same code. Put the event's address in the meeting invitation if people should be able to find it without the QR code, and remember that a guest still needs **Tillåt icke-medlemmar att delta** ticked to use it.

## Checking people in and out
- A signed-in member opens the event page, types the code (or scans the QR code with a phone camera, which opens the same page with the code prefilled) and presses **Gå in**. The member is recorded as themselves, and the page then shows them as present, with **Gå in** disabled and **Gå ut** ready.
- A visitor without an account types their name in the name box, then the code, and presses **Gå in**. The name is what the list keeps. If **Tillåt icke-medlemmar att delta** is unticked there is no name box, and the page asks the visitor to log in instead.
- Nobody can go in twice or go out when not present. For a signed-in member the button that makes no sense is disabled. For everyone, the server refuses the action with a message on the page instead of writing a row: "Du kan inte gå in i ett evenemang var du redan är närvarande" or "Du kan inte gå ut ur ett evenemang var du inte är närvarande".
- The **Närvarande** list at the bottom of the event page is a snapshot from the moment the page was opened, so reload to see who has arrived since. On the staff overview page the same list is live: it picks up a name as that person checks in and drops it as they check out, next to the code and the QR code, which also update by themselves.
- A guest appears on the overview page under exactly the name they typed. The event page's list adds the marker "(icke-medlem)" after a guest's name; the overview page leaves it off, because that label is the one the live update carries.
- The **Närvarande** list is public on the event page: anyone who can open the page sees who is present, including the names guests typed. Only the change log below it is staff-only.
- A guest's name is remembered from one event to the next, because the name is the whole identity of a guest. Two different people who type the same name share one entry and cannot be told apart, so ask guests for a name that is theirs alone, such as first name and surname.

## The change log
- The event page shows a **Närvaroändringar** list to staff under the attendee list: one line per change, newest first, naming the person, the change in Swedish (**anlände** or **lämnade**) and the date and time in the association's own timezone. It is the same data the attendee list is computed from, so it is what to read when the **Närvarande** snapshot on the event page looks out of date.
- The admin also has a standalone list of all attendance changes across every event, and each event's admin page carries the same rows as a collapsed table at the bottom.
- The change rows can be edited and deleted in the admin like any other row, but deleting one changes who counts as present on the public page, because presence is read from the newest row rather than stored. Treat a manual edit as a correction of last resort, and reload the public page afterwards.

## Non-members in the admin
There is no admin page for guests and no guest list to keep tidy. A guest's row is created the first time their name is used on the public check-in form, and it is reused for every later event. So an editor adds a guest by having them check in, not by creating anything. There is no guest record to correct either: a name lives on the change rows and in a shared row that only a developer can rename or delete, and deleting that row removes the name's changes everywhere.

## Deleting events and members
- Deleting an event deletes every attendance change recorded for it, because a change has no meaning outside its event. The guests' names stay, since they are shared between events.
- Deleting a member's account deletes that member's own attendance rows with it. The minutes, not this table, are what outlives a member, so a meeting's record survives even when an account and its attendance history are gone. Export the history first if it has to be kept.

## Permissions
- Being staff is group membership, not a checkbox on the member: the groups named in the site's staff group setting, which for this site are `styrelse`, `admin`, `fotograf` and `rösträknare`, plus superusers.
- Staff status is what shows **Till översiktsvyn**, the code, the QR code, the change log on the event page and the live code and attendee updates on the overview page. It is wider than "the board": a photographer or a vote counter is staff too and can see the code. The app has no smaller permission for the overview page, so keeping a group out of it means changing the staff group list for the site, not unticking something on the member.
- Creating and editing events and change rows in the admin follows the ordinary Django model permissions, so the attendance permissions have to be granted to the group that should create events. Staff status alone lets somebody log in, not edit.

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

# Booking Admin Guide

## Purpose
Room booking lets the association publish the rooms it lends out and lets anyone see them and book one. The room list and each room's page are open to visitors. People who have an account on the website can book straight away; people who do not must unlock the booking form with a shared code. Upcoming bookings also appear in a block on the front page. The board manages the rooms, the bookings and the code in the Django admin.

## Managing Rooms
1. Open **Booking › Utrymmen** in `/admin`. The list shows each room's name, whether it is bookable, and how many bookings it has. Use the search box to find a room by name.
2. Use the add button above the list and fill in:
   - **Namn**: the room name.
   - **Beskrivning**: free text about the room, for example what it contains or how to find it.
   - **Aktiv**: the bookable flag. Leave it ticked while the room can be booked.
3. Save. The room appears on the public booking page immediately.
4. The room page also contains a table of that room's bookings, so you can add or adjust a booking without leaving the room.

The room name and the description are public. The list shows the first 30 words of the description and the room page shows all of it, so do not put internal notes there.

**Aktiv** means bookable. Unticking it removes the room from the public list, from the front-page block and from its own page (a direct link then shows "not found"). The room row and its complete booking history stay in the database and remain visible in the admin, so untick **Aktiv** when a room is only closed for a while. Deleting a room deletes its bookings as well, so use deletion only when the room and its history should really be gone.

## Managing Bookings
Open **Booking › Bokningar**. The list opens furthest away first, so the rows at the top are the bookings still to come and the history sits below them. It has these columns:

- **Utrymme**: the room that was booked.
- **Tid**: the start date and time, followed by the end time.
- **Bokare**: the member who booked, or the name recorded for a booking made by someone without an account. A member's name is written down when the booking is made, so it stays readable here even if that member later deletes the account.
- **Utan konto**: ticked when there is no website account behind the booking. It is also ticked for a booking made by a member who has since deleted the account, so read it together with **Bokare** rather than on its own.

Filters are available by booking origin, by room and by start date, the date drill-down at the top steps through the calendar, and the search box looks in the booker's name, the booker's email and the booking description. The origin filter has three choices:

- **Bokning av en medlem**: the booking is attached to a website account.
- **Bokning utan konto, via webbformuläret**: the booking came from the public form. An address is always recorded there, which is what separates it from the next choice.
- **Bokning utan konto**: no account, whether the booking came from the public form or the account was deleted afterwards.

The last two choices are read from the account and the address, not from a stored marker, so a booking the board entered by hand with no account and an address lands under **Bokning utan konto, via webbformuläret** even though nobody filled in the public form. Treat the filter as a way to narrow the list, not as proof of where a booking came from.

Open a booking to change it. All fields can be edited: **Utrymme**, **Bokare** (the member account, optional), **Namn**, **E-post**, **Starttid**, **Sluttid** and **Beskrivning**. The creation timestamp (**Skapad**) is read-only.

- **To move a booking**, change **Starttid** or **Sluttid** and save.
- **To cancel a booking**, delete it. Deletion cannot be undone, so check the row before confirming.
- The overlap rule is checked here too. Saving a booking that overlaps another booking in the same room is refused with "Utrymmet är redan bokat under denna tid.".
- The end time must be later than the start time, otherwise the save is refused.
- A new booking cannot start in the past: it is refused with "Starttiden kan inte vara i det förflutna.". A few minutes are allowed, because a visitor filling in the form by hand can be a moment late. A booking that already exists keeps whatever times it has, so you can still correct the description of one whose time is over.

**Beskrivning** is where a booker says what the room is for. It is shown on the public form with a note that only the board sees it, and it is visible only here.

The room page carries a table of that room's **upcoming** bookings, soonest first, so a booking can be added or adjusted without leaving the room. Past bookings are not listed there, because a room collects them for years; use **Booking › Bokningar** for those, where the room filter and the date drill-down reach them.

What is public and what is not:

- Public: the room's name and description, and the booking's start and end times. The room list, the room page and the front-page block show nothing else.
- Not public: the booking **description**, the **booker name** and the **booker email**. They are visible only in the admin.
- The booker email is used for one thing: the confirmation message that the site sends to a person who booked without an account. Bookings made by a signed-in member send no email.

If the member account behind a booking is later deleted, the booking itself stays, and it keeps showing the name that was recorded when it was made.

## The Booking Code
The code does not change by itself. It stays exactly as it is until someone with the booking permissions rotates it, so there is no schedule to keep an eye on and no moment of the month when bookers are suddenly locked out.

Open **Booking › Bokningsinställningar**. The page shows:

- **Så får besökare koden**: the board's own sentence about how a booker gets the code. It is optional; see the next section.
- **Aktuell bokningskod**: the code that works right now. It is read-only.
- **Senast bytt**: when the code was last rotated, or **Aldrig** if it never has been.

The code is generated by the site from its own secret and a counter. It cannot be typed in, chosen, copied from anywhere else, or edited, and the settings page has no field for it. The site never stores the code itself, so there is nothing to reveal or reset.

### Rotating the code
1. Open **Booking › Bokningsinställningar**.
2. Tick the settings row.
3. Choose **Byt bokningskoden nu** in the action menu and press **Kör**.
4. The page then tells you the new code. Write it down before you leave the page: the code is not stored anywhere that a later page could show it again, and the next rotation replaces it.

Only someone who may change the booking settings is offered the action.

The previous code keeps working for 15 minutes after a rotation, counted from the moment you rotated it, so a booker who was handed the code just before you rotated is not stranded. Unlocks are not so forgiving: everybody who had already typed the old code has to type the new one, because a rotation ends every unlock at once.

### When to rotate
- When someone who should not have the code has it, for example after it went to the wrong group.
- If the code has been passed around far beyond the association and you want it back under control.
- Not on a calendar. There is no reason to rotate while a code is doing its job, and every rotation costs a round of telling people the new one.

Nothing rotates the code on a schedule, and nothing warns you that a code is old. **Senast bytt** is the only signal, so a board that wants the code to move regularly has to remember to move it. A code that is never rotated stays valid indefinitely, which is why the captcha and the five-attempt limit carry the weight they do; the developer guide says how far those reach.

## Telling Bookers the Code
The board shares the current code with outside bookers through whatever channel it already uses, for example at the office, by phone, in a group chat or by email. The site does not send the code to anyone, and it deliberately does not say how the code reaches a booker, because that is the board's business rather than the website's.

The website does explain the rest. The room list says that an account books directly and that everyone else needs a code, and the page that asks for the code says that the board provides it.

**Så får besökare koden** on **Booking › Bokningsinställningar** is where the board writes its own sentence for that page, if the standard text does not fit: "koden delas ut i kansliet på onsdagar", "fråga i Slackkanalen", or whatever the board actually does. It is shown on the page that asks for the code, above the box. Leave it empty and the page says only that the board provides the code. The text is public, so do not put anything there that bookers should not read. It is written once per association and is not translated, the same as a room's name and description.

Whoever is asked for the code always has a way to reach the board: the association address is in the footer of every page, and the code page and the room page repeat it. The confirmation email carries it too, so a booker whose plans change knows where to turn.

A booker who has unlocked the form stays unlocked for the rest of the current period. When the code rotates, every existing unlock ends, and the next visit asks for a code again. If the booker already has the previous code, it still works during the grace period described above.

## Reaching the Booking Page
The room list is linked from the booking block on the front page. To put it in the site menu as well, add a page under **Static Pages** with the URL `/booking/` and place it through **Page Navigation**. The path is the same in every language, because the website keeps the language in a cookie rather than in the address.

## Permissions
Access to the booking section is controlled by the ordinary Django model permissions. A staff group does not get booking access by being a staff group; the permissions have to be granted deliberately to each group that should have them.

The permissions to grant, by model, with the exact codenames as they appear in the group permission list:

- Utrymme (Room):
  - `booking.view_room`
  - `booking.add_room`
  - `booking.change_room`
  - `booking.delete_room`
- Bokning (Booking):
  - `booking.view_booking`
  - `booking.add_booking`
  - `booking.change_booking`
  - `booking.delete_booking`
- Bokningsinställningar (BookingSettings):
  - `booking.view_bookingsettings`
  - `booking.change_bookingsettings`
  - `booking.add_bookingsettings` and `booking.delete_bookingsettings` also exist, but the site creates the settings row on its own and the admin never offers to delete it, so they are not needed.

Who should have them:

- The board group (`styrelse`) should have all of the permissions above, so the board can manage rooms, bookings and the code.
- Staff groups that have nothing to do with room booking, such as photographers (`fotograf`) and vote counters (`rösträknare`), must not. With these permissions a group could change rooms, delete other people's bookings, or look up the email addresses of outside bookers.
- Grant `booking.view_bookingsettings` only to people who may see the code, because the settings page displays it.
- Any other staff group follows the same rule: no booking access unless it is granted.

How to grant them: open the group on the **Grupper** (**Groups**) page in the admin's authentication section, move the booking permissions from the available list to the chosen list, and save. Granting a permission is what makes the booking section appear for that group; no other step is needed. A group without any of these permissions sees no booking section at all in the admin. Superusers always have access.

## Troubleshooting
**An outside booker says the code is rejected.**
- The code has been rotated since it was shared. Check **Bokningsinställningar** for **Aktuell bokningskod** and pass that on. The old code works for 15 minutes after a rotation and then stops.
- Or the booker typed a wrong code five times and is locked out. The lockout is tied to that visitor's browser and clears by itself after 15 minutes. Using another browser or device starts fresh.

**A room is missing from the public list.**
- Open the room and check that **Aktiv** is ticked. An unticked room is hidden from the public list, from the front page and from its own page, but keeps its whole booking history.

**A booking was rejected as overlapping.**
- Another booking in the same room covers part of that time. Open **Bokningar**, filter by the room, and either change the times or delete the booking that is in the way. The message is "Utrymmet är redan bokat under denna tid.".
- Times that only touch are not an overlap: a booking that ends at 15:00 does not block one that starts at 15:00.

**A booking was rejected because of the times or the name.**
- The end time must be later than the start time.
- The start time cannot be in the past. The visitor picked a date that has already been and gone, which is usually a wrong year or a wrong month; ask them to pick the date again.
- A booking with no member account must have a name, otherwise the admin asks for it ("Ange namnet på den som bokar.").

**A booking is missing from the room page but you know it exists.**
- The room page lists upcoming bookings only. A booking whose time is over is still in **Bokningar**, which the room filter and the date drill-down reach.

**The booking section is not in the admin menu.**
- Under the Unfold admin theme the section appears in the sidebar only for a user who holds at least one of the booking view permissions. Grant them as described under Permissions above.

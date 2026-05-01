# Members Admin Guide

## Purpose
Manage member accounts, memberships, subscription payments, and functionary roles.

## Member Accounts
Most people register themselves at `/members/signup/`. Those signups land in the admin as inactive users; review their details and activate them once payment/eligibility is confirmed. Only use the manual “Add member” flow below when you truly need to create an account on someone’s behalf.

1. Go to **Members › Members** (`/admin/members/member/`).
2. **Add member**:
   - Fill in username (letters/underscore/hyphen only), contact details, membership type, and optional groups.
   - Set a temporary password. Tick **Send email** if you plan to notify the member manually (system does not send the password automatically).
3. **Edit member**:
   - Update contact info, membership type, or group assignments as needed.
   - Use the actions menu to bulk **Activate** or **Deactivate** selected users.
   - `is_staff` is computed automatically from group membership (groups listed in `settings.STAFF_GROUPS`).
4. **Password resets** – direct members to the "Forgot password" link on the login page, which uses the custom reset form.

## Membership Types
- Found under **Members › Membership types**. Each type has a description and a `Behörighetsprofil` (Freshman, Ordinary, Supporting, Senior). These profiles are referenced by other apps (e.g., Polls, Archive) to enforce permissions.

## Subscription Products & Payments
1. **Subscriptions** define name, price, renewal cadence (days/months/years), and whether they expire.
2. **Subscription payments** record actual payments:
   - Use **Add subscription payment** to log membership dues.
   - Pick the member (searchable list), subscription type, payment date, and amount paid.
   - `Date expires` is calculated automatically from the subscription’s renewal settings.
   - List filters help you find expired vs active payments.

## Functionary Roles & Assignments
1. Define positions under **Members › Functionary roles** (mark `Styrelse` if it’s a board seat).
2. Assign members in **Members › Functionaries**:
   - Fill in the member, role, and year.
   - Use filters to review by year or role. Deleting a record removes it from the public functionary list.
3. Members can also manage their own functionary history via `/members/functionary/`, but admin edits override their entries.

## Front-Facing Pages
- `/members/login/` – custom auth view using the `Member` model.
- `/members/info/` – members can edit their profile (first/last name, address, etc.).
- `/members/signup/` – collects new member requests (kept inactive until an admin activates them).
- `/members/functionaries/` – public listing filtered by year/role using data from Functionary models.

## Tips
- When demoting a member (e.g., from Ordinary to Senior), consider their access in other apps (archive, polls) that rely on `permission_profile`.
- Use export tools (e.g., admin changelist CSV) for periodic mailing list updates.

# Members Admin Guide

## Purpose
Manage member accounts, memberships, and subscription payments.

## Member Accounts
Most people register themselves at `/members/signup/`. Those signups land in the admin as inactive users; review their details and activate them once payment/eligibility is confirmed. Only use the manual “Add member” flow below when you truly need to create an account on someone’s behalf.

1. Go to **Members › Members** (`/admin/members/member/`).
2. **Add member**:
   - Fill in username (letters/underscore/hyphen only), contact details, membership type, and optional groups.
   - Set a temporary password. Tick **Send email** if you plan to notify the member manually (system does not send the password automatically).
3. **Edit member**:
    - Update contact info, membership type, or group assignments as needed.
    - On SF, tick **Gulispass utfört** after the member completes the required duty/pass. Until then, both ordinary and lifetime SF members are blocked from the picture and exam archives. The checkbox only appears on SF.
   - Use the actions menu to bulk **Activate** or **Deactivate** selected users.
   - `is_staff` is computed automatically from group membership (groups listed in `settings.STAFF_GROUPS`).
4. **Password resets**: direct members to the "Forgot password" link on the login page, which uses the custom reset form.

## Membership Types
- Found under **Members › Membership types**. Each type has a description and a `Behörighetsprofil` (Freshman, Ordinary, Supporting, Senior). These profiles are referenced by other apps (e.g., Polls, Archive) to enforce permissions.
- SF signup asks applicants to choose **Ordinarie medlem** or **Evig SF:are**, and member administration offers the same two types. Both use ordinary-member behavior outside the separate archive eligibility checkbox. Provisioning does not delete historical membership types that may still be attached to existing records.
- **Ordinarie medlem** costs 15 euro and expires after one year. **Evig SF:are** costs 40 euro and does not expire.

## SF Staff Access
- `styrelse` can administer all site app models except the complete members app.
- `skattis`, `sekre`, `webbansvarig`, and `admin` have full site app model permissions without becoming superusers.
- `Inauta` has full permissions outside the members app. In the member registry it can only show and edit **Evig SF:are** members. Inauta cannot access membership products or payments, create members, change membership types, or change member groups.
- Superusers remain unrestricted.

## Subscription Products & Payments
1. **Subscriptions** define name, price, renewal cadence (days/months/years), and whether they expire.
2. **Subscription payments** record actual payments:
   - Use **Add subscription payment** to log membership dues.
   - Pick the member (searchable list), subscription type, payment date, and amount paid.
   - `Date expires` is calculated automatically from the subscription’s renewal settings.
   - List filters help you find expired vs active payments.

## Functionary Roles & Assignments
Functionary roles and assignments are managed by the `functionaries` app. See the [Functionaries Admin Guide](functionaries.md).

## Front-Facing Pages
- `/members/login/`: custom auth view using the `Member` model.
- `/members/info/`: members can edit their profile (first/last name, address, etc.).
- `/members/signup/`: collects new member requests (kept inactive until an admin activates them).
- `/members/functionaries/`: public functionary listing owned by the `functionaries` app.

## Tips
- When demoting a member (e.g., from Ordinary to Senior), consider their access in other apps (archive, polls) that rely on `permission_profile`.
- Use export tools (e.g., admin changelist CSV) for periodic mailing list updates.

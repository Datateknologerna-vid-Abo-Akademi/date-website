# Functionaries Development Notes

## Responsibility
The `functionaries` app owns yearly positions of trust and the public/member-facing functionary pages.

The public routes remain under the members URL namespace for compatibility:
- `/members/functionary/` (`members:functionary`) lets logged-in members manage their own history.
- `/members/functionaries/` (`members:functionaries`) shows the public year/role listing.

## Models
- `FunctionaryRole` defines a translated position title and whether it is a board seat.
- `Functionary` links a role to a year and either a `Member` or standalone display `name`.
- When a linked member has no stored display name, `Functionary.save()` snapshots the member's current full name or username.

## Forms & Selectors
- `FunctionaryForm` enforces uniqueness per `(member, role, year)` for member-managed entries.
- `functionaries.selectors` groups and filters functionaries by year, role, and board/non-board status for the public listing.

## Admin
- `FunctionaryRoleAdmin` includes an inline `Functionary` table so role metadata and yearly assignments can be edited together.
- `FunctionaryAdmin` links each assignment back to its role and supports searching by linked member or standalone display name.

## Migration Notes
- Data was split out from `members.FunctionaryRole` and `members.Functionary`.
- The split migration preserves primary keys and translated role titles, then drops the legacy members functionary tables after copying.

## Extending
- Keep member account concerns in `members`; add position/history behavior here.
- If standalone functionary display needs richer metadata, add those fields to this app rather than `members`.

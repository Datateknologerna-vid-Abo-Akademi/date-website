# Site Shell (date app) Admin Guide

## Purpose
The `date` app powers the front page (`/`) and language switcher. There are no database models to edit, but content curators should know which other apps feed the landing page.

## What Appears on the Front Page
- **Events** – pulled automatically from the Events app (next 31 days plus selected past entries).
- **News** – latest three posts without a category.
- **Ads** – every banner stored in the Ads app.
- **Instagram posts** – URLs managed through the Social app.
- **Albins Angels highlight** – appears if a news post in the "Albins Angels" category was published within the last 10 days.

## Editor Checklist
1. Before big announcements, verify that Events, News, Ads, and Social entries are up to date. The front page simply mirrors those tables.
2. Use the `language` dropdown on the site (or visit `/lang/fi/` and `/lang/sv/`) to confirm translations look correct. The current language is stored in the session.
3. Custom error pages (`/404`, `/500`) live in `templates/core`. Content updates require developer help.

## No Direct Admin Models
- Because the `date` app only aggregates data, there is nothing to edit under `/admin` for this module. Manage content in the respective source apps instead.

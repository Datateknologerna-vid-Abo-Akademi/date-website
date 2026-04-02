# Lucia Admin Guide

## Purpose
Showcase Lucia candidates, their bios, and the related poll links during the annual election. Everything is managed through a single model called **Lucia**.

## Access
1. Log in to `/admin`.
2. Open **Lucia › Lucian** (`/admin/lucia/candidate/`). Each row corresponds to one candidate card.

## Add or Edit a Candidate
1. Click **Add lucia** (or choose an existing entry).
2. Populate the fields:
   - **Bild URL** – paste a publicly accessible image URL (square images look best).
   - **Titel** – candidate name and class year if desired.
   - **Innehåll** – bio text (supports rich formatting via CKEditor).
   - **Publicera** – uncheck to hide the candidate while drafting.
   - **Slug** – lowercase identifier for detail URLs (`/lucia/<slug>/`). Must be unique.
   - **Poll URL** – link to the external poll (usually a Google Form or internal Polls view).
3. Click **Save**. Published candidates appear automatically on `/lucia/` and `/lucia/<slug>/`.

## Publishing Workflow Tips
- Draft entries with **Publicera** unchecked until copy and images are approved.
- Reuse the previous year’s entry by duplicating it (use the **Save as new** button) and then updating text/URLs.
- The list page orders candidates by creation order; use consistent naming if you want a particular display order.

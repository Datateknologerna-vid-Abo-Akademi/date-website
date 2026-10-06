# Instagram Admin Guide

## Purpose
Manage the Instagram posts shown in the scrolling slider on the home page (kk and Impuls).

## Adding a post
1. In `/admin`, open **Social & Ads › Instagram URLs** and click **Add**.
2. **Bild** – upload the post's image (a screenshot or the original photo works). It must be at least 300 px tall so it stays sharp in the slider; smaller images are rejected with a message.
3. **Instagram-inlägg** – paste the link to the post, e.g. `https://www.instagram.com/p/ABC123/`. It is saved as the post's code, and clicking the image in the slider opens the post.
4. Leave **URL** empty; it is only used by the automatic updater.
5. Save. The newest post is shown first; delete old posts to keep the slider short. When there are no posts, the slider is hidden.

## Automatic updater (kk)
Sites with an Instagram account configured (currently kk) can also fill the slider automatically. Those posts have a **URL** instead of an uploaded image, are replaced on every update, and their images expire if the updater stops running. Posts with an uploaded image are never touched by the updater.

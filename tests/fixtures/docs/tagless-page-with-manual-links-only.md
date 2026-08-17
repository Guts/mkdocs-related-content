---
title: Tagless page with manual links only
related_content:
  links:
    - page-a.md
    - tagless-page-with-manual-links-only.md
    - this-page-does-not-exist.md
---

# Tagless page with manual links only

No `tags` at all - must still be indexed (kept) purely because of its
`related_content.links`, but never gets automatic suggestions of its own,
nor is it ever suggested to others via scoring. Also lists itself
(self-reference, must be dropped) and a page that doesn't exist (broken
reference, must be skipped without crashing the build).

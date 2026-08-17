---
title: Page with manual links
tags:
  - oauth
related_content:
  links:
    - page-c.md
    - Custom label: page-d.md
    - https://example.org/external-resource/
    - Clean external label: https://example.org/other-resource/
---

# Page with manual links

Shares the `oauth` tag with `page-b.md` (one automatic candidate, score
1/3), but also hand-picks four manual links via `related_content.links`,
mixing the two supported shapes (bare target, and `{label: target}`) for
both internal and external targets. Manual links must appear first, in
this exact order, before the automatic `page-b.md` suggestion.

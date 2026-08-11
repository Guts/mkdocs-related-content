---
title: Page with malformed related_content frontmatter
tags:
  - api
related_content: true
---

# Page with malformed related_content frontmatter

`related_content` is a bare boolean here, not a mapping - the plugin must
not crash on this, and must not treat it as an opt-out either: only the
documented `exclude_from_scoring: true` shape does that.

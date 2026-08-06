---
title: Integrations
description: How the Related Content plugin integrates with MaterialX/Material's built-in tags plugin
tags:
  - integrations
  - materialx
  - material
  - tags
---

## MaterialX / Material `tags` plugin

If your `mkdocs.yml` uses `theme.name: materialx` (supported) or `theme.name: material` (unsupported since it's unmaintained), and declares the built-in `tags` plugin, this plugin detects it automatically. No configuration needed beyond [`use_material_tags`](configuration.md#plugin-options), which is `true` by default.

```yaml
theme:
  name: materialx # or: material
[...]
plugins:
  - tags
  - related-content
```

### What gets reused, and what doesn't

It would be natural to expect this plugin to simply read `tags.json`, the file the `tags` plugin can export. It doesn't, and this is a deliberate, tested consequence of MkDocs' build lifecycle rather than a missing feature:

The `tags` plugin builds its page/tag mapping - and `tags.json` - incrementally, finishing only once every page has been processed (`on_post_build`). A page's own Jinja context, however, is built earlier, while pages are still being processed one by one. `tags.json` (and the `tags` plugin's internal mapping) is only complete *after* every page's HTML has already been rendered - too late to use for filling in that page's `related_pages`.

What *is* available at any point of the build is the `tags` plugin's static **configuration** - in particular `tags_allowed`, the optional allow-list of valid tag names. This plugin reads it (when `use_material_tags` is enabled) and applies the same filter to its own, independently-computed tag index, so a page's `related_pages` never includes a tag that wouldn't appear on the MaterialX/Material tags index page either.

!!! note "A note on `tags_allowed` and `Tag` objects"
    MaterialX/Material's `tags_allowed` setting doesn't hold plain strings: it validates into a `set` of the theme's own `Tag` objects, whose `__eq__` only compares against other `Tag` instances - comparing one to a plain Python `str` raises an `AssertionError` rather than returning `False`. This plugin normalizes them to their string names before using them, so this stays an implementation detail you never have to think about.

### Avoiding a duplicate `tags.json`

When both the theme's own `tags` plugin and `export_tags_json` (on by default here) are active, this plugin checks whether the `tags` plugin already exports its own JSON, and skips its own fallback export in that case - see [`export_tags_json`](configuration.md#plugin-options).

```yaml
plugins:
  - tags # exports its own tags.json
  - related-content # -> no related-tags.json written, avoids a duplicate
```

Without the `tags` plugin (or with a different theme entirely), this plugin exports its own JSON at `site_dir/related-tags.json` by default, shaped the same way (`{"mappings": [{"item": {"url": ..., "title": ...}, "tags": [...]}]}`), for anyone who wants to reuse it (e.g. a client-side search widget).

----

## Any other theme

Without MaterialX/Material's `tags` plugin, or with a different theme entirely, the plugin works exactly the same way, just without the `tags_allowed` alignment: every tag found in a page's frontmatter is considered valid.

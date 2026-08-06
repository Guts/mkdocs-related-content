---
title: Configuration
description: Configuration steps and settings for the MkDocs Related Content plugin
tags:
  - options
  - plugin
  - settings
---

To compute related pages, the plugin uses:

- the [`tags`](https://www.mkdocs.org/user-guide/writing-your-docs/#yaml-style-meta-data) key in each page's YAML frontmatter
- some [plugin options](#plugin-options) to tune scoring and display
- optionally, [the MaterialX/Material `tags` plugin's own configuration](integrations.md), when present

## Page attributes

| Attribute | Expected level | Effect |
| :-------- | :-------------: | :----- |
| `page.meta.tags` | **required** for a page to participate | A page without `tags` is skipped entirely: it's never scored, and never listed as related to another page. |
| `page.meta.title` | *optional* | Used as the related page's display title. If absent, the plugin falls back to the page's first Markdown heading, then to a humanized filename - see [How it works](index.md#how-the-score-is-computed). |

----

## Plugin options

Minimal option:

```yaml
plugins:
  - related-content
```

Full options, with their defaults:

```yaml
plugins:
  - related-content:
      enabled: true
      export_tags_json: true
      max_related: 5
      min_score: 0.1
      section_title: "Related contents"
      tags_json_filename: related-tags.json
      use_material_tags: true
```

| Option | Type | Default | Description |
| :----- | :--- | :------ | :----------- |
| `enabled` | `bool` | `true` | Set to `false` to disable the plugin without removing it from `mkdocs.yml` (e.g. via an environment-driven override). |
| `section_title` | `str` | `"Contenus liés"` | Exposed to Jinja as `related_content_section_title`. Purely informational - the plugin doesn't render any HTML itself, your template decides where and how to use it. |
| `max_related` | `int` | `5` | Maximum number of related pages kept per page, after sorting by descending score. |
| `min_score` | `float` | `0.1` | Minimum [Jaccard score](index.md#how-the-score-is-computed) (between `0` and `1`) for a page to be considered related. Raise it for stricter, higher-confidence matches only. |
| `use_material_tags` | `bool` | `true` | Whether to align tag filtering with MaterialX/Material's `tags` plugin configuration (`tags_allowed`), when that theme and plugin are active. Set to `false` to ignore it entirely. See [Integrations](integrations.md). |
| `export_tags_json` | `bool` | `true` | Whether to write a fallback `tags.json`-shaped export at `on_post_build`. Automatically skipped when MaterialX/Material's own `tags` plugin already exports one, to avoid a duplicate. |
| `tags_json_filename` | `str` | `related-tags.json` | Filename of the fallback export, relative to `site_dir`. Only written when `export_tags_json` is `true` and the condition above applies. |

----

## Jinja context

Two variables are added to every page's template context.

See [the quickstart](index.md#quickstart) for a minimal template example.

| Variable | Type |
| :------- | :--- |
| `related_pages` | `list[RelatedPage]`, possibly empty |
| `related_content_section_title` | `str` |

Each `RelatedPage` exposes: `title` (`str`), `url` (`str`), `shared_tags` (`list[str]`), `score` (`float`, rounded to 3 decimals).

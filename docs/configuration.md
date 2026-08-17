---
title: Configuration
description: Configuration steps and settings for the MkDocs Related Content plugin
tags:
  - options
  - plugin
  - settings
related_content:
  links:
    - MaterialX blog plugin links: https://jaywhj.github.io/mkdocs-materialx/plugins/blog.html#meta.links
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
| `page.meta.related_content.exclude_from_scoring` | *optional* | Set to `true` to opt a page out entirely - same effect as failing [`match_path`](#plugin-options), but decided per-page rather than site-wide. The page is never scored, never shown as related content elsewhere, and never given related pages of its own. |
| `page.meta.related_content.links` | *optional* | List of hand-picked pages (or external URLs) this page's author wants prioritized over automatic suggestions. See below. |

Typical YAML front-matter:

```yaml
---
title: "Life: the best tutorial to enjoy it!"
tags:
  - clickbait
  - life
related_content:
  exclude_from_scoring: true
  links:
    - some-page.md
    - Custom label: some-other-page.md
    - https://example.org/some-external-resource/
    - Clean label: https://example.org/some-other-resource/
---
```

!!! note "Not the same as `hide: [related_content]`"
    `hide: [related_content]` (see [the quickstart](index.md#quickstart)) only hides *that page's own* related-pages block - a template-level check, and the page still counts normally in the site-wide similarity computation. `exclude_from_scoring` is the opposite: enforced by the plugin itself, it removes the page from the computation altogether, in both directions.

### Manual links

Entries in `related_content.links` are shown first (in the order they're listed) before any automatically-computed suggestion and always shown regardless of [`min_score`](#plugin-options), since they're an explicit author choice.

The syntax follows MaterialX/Material's own [blog plugin `links` property](https://jaywhj.github.io/mkdocs-materialx/plugins/blog.html#meta.links): each entry is either a bare target, or a single-key `{label: target}` mapping for an explicit, clean title. A given `label` always wins over any auto-resolved title, even the page's own real title.

!!! important
    Nested sections (a mapping whose value is itself a list, as the blog plugin also supports for its nav-like sidebar) aren't supported here since they don't map to a flat related-content list. They are silently skipped rather than failing the build.

A target may be:

- **internal**: a `src_uri` (`docs_dir` relative, same convention as `match_path`). Without a `label`, the title/tags/relative URL are resolved the same way as automatic suggestions. A reference to a page that doesn't exist is skipped silently (logged at debug level), not an error. A self-reference is dropped.
- **external**: any URL with a scheme (`https://...`, `mailto:...`, protocol-relative `//...`). It's used exactly as written: no title or tags to resolve. So without a `label`, `RelatedPage.title` falls back to the URL itself and `shared_tags` is always empty.

A page can have `related_content.links` without any `tags` at all, it's still indexed (so its manual links get resolved), it just never receives automatic suggestions of its own, and is never suggested to others via scoring.

The plugin never adds a manually-linked page a second time among the automatic suggestions on the same page. See [`max_related`](#plugin-options) and `max_manual_related` for how the two combine.

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
      css_class: related-pages
      export_tags_json: true
      match_path: ".*"
      max_related: 5
      max_manual_related: 5
      min_score: 0.1
      weight_by_tag_rarity: false
      section_title: "Related contents"
      tags_json_filename: related-tags.json
      use_material_tags: true
```

| Option | Type | Default | Description |
| :----- | :--- | :------ | :----------- |
| `enabled` | `bool` | `true` | Set to `false` to disable the plugin without removing it from `mkdocs.yml` (e.g. via an environment-driven override). |
| `match_path` | `str` | `".*"` | Regular expression matched against each page's `src_uri`. A page that doesn't match is excluded from the whole feature: it's never indexed, so it never appears as related content for another page, and never gets a related-pages list of its own. Same option name and semantics as [mkdocs-rss-plugin's `match_path`](https://guts.github.io/mkdocs-rss-plugin/configuration/#match_path). |
| `section_title` | `str` | `"Related contents"` | Exposed to Jinja as `related_content_section_title`. Purely informational - the plugin doesn't render any HTML itself, your template decides where and how to use it. |
| `css_class` | `str` | `"related-pages"` | Exposed to Jinja as `related_content_css_class`, for the same reason: a stable, known class name themes can target, that you can rename to avoid clashing with an existing theme class. |
| `max_related` | `int` | `5` | Maximum number of related pages shown per page, **manual and automatic cumulated**. See [manual links](#manual-links). |
| `max_manual_related` | `int` | `5` | Maximum number of *manual* links (`related_content.links` in the page's YAML frontmatter) honored within that total. Remaining slots, up to `max_related` are filled with automatic suggestions. |
| `min_score` | `float` | `0.1` | Minimum [Jaccard score](index.md#how-the-score-is-computed) (between `0` and `1`) for a page to be considered related. Only applies to automatic suggestions - manual links always show regardless. Raise it for stricter, higher-confidence automatic matches only. |
| `weight_by_tag_rarity` | `bool` | `false` | When `true`, a shared tag counts for more the fewer pages on the site use it - a tag on 2 pages out of 500 is a stronger signal than one on half the site. See [How it works](index.md#weighting-by-tag-rarity). |
| `use_material_tags` | `bool` | `true` | Whether to align tag filtering with MaterialX/Material's `tags` plugin configuration (`tags_allowed`), when that theme and plugin are active. Set to `false` to ignore it entirely. See [Integrations](integrations.md). |
| `export_tags_json` | `bool` | `true` | Whether to write a fallback `tags.json`-shaped export at `on_post_build`. Automatically skipped when MaterialX/Material's own `tags` plugin already exports one, to avoid a duplicate. |
| `tags_json_filename` | `str` | `related-tags.json` | Filename of the fallback export, relative to `site_dir`. Only written when `export_tags_json` is `true` and the condition above applies. |

----

## Jinja context

Three variables are added to every page's template context.

See [the quickstart](index.md#quickstart) for a minimal template example.

| Variable | Type |
| :------- | :--- |
| `related_pages` | `list[RelatedPage]`, possibly empty |
| `related_content_section_title` | `str` |
| `related_content_css_class` | `str` |

Each `RelatedPage` exposes: `title` (`str`), `url` (`str`), `shared_tags` (`list[str]`), `score` (`float`, rounded to 3 decimals), `manual` (`bool` - `true` for a hand-picked link, see [manual links](#manual-links)).

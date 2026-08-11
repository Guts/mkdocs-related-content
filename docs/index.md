---
title: The MkDocs Related Content Plugin
description: "Automatically compute and display related pages based on shared tags, for any MkDocs site."
tags:
  - tags
  - Mkdocs
  - plugin
  - related content
---

A plugin for [MkDocs](https://www.mkdocs.org) which computes, for every tagged page, a list of related pages based on shared tags - and exposes it to the Jinja context so your theme can render a "Related content" / "See also" section.

## Quickstart

Installation:

```sh
pip install mkdocs-related-content-plugin
```

Then in your `mkdocs.yml`:

```yaml
plugins:
  - related-content
```

The plugin exposes three Jinja variables to every page's template context:

| Variable | Type | Description |
| :------- | :--- | :----------- |
| `related_pages` | `list[RelatedPage]` | The related pages for the current page, sorted by descending similarity score. Empty if the page has no tags, or no other page shares one. |
| `related_content_section_title` | `str` | The configured section title (see [`section_title`](configuration.md#section_title)). |
| `related_content_css_class` | `str` | A stable CSS class themes can target, or rename to avoid clashing with an existing one (see [`css_class`](configuration.md#css_class)). |

Each `RelatedPage` has: `title`, `url` (already relative to the page being rendered - ready to use as-is in an `href`, no need for Mkdocs' `| url` filter), `shared_tags` (the list of tags in common with the current page) and `score` (the [Jaccard similarity](https://en.wikipedia.org/wiki/Jaccard_index), between 0 and 1).

A minimal template override:

```jinja title="overrides/partials/related.html"
{% if related_pages and "related_content" not in (page.meta.hide or []) %}
<div class="{{ related_content_css_class }}">
  <h2>{{ related_content_section_title }}</h2>
  <ul>
  {% for r in related_pages %}
    <li><a href="{{ r.url }}">{{ r.title }}</a></li>
  {% endfor %}
  </ul>
</div>
{% endif %}
```

!!! tip "Hiding the block on a specific page"
    The `"related_content" not in (page.meta.hide or [])` check follows MaterialX/Material's own [`hide` frontmatter convention](https://jaywhj.github.io/mkdocs-materialx/setup/setting-up-navigation.html#hiding-the-sidebars) (the same one used for `hide: [navigation]` or `hide: [toc]`) - so a page can opt out of the block with:

    ```yaml
    ---
    hide:
      - related_content
    ---
    ```

    This is purely a template-level check: the plugin itself doesn't read `hide` and knows nothing about it. The page is still indexed and scored normally, and still shows up as related content *on other pages* - only its own block is suppressed. Since the plugin doesn't render any HTML itself, this only works if your template includes the check above.

Included from your theme's `main.html`:

```jinja title="overrides/main.html"
{% extends "base.html" %}
{% block content %}
  {{ super() }}
  {% include "partials/related.html" %}
{% endblock %}
```

----

## How the score is computed

Two pages' relatedness is their [Jaccard similarity](https://en.wikipedia.org/wiki/Jaccard_index): the size of the intersection of their tags, divided by the size of the union.

$$
score(A, B) = |tags(A) ∩ tags(B)| / |tags(A) ∪ tags(B)|
$$

A page with tags `[api, auth, python]` and a page with tags `[api, oauth]` share one tag (`api`) out of four distinct tags across both pages, for a score of `0.25`. Identical tag sets score `1.0`; pages with no tag in common score `0.0` and are never listed as related.

!!! tip
    See [Configuration](configuration.md) to adjust the minimum score (`min_score`) and the maximum number of related pages shown (`max_related`).

----

## Weighting by tag rarity

By default, every tag counts equally: two pages sharing a tag half the site uses (say `guide`) are treated exactly like two pages sharing one only they use (say `oauth-pkce`) - as long as the set sizes are the same, the score is the same.

Setting [`weight_by_tag_rarity: true`](configuration.md#plugin-options) changes that: each tag is weighted by the inverse of how many pages on the site use it (`1 / page_count`), and that weight - instead of a flat `1` - is what gets summed on both sides of the Jaccard ratio.

$$
score(A, B) = \frac{\sum_{t \, \in \, tags(A) \, \cap \, tags(B)} weight(t)}{\sum_{t \, \in \, tags(A) \, \cup \, tags(B)} weight(t)}
$$

Concretely: a tag used by only 2 pages gets a weight of `0.5`; a tag used by 250 pages gets `0.004`. Two pages sharing the rare tag end up scored far higher than two pages sharing the common one, even if the rest of their tags are otherwise identical in number. The score still stays between `0` and `1` either way - with every tag weighted `1` (the default), this is exactly the plain Jaccard score above.

----

## Why this couldn't just read `tags.json`

If your theme is [MaterialX](https://jaywhj.github.io/mkdocs-materialx/) or [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) with its built-in `tags` plugin enabled, you might expect this plugin to simply read the `tags.json` file that plugin can export. It can't, and the reason is a genuine constraint of MkDocs' build lifecycle, not an oversight:

The `tags` plugin builds its page/tag mapping - and the `tags.json` export - incrementally, page by page, and only finishes once *every* page has been processed (at `on_post_build`). But a page's own Jinja context is built *before* that point, while pages are still being processed one by one. By the time `tags.json` (or the `tags` plugin's internal mapping) is complete, every page's HTML has already been rendered.

This plugin works around that by reading every page's YAML frontmatter **directly from disk** during the `on_files` event - before MkDocs has rendered a single page. See [Integrations](integrations.md) for how it still stays consistent with the `tags` plugin's own configuration (e.g. `tags_allowed`) despite not being able to read its output.

## Credits

- Package layout, testing patterns and documentation structure are directly inspired by [Guts/mkdocs-rss-plugin](https://github.com/Guts/mkdocs-rss-plugin).
- Feature scope inspired by [this MaterialX discussion](https://github.com/jaywhj/mkdocs-materialx/discussions/117) on automatic "Related content" sections.

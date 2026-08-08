#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

# for class autoref typing
from __future__ import annotations

# standard library
from dataclasses import dataclass, field

# ############################################################################
# ########## Classes ###############
# ##################################


@dataclass
class PageTagsEntry:
    """Lightweight, timing-safe representation of one page's tags.

    Built directly from a page's YAML frontmatter during `on_files` - i.e.
    straight from disk, *before* Mkdocs has read/rendered a single page.
    This is what makes it possible to know every page's tags before
    computing relatedness for the very first one.

    `title` starts as a best-effort guess (frontmatter `title`, else first
    Markdown heading, else a humanized filename) and gets superseded by the
    real `Page.title` wherever that's already available - see
    `util.Util.resolve_related_pages`.
    """

    src_uri: str
    url: str
    tags: list[str] = field(default_factory=list)
    fallback_title: str | None = None


@dataclass
class RelatedPage:
    """One entry exposed to the Jinja template for a single related page."""

    title: str
    url: str
    """Relative to the page it's attached to (see `Util.resolve_related_pages`),
    ready to use as-is in an `href` - unlike `PageTagsEntry.url`, which is
    root-relative."""
    shared_tags: list[str] = field(default_factory=list)
    score: float = 0.0

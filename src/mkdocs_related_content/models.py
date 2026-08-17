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


@dataclass(frozen=True)
class ManualLink:
    """One entry from a page's own `related_content.links` frontmatter.

    Follows the same syntax as MaterialX/Material's blog plugin `links`
    property: a bare string (`target`, no `label`), or a single-key
    mapping (`{label: target}`). Nested sections (a mapping whose value is
    itself a list) aren't supported here - they make sense for a real nav
    sidebar, not a flat related-content list - and are skipped with a debug
    log rather than causing a build error.
    """

    target: str
    """`src_uri` (docs_dir-relative) or external URL."""
    label: str | None = None
    """Explicit title override, if given. Always wins over any
    auto-resolved title - see `Util.resolve_related_pages`."""


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
    manual_links: tuple[ManualLink, ...] = ()
    """This page's own `related_content.links` frontmatter, in the order
    they were listed - see `ManualLink`."""


@dataclass
class RelatedPage:
    """One entry exposed to the Jinja template for a single related page."""

    title: str
    url: str
    """Relative to the page it's attached to (see `Util.resolve_related_pages`),
    ready to use as-is in an `href` - unlike `PageTagsEntry.url`, which is
    root-relative. Exception: an external manual link's `url` is used
    exactly as written in the frontmatter, unchanged."""
    shared_tags: list[str] = field(default_factory=list)
    score: float = 0.0
    manual: bool = False
    """True for a page listed in the current page's own `related_content.links`
    frontmatter, rather than computed from tag similarity."""

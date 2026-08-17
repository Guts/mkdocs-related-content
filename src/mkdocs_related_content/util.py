#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

from __future__ import annotations

# standard library
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

# 3rd party
from mkdocs.plugins import get_plugin_logger
from mkdocs.utils import get_relative_url
from mkdocs.utils import meta as mkdocs_meta

# package
from mkdocs_related_content.constants import (
    FIRST_HEADING_PATTERN,
    FRONTMATTER_EXCLUDE_FROM_SCORING_KEY,
    FRONTMATTER_KEY,
    FRONTMATTER_LINKS_KEY,
    MKDOCS_LOGGER_NAME,
)
from mkdocs_related_content.models import ManualLink, PageTagsEntry, RelatedPage

if TYPE_CHECKING:
    from mkdocs.structure.files import Files

# ############################################################################
# ########## Globals #############
# ################################

logger = get_plugin_logger(MKDOCS_LOGGER_NAME)

_FIRST_HEADING_RE = re.compile(FIRST_HEADING_PATTERN, re.MULTILINE)


def _is_external_link(link: str) -> bool:
    """True for anything that isn't a docs_dir-relative internal path.

    Covers `http://`, `https://`, `mailto:`, protocol-relative `//cdn...`,
    and any other URL with a scheme - not just the two most common ones,
    since a `related_content.links` entry could reasonably be a `mailto:`
    or an `ftp://` link too.
    """
    return bool(urlparse(link).scheme) or link.startswith("//")


def _parse_manual_links(raw_links: list, self_src_uri: str) -> tuple[ManualLink, ...]:
    """Parse a page's `related_content.links` frontmatter into `ManualLink`s.

    Follows the same `nav`-like syntax as MaterialX/Material's blog plugin
    `links` property (https://jaywhj.github.io/mkdocs-materialx/plugins/blog.html#meta.links):
    each entry is either a bare string (target, no label) or a single-key
    mapping (`{label: target}`). Nested sections (mapping value is a list,
    as the blog plugin also supports for its nav-like sidebar) aren't
    supported here - they don't map to a flat related-content list - and
    are skipped with a debug log rather than failing the build. A
    self-reference is dropped; duplicate targets keep only the first
    occurrence, in the author's own order.

    Args:
        raw_links: the raw `related_content.links` list from frontmatter.
        self_src_uri: the page's own `src_uri`, to filter self-references.

    Returns:
        Parsed, deduplicated, ordered `ManualLink`s.
    """
    seen: set[str] = set()
    parsed: list[ManualLink] = []

    for item in raw_links:
        target: str | None = None
        label: str | None = None

        if isinstance(item, str):
            target = item
        elif isinstance(item, dict) and len(item) == 1:
            label, value = next(iter(item.items()))
            if isinstance(value, str):
                target = value
            else:
                logger.debug(
                    "'related_content.links' entry has a nested section "
                    f"under {label!r}, which isn't supported here - skipped."
                )
                continue
        else:
            logger.debug(
                f"Unrecognized 'related_content.links' entry, skipped: {item!r}"
            )
            continue

        target = str(target)
        if target == self_src_uri or target in seen:
            continue
        seen.add(target)
        parsed.append(ManualLink(target=target, label=str(label) if label else None))

    return tuple(parsed)


# ############################################################################
# ########## Classes ###############
# ##################################


class Util:
    """Standalone helpers for the Related Content plugin.

    Kept free of any Mkdocs event wiring so the scoring logic can be unit
    tested on its own - same separation of concerns as mkdocs-rss-plugin's
    own `Util` class.
    """

    def build_tags_index(
        self,
        files: Files,
        allowed_tags: set[str] | None = None,
        match_path_pattern: re.Pattern[str] | None = None,
    ) -> dict[str, PageTagsEntry]:
        """Build a {src_uri: PageTagsEntry} index by reading YAML frontmatter
        directly from disk.

        This intentionally does *not* rely on `Page.meta`: at `on_files`
        time, no page has been read by Mkdocs yet, so this is the only way
        to know every page's tags before rendering the first one.

        Args:
            files: Mkdocs' global Files collection.
            allowed_tags: optional allow-list (typically Material's tags
                plugin `tags_allowed` setting) used to discard unknown tags.
                None means no filtering.
            match_path_pattern: optional compiled regex (see the plugin's
                `match_path` option) matched against each page's `src_uri`.
                A page that doesn't match is skipped entirely - it never
                appears as a related page for another page, and never gets
                related pages of its own, since it's absent from the
                returned index either way. `None` means every page matches.

        A page can also opt itself out via its own YAML frontmatter,
        regardless of `match_path`:

        ```yaml
        related_content:
          exclude_from_scoring: true
        ```

        This has the exact same effect as failing `match_path` - the page
        is entirely absent from the returned index - but is a per-page
        author decision rather than a site-wide, path-based one. Unlike
        the `hide: [related_content]` frontmatter convention (a purely
        template-level check - see docs/index.md), this is read and
        enforced by the plugin itself, before any candidate scoring runs.

        A page can also pin its own hand-picked suggestions, which take
        priority over automatically-computed ones (see
        `resolve_related_pages`):

        ```yaml
        related_content:
          links:
            - some-page.md
            - Custom label: some-other-page.md
            - https://example.org/some-external-resource/
        ```

        Same `nav`-like syntax as MaterialX/Material's blog plugin `links`
        property - a bare string, or a single-key `{label: target}` mapping
        for an explicit title (always used as-is, no auto-resolution) - see
        `_parse_manual_links`. A target may be internal (`src_uri`-style) or
        an external URL. A page with `links` but no `tags` is still indexed
        (it just never gets automatic suggestions of its own, nor is it
        ever suggested to others via scoring).

        Returns:
            The index, keyed by `File.src_uri`. A page is omitted only if
            it has neither a (valid) tag nor any `related_content.links`.
        """
        index: dict[str, PageTagsEntry] = {}

        for file in files.documentation_pages():
            if match_path_pattern is not None and not match_path_pattern.match(
                file.src_uri
            ):
                continue

            if not file.abs_src_path:
                # generated / in-memory files have no source to read from
                continue

            try:
                source = Path(file.abs_src_path).read_text(encoding="utf-8-sig")
            except OSError as err:
                logger.debug(f"Unable to read {file.abs_src_path}: {err}")
                continue

            _, page_meta = mkdocs_meta.get_data(source)

            related_content_meta = page_meta.get(FRONTMATTER_KEY)
            if isinstance(related_content_meta, dict) and related_content_meta.get(
                FRONTMATTER_EXCLUDE_FROM_SCORING_KEY
            ):
                continue

            tags = [str(tag) for tag in (page_meta.get("tags") or [])]

            if allowed_tags is not None:
                tags = [tag for tag in tags if tag in allowed_tags]

            manual_links: tuple[ManualLink, ...] = ()
            if isinstance(related_content_meta, dict):
                raw_links = related_content_meta.get(FRONTMATTER_LINKS_KEY)
                if isinstance(raw_links, list):
                    manual_links = _parse_manual_links(raw_links, file.src_uri)

            if not tags and not manual_links:
                continue

            index[file.src_uri] = PageTagsEntry(
                src_uri=file.src_uri,
                url=file.url,
                tags=tags,
                fallback_title=self._guess_title(
                    page_meta=page_meta, source=source, src_uri=file.src_uri
                ),
                manual_links=manual_links,
            )

        logger.debug(f"{len(index)} page(s) indexed with tags and/or manual links.")
        return index

    @staticmethod
    def _guess_title(page_meta: dict, source: str, src_uri: str) -> str:
        """Best-effort title, used only until Mkdocs resolves the real one.

        Mirrors (loosely) how Mkdocs itself resolves `Page.title`: frontmatter
        `title`, else the first Markdown heading, else a humanized filename.
        """
        if page_meta.get("title"):
            return str(page_meta["title"])

        match = _FIRST_HEADING_RE.search(source)
        if match:
            return match.group(1).strip()

        return Path(src_uri).stem.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def compute_tag_weights(tags_index: dict[str, PageTagsEntry]) -> dict[str, float]:
        """Weight each tag by the inverse of how many pages use it.

        A tag shared by only 2 pages out of 500 is a much stronger signal
        of relatedness than a tag half the site uses - this gives the
        former a weight of `0.5` and the latter `1/250 = 0.004`, so it
        counts for much less in `jaccard_score`.

        Args:
            tags_index: output of `build_tags_index`.

        Returns:
            {tag: weight}, weight = 1 / number of pages using that tag.
        """
        frequency: dict[str, int] = {}
        for entry in tags_index.values():
            for tag in entry.tags:
                frequency[tag] = frequency.get(tag, 0) + 1
        return {tag: 1 / count for tag, count in frequency.items()}

    @staticmethod
    def jaccard_score(
        tags_a: set[str],
        tags_b: set[str],
        tag_weights: dict[str, float] | None = None,
    ) -> float:
        """Similarity between two tag sets: |intersection| / |union|.

        Computes the union via inclusion-exclusion
        (`|a| + |b| - |a & b|`, or the weighted equivalent below) instead
        of building the union set itself (`a | b`) - same result, one
        fewer set allocation per call, which matters here since this runs
        inside `compute_related_pages`'s O(N^2) loop.

        When `tag_weights` is given (see `compute_tag_weights`), each tag
        contributes its weight instead of a flat `1` to both the
        intersection and union sums - rare, shared tags count for more
        than common ones. The result stays between 0 and 1 either way,
        since the intersection is always a subset of the union.

        Args:
            tags_a: tags of the first page.
            tags_b: tags of the second page.
            tag_weights: optional per-tag weight, e.g. from
                `compute_tag_weights`. A tag missing from this mapping
                falls back to a weight of `1`. `None` (the default) is
                equivalent to every tag weighing `1` - the plain,
                unweighted Jaccard score.

        Returns:
            A score between 0 (no shared tag) and 1 (identical tag sets).
        """
        intersection = tags_a & tags_b

        if tag_weights is None:
            union_size = len(tags_a) + len(tags_b) - len(intersection)
            return len(intersection) / union_size if union_size else 0.0

        def weight_sum(tags: set[str]) -> float:
            return sum(tag_weights.get(t, 1) for t in tags)

        intersection_weight = weight_sum(intersection)
        # same inclusion-exclusion as above, applied to weighted sums
        # instead of counts: sum(A) + sum(B) double-counts the shared
        # (intersection) part once too many, hence subtracting it back out.
        union_weight = weight_sum(tags_a) + weight_sum(tags_b) - intersection_weight
        return intersection_weight / union_weight if union_weight else 0.0

    def compute_related_pages(
        self,
        tags_index: dict[str, PageTagsEntry],
        min_score: float,
        max_related: int,
        tag_weights: dict[str, float] | None = None,
    ) -> dict[str, list[tuple[float, str]]]:
        """Precompute every page's related pages.

        Args:
            tags_index: output of `build_tags_index`.
            min_score: minimum score for a page to be considered related.
            max_related: maximum number of related pages kept per page -
                shared between automatic and manual suggestions together,
                see `resolve_related_pages`.
            tag_weights: optional per-tag weight passed to `jaccard_score`
                (see `compute_tag_weights`). `None` (the default) scores
                every tag equally.

        A page's own `related_content.links` targets (see `build_tags_index`)
        are kept out of its *automatic* candidates here, before `max_related`
        caps the list - a page already pinned manually never wastes a slot
        that a fresh automatic candidate could fill instead.

        Returns:
            {src_uri: [(score, related_src_uri), ...]}, sorted by descending
            score and capped to `max_related`.
        """
        related: dict[str, list[tuple[float, str]]] = {
            src_uri: [] for src_uri in tags_index
        }

        tags_by_page = {
            src_uri: set(entry.tags) for src_uri, entry in tags_index.items()
        }
        manual_targets_by_page = {
            src_uri: {link.target for link in entry.manual_links}
            for src_uri, entry in tags_index.items()
        }

        pages_by_tag: dict[str, list[str]] = defaultdict(list)
        for src_uri, tags in tags_by_page.items():
            for tag in tags:
                pages_by_tag[tag].append(src_uri)

        seen_pairs: set[tuple[str, str]] = set()
        for pages in pages_by_tag.values():
            for src_uri_a, src_uri_b in combinations(pages, 2):
                pair = (
                    (src_uri_a, src_uri_b)
                    if src_uri_a < src_uri_b
                    else (src_uri_b, src_uri_a)
                )
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                score = self.jaccard_score(
                    tags_by_page[pair[0]],
                    tags_by_page[pair[1]],
                    tag_weights=tag_weights,
                )
                if score < min_score:
                    continue
                # one-directional: pair[0] manually pinning pair[1] doesn't
                # stop pair[1] from suggesting pair[0] back automatically.
                if pair[1] not in manual_targets_by_page[pair[0]]:
                    related[pair[0]].append((score, pair[1]))
                if pair[0] not in manual_targets_by_page[pair[1]]:
                    related[pair[1]].append((score, pair[0]))

        for src_uri, scored in related.items():
            # Ties (same score) are broken by src_uri, not left to whatever
            # order pairs happened to be discovered in - which pages make
            # the `max_related` cut must stay stable across builds and
            # implementations (e.g. an inverted-index-based rewrite of this
            # loop), not depend on incidental dict/traversal order.
            scored.sort(key=lambda pair: (-pair[0], pair[1]))
            related[src_uri] = scored[:max_related]

        return related

    def resolve_related_pages(
        self,
        related: list[tuple[float, str]],
        tags_index: dict[str, PageTagsEntry],
        current_tags: set[str],
        files: Files,
        current_page_url: str,
        manual_links: tuple[ManualLink, ...] = (),
        max_related: int = 5,
        max_manual_related: int = 5,
    ) -> list[RelatedPage]:
        """Turn automatic candidates and the page's own manual links into
        template-ready `RelatedPage` objects, manual ones first.

        Prefers the real, fully-resolved `Page.title` whenever Mkdocs has
        already produced it (i.e. the related page was processed earlier in
        the build), and falls back to the frontmatter/heading guess from
        `tags_index` otherwise. In practice the two are almost always
        identical. A manual link's own `label` (see `ManualLink`), when
        given, always wins over both - it's an explicit author choice.

        `RelatedPage.url` is computed relative to `current_page_url` (via
        Mkdocs' own `get_relative_url`) rather than left root-relative like
        `tags_index[...].url` is. Root-relative URLs (e.g. `sub/page-b/`)
        only resolve correctly from the site root - used directly as
        `href="{{ r.url }}"` in a template, they produce a wrong link for
        any page that isn't at the site root itself. Resolving them here
        means every consumer gets a correct, ready-to-use `href` without
        having to remember to apply Mkdocs' `| url` Jinja filter themselves.
        An *external* manual link (see `_is_external_link`) is the one
        exception - its `url` is used exactly as written, since there's no
        internal file to resolve it against.

        Manual links (`related_content.links`, see `build_tags_index`) are
        resolved first, capped to `max_manual_related`, and always shown
        regardless of `min_score` - an explicit author choice overrides the
        automatic threshold. Remaining slots, up to `max_related` in total,
        go to automatic candidates - `compute_related_pages` already keeps
        those free of anything also listed manually, so no duplicate work
        and no wasted slot.

        Args:
            related: `(score, src_uri)` pairs, typically from
                `compute_related_pages`.
            tags_index: output of `build_tags_index`.
            current_tags: tags of the page these related pages are for.
            files: Mkdocs' global Files collection, used to reach the real
                `Page` object when it's already available.
            current_page_url: root-relative URL of the page these related
                pages are for (`page.url`), used to make each `RelatedPage.url`
                relative to it.
            manual_links: this page's own `related_content.links`, in
                frontmatter order - typically `tags_index[this_page].manual_links`.
            max_related: total number of related pages shown, manual and
                automatic combined.
            max_manual_related: maximum number of manual links honored
                within that total.

        Returns:
            Ready-to-render related pages: manual ones first (in the
            author's own order), then automatic ones by descending score.
        """
        resolved: list[RelatedPage] = []
        seen_src_uris: set[str] = set()

        for manual_link in manual_links[:max_manual_related]:
            target = manual_link.target
            if target in seen_src_uris:
                continue

            if _is_external_link(target):
                # no file to resolve, no tags to compare, no relative URL
                # to compute - used exactly as written in the frontmatter
                resolved.append(
                    RelatedPage(
                        title=manual_link.label or target,
                        url=target,
                        shared_tags=[],
                        score=1.0,
                        manual=True,
                    )
                )
                seen_src_uris.add(target)
                continue

            other_file = files.get_file_from_path(target)
            if other_file is None:
                logger.debug(
                    f"'related_content.links' entry not found, skipped: {target}"
                )
                continue

            entry = tags_index.get(target)
            if manual_link.label:
                title = manual_link.label
            else:
                title = entry.fallback_title if entry is not None else None
                if other_file.page is not None and other_file.page.title:
                    title = other_file.page.title

            shared_tags = (
                sorted(current_tags & set(entry.tags)) if entry is not None else []
            )

            resolved.append(
                RelatedPage(
                    title=title or target,
                    url=get_relative_url(other_file.url, current_page_url),
                    shared_tags=shared_tags,
                    score=1.0,
                    manual=True,
                )
            )
            seen_src_uris.add(target)

        auto_budget = max(0, max_related - len(resolved))
        for score, src_uri in related[:auto_budget]:
            if src_uri in seen_src_uris:
                continue

            entry = tags_index[src_uri]
            other_file = files.get_file_from_path(src_uri)

            title = entry.fallback_title
            if other_file is not None and other_file.page and other_file.page.title:
                title = other_file.page.title

            resolved.append(
                RelatedPage(
                    title=title or src_uri,
                    url=get_relative_url(entry.url, current_page_url),
                    shared_tags=sorted(current_tags & set(entry.tags)),
                    score=round(score, 3),
                    manual=False,
                )
            )
            seen_src_uris.add(src_uri)

        return resolved

    def write_tags_json(
        self,
        tags_index: dict[str, PageTagsEntry],
        files: Files,
        site_dir: str,
        filename: str,
    ) -> None:
        """Write a `tags.json`-shaped export, as a fallback when Material's
        tags plugin isn't available to produce one itself.

        Meant to be called from `on_post_build`: by then every page has been
        processed, so titles/URLs are fully resolved - unlike the index
        built in `on_files`, which only has best-effort titles.

        Args:
            tags_index: output of `build_tags_index`.
            files: Mkdocs' global Files collection.
            site_dir: build output directory (`config.site_dir`).
            filename: name of the JSON file to write, relative to `site_dir`.
        """
        mappings = []
        for src_uri, entry in tags_index.items():
            other_file = files.get_file_from_path(src_uri)
            title = entry.fallback_title
            if other_file is not None and other_file.page and other_file.page.title:
                title = other_file.page.title

            mappings.append(
                {
                    "item": {"url": entry.url, "title": title},
                    "tags": entry.tags,
                }
            )

        out_path = Path(site_dir) / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"mappings": mappings}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"Tags JSON export written to {out_path}")

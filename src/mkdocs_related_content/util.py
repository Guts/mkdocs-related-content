#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

from __future__ import annotations

# standard library
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

# 3rd party
from mkdocs.plugins import get_plugin_logger
from mkdocs.utils import get_relative_url
from mkdocs.utils import meta as mkdocs_meta

# package
from mkdocs_related_content.constants import (
    FIRST_HEADING_PATTERN,
    MKDOCS_LOGGER_NAME,
)
from mkdocs_related_content.models import PageTagsEntry, RelatedPage

if TYPE_CHECKING:
    from mkdocs.structure.files import Files

# ############################################################################
# ########## Globals #############
# ################################

logger = get_plugin_logger(MKDOCS_LOGGER_NAME)

_FIRST_HEADING_RE = re.compile(FIRST_HEADING_PATTERN, re.MULTILINE)

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
        self, files: Files, allowed_tags: set[str] | None = None
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

        Returns:
            The index, keyed by `File.src_uri`. Pages without any (valid)
            tag are omitted.
        """
        index: dict[str, PageTagsEntry] = {}

        for file in files.documentation_pages():
            if not file.abs_src_path:
                # generated / in-memory files have no source to read from
                continue

            try:
                source = Path(file.abs_src_path).read_text(encoding="utf-8-sig")
            except OSError as err:
                logger.debug(f"Unable to read {file.abs_src_path}: {err}")
                continue

            _, page_meta = mkdocs_meta.get_data(source)
            tags = [str(tag) for tag in (page_meta.get("tags") or [])]

            if allowed_tags is not None:
                tags = [tag for tag in tags if tag in allowed_tags]

            if not tags:
                continue

            index[file.src_uri] = PageTagsEntry(
                src_uri=file.src_uri,
                url=file.url,
                tags=tags,
                fallback_title=self._guess_title(
                    page_meta=page_meta, source=source, src_uri=file.src_uri
                ),
            )

        logger.debug(f"{len(index)} page(s) indexed with tags.")
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

        Computes the union's *size* via inclusion-exclusion
        (`len(a) + len(b) - len(a & b)`) instead of building the union set
        itself (`a | b`) - same result, one fewer set allocation per call,
        which matters here since this runs inside `compute_related_pages`'s
        O(N^2) loop.

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
        intersection = len(tags_a & tags_b)
        union = len(tags_a) + len(tags_b) - intersection
        if not union:
            return 0.0

        if tag_weights is None:
            return intersection / union

        intersection_weight = sum(tag_weights.get(t, 1) for t in tags_a & tags_b)
        union_weight = sum(tag_weights.get(t, 1) for t in union)
        return intersection_weight / union_weight if union_weight else 0.0

    def compute_related_pages(
        self,
        tags_index: dict[str, PageTagsEntry],
        min_score: float,
        max_related: int,
        tag_weights: dict[str, float] | None = None,
    ) -> dict[str, list[tuple[float, str]]]:
        """Precompute every page's related pages in a single pass.

        Only unique pairs are scored (N*(N-1)/2 instead of N*(N-1)), since
        the Jaccard score is symmetric. Each page's tags are converted to a
        `set` once upfront, rather than once per pair it appears in -
        rebuilding it inside the inner loop would mean up to N-1 redundant
        `set()` calls per page, on top of the O(N^2) pair count itself.

        Args:
            tags_index: output of `build_tags_index`.
            min_score: minimum score for a page to be considered related.
            max_related: maximum number of related pages kept per page.
            tag_weights: optional per-tag weight passed to `jaccard_score`
                (see `compute_tag_weights`). `None` (the default) scores
                every tag equally.

        Returns:
            {src_uri: [(score, related_src_uri), ...]}, sorted by descending
            score and capped to `max_related`.
        """
        related: dict[str, list[tuple[float, str]]] = {
            src_uri: [] for src_uri in tags_index
        }

        entries = [(src_uri, set(entry.tags)) for src_uri, entry in tags_index.items()]
        for i, (src_uri_a, tags_a) in enumerate(entries):
            for src_uri_b, tags_b in entries[i + 1 :]:
                score = self.jaccard_score(tags_a, tags_b, tag_weights=tag_weights)
                if score < min_score:
                    continue
                related[src_uri_a].append((score, src_uri_b))
                related[src_uri_b].append((score, src_uri_a))

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
    ) -> list[RelatedPage]:
        """Turn `(score, src_uri)` pairs into template-ready `RelatedPage` objects.

        Prefers the real, fully-resolved `Page.title` whenever Mkdocs has
        already produced it (i.e. the related page was processed earlier in
        the build), and falls back to the frontmatter/heading guess from
        `tags_index` otherwise. In practice the two are almost always
        identical.

        `RelatedPage.url` is computed relative to `current_page_url` (via
        Mkdocs' own `get_relative_url`) rather than left root-relative like
        `tags_index[...].url` is. Root-relative URLs (e.g. `sub/page-b/`)
        only resolve correctly from the site root - used directly as
        `href="{{ r.url }}"` in a template, they produce a wrong link for
        any page that isn't at the site root itself. Resolving them here
        means every consumer gets a correct, ready-to-use `href` without
        having to remember to apply Mkdocs' `| url` Jinja filter themselves.

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

        Returns:
            Ready-to-render related pages, in the same order as `related`.
        """
        resolved: list[RelatedPage] = []

        for score, src_uri in related:
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
                )
            )

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

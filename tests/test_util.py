#! python3  # noqa: E265

"""Usage from the repo root folder:

.. code-block:: python

    # for whole test module
    python -m unittest tests.test_util
"""

# #############################################################################
# ########## Libraries #############
# ##################################

# Standard library
import json
import re
import tempfile
import unittest
from pathlib import Path

# 3rd party
from mkdocs.config import load_config
from mkdocs.structure.files import get_files

# plugin target
from mkdocs_related_content.models import ManualLink, PageTagsEntry
from mkdocs_related_content.util import Util, _parse_manual_links

# #############################################################################
# ########## Classes ###############
# ##################################


class TestUtilScoring(unittest.TestCase):
    """Test the pure scoring logic, independent from any MkDocs object."""

    @classmethod
    def setUpClass(cls):
        """Executed when module is loaded before any test."""
        cls.plg_utils = Util()

    # -- TESTS ---------------------------------------------------------
    def test_jaccard_score_partial_overlap(self):
        score = self.plg_utils.jaccard_score({"a", "b"}, {"a", "c"})
        self.assertAlmostEqual(score, 1 / 3)

    def test_jaccard_score_identical_sets(self):
        score = self.plg_utils.jaccard_score({"a", "b"}, {"a", "b"})
        self.assertEqual(score, 1.0)

    def test_jaccard_score_no_overlap(self):
        score = self.plg_utils.jaccard_score({"a"}, {"b"})
        self.assertEqual(score, 0.0)

    def test_jaccard_score_both_empty(self):
        """Two pages without tags must not raise a ZeroDivisionError."""
        score = self.plg_utils.jaccard_score(set(), set())
        self.assertEqual(score, 0.0)

    def test_jaccard_score_weights_none_matches_unweighted(self):
        """`tag_weights=None` (the default) is the plain, unweighted score."""
        score = self.plg_utils.jaccard_score({"a", "b"}, {"a", "c"}, tag_weights=None)
        self.assertAlmostEqual(score, 1 / 3)

    def test_jaccard_score_weighted_favors_rarer_shared_tag(self):
        """A shared tag with a lower weight (rarer) counts for more."""
        weights = {"common": 0.1, "rare": 0.5}

        # sharing only the frequent tag
        score_common = self.plg_utils.jaccard_score(
            {"common", "x1"}, {"common", "x2"}, tag_weights=weights
        )
        # sharing only the rare tag
        score_rare = self.plg_utils.jaccard_score(
            {"rare", "x1"}, {"rare", "x2"}, tag_weights=weights
        )
        # same set shape either way (2 tags, 1 shared) - unweighted these tie
        unweighted = self.plg_utils.jaccard_score({"common", "x1"}, {"common", "x2"})
        self.assertAlmostEqual(unweighted, 1 / 3)

        self.assertGreater(score_rare, score_common)

    def test_compute_tag_weights_is_inverse_frequency(self):
        index = {
            "a.md": PageTagsEntry(src_uri="a.md", url="a/", tags=["common", "rare"]),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["common"]),
            "c.md": PageTagsEntry(src_uri="c.md", url="c/", tags=["common"]),
            "d.md": PageTagsEntry(src_uri="d.md", url="d/", tags=["common"]),
        }
        weights = self.plg_utils.compute_tag_weights(index)

        # "common" is used by 4 pages -> weight 1/4 ; "rare" by 1 -> weight 1
        self.assertEqual(weights["common"], 0.25)
        self.assertEqual(weights["rare"], 1.0)

    def test_compute_related_pages_with_weights_changes_ranking(self):
        """Unweighted, `page-b` and `page-c` tie with `page-a` (same set
        shape). Weighted by rarity, `page-c` (shares the rarer tag) ranks
        strictly above `page-b` (shares the more common one).
        """
        index = {
            "page-a.md": PageTagsEntry(
                src_uri="page-a.md", url="a/", tags=["common", "rare"]
            ),
            "page-b.md": PageTagsEntry(
                src_uri="page-b.md", url="b/", tags=["common", "x1"]
            ),
            "page-c.md": PageTagsEntry(
                src_uri="page-c.md", url="c/", tags=["rare", "x2"]
            ),
            # filler pages, just to make "common" more frequent than "rare"
            "filler-1.md": PageTagsEntry(
                src_uri="filler-1.md", url="f1/", tags=["common"]
            ),
            "filler-2.md": PageTagsEntry(
                src_uri="filler-2.md", url="f2/", tags=["common"]
            ),
        }

        unweighted = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.0, max_related=5
        )
        scores_unweighted = {src: score for score, src in unweighted["page-a.md"]}
        self.assertAlmostEqual(
            scores_unweighted["page-b.md"], scores_unweighted["page-c.md"]
        )

        weights = self.plg_utils.compute_tag_weights(index)
        weighted = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.0, max_related=5, tag_weights=weights
        )
        scores_weighted = {src: score for score, src in weighted["page-a.md"]}
        self.assertGreater(scores_weighted["page-c.md"], scores_weighted["page-b.md"])

    def test_compute_related_pages_symmetry_and_threshold(self):
        index = {
            "a.md": PageTagsEntry(
                src_uri="a.md", url="a/", tags=["api", "auth", "python"]
            ),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["api", "oauth"]),
            "c.md": PageTagsEntry(src_uri="c.md", url="c/", tags=["gardening"]),
        }

        related = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.1, max_related=5
        )

        # a and b share one tag out of three -> related to each other
        self.assertEqual(related["a.md"], [(0.25, "b.md")])
        self.assertEqual(related["b.md"], [(0.25, "a.md")])
        # c shares nothing with anyone
        self.assertEqual(related["c.md"], [])

    def test_compute_related_pages_scores_multi_tag_overlap_once(self):
        """`a.md` and `b.md` share every one of their tags. The inverted
        index groups candidate pairs by tag, so this pair is a candidate
        under 3 different tags - it must still be scored (and appear in
        the result) exactly once, not 3 times.
        """
        index = {
            "a.md": PageTagsEntry(
                src_uri="a.md", url="a/", tags=["api", "auth", "python"]
            ),
            "b.md": PageTagsEntry(
                src_uri="b.md", url="b/", tags=["api", "auth", "python"]
            ),
        }

        related = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.1, max_related=5
        )

        self.assertEqual(related["a.md"], [(1.0, "b.md")])
        self.assertEqual(related["b.md"], [(1.0, "a.md")])

    def test_compute_related_pages_excludes_own_manual_links_from_auto_pool(self):
        """`a.md` manually pins `b.md` via `related_content.links`. Even
        though they'd also score highly by tags, `b.md` must not appear a
        second time in `a.md`'s *automatic* candidates -
        `resolve_related_pages` is what actually shows the manual entry,
        this is purely about not wasting an automatic slot on a duplicate.
        """
        index = {
            "a.md": PageTagsEntry(
                src_uri="a.md",
                url="a/",
                tags=["api", "auth"],
                manual_links=(ManualLink(target="b.md"),),
            ),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["api", "auth"]),
            "c.md": PageTagsEntry(src_uri="c.md", url="c/", tags=["api"]),
        }

        related = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.1, max_related=1
        )

        self.assertEqual(len(related["a.md"]), 1)
        self.assertEqual(related["a.md"][0][1], "c.md")
        # one-directional: b.md doesn't manually link a.md back, so
        # a.md still shows up in b.md's own automatic candidates
        self.assertEqual(related["b.md"], [(1.0, "a.md")])

    def test_compute_related_pages_respects_max_related(self):
        index = {
            "a.md": PageTagsEntry(src_uri="a.md", url="a/", tags=["api"]),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["api"]),
            "c.md": PageTagsEntry(src_uri="c.md", url="c/", tags=["api"]),
            "d.md": PageTagsEntry(src_uri="d.md", url="d/", tags=["api"]),
        }

        related = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.1, max_related=2
        )

        # b, c and d all tie at score 1.0 with a - which 2 make the cut
        # must be deterministic (src_uri order), not incidental
        self.assertEqual(related["a.md"], [(1.0, "b.md"), (1.0, "c.md")])

    def test_compute_related_pages_ties_are_broken_deterministically(self):
        """Same pages, same tags, inserted in a different order: the
        `max_related` cut must land on the same pages regardless, or a
        rebuild - or a future rewrite of this loop (e.g. an inverted-index
        traversal instead of a full pairwise scan) - could silently change
        which related pages a reader sees.
        """
        entries = {
            "z.md": PageTagsEntry(src_uri="z.md", url="z/", tags=["api"]),
            "a.md": PageTagsEntry(src_uri="a.md", url="a/", tags=["api"]),
            "m.md": PageTagsEntry(src_uri="m.md", url="m/", tags=["api"]),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["api"]),
        }
        index_in_order = {k: entries[k] for k in ["z.md", "a.md", "m.md", "b.md"]}
        index_reversed = {k: entries[k] for k in ["b.md", "m.md", "a.md", "z.md"]}

        related_in_order = self.plg_utils.compute_related_pages(
            tags_index=index_in_order, min_score=0.1, max_related=2
        )
        related_reversed = self.plg_utils.compute_related_pages(
            tags_index=index_reversed, min_score=0.1, max_related=2
        )

        # both must keep the 2 alphabetically-first src_uris, in the same
        # order, no matter which order the pages were discovered in
        expected = [(1.0, "a.md"), (1.0, "b.md")]
        self.assertEqual(related_in_order["z.md"], expected)
        self.assertEqual(related_reversed["z.md"], expected)

    def test_compute_related_pages_respects_min_score(self):
        index = {
            "a.md": PageTagsEntry(
                src_uri="a.md", url="a/", tags=["api", "auth", "python"]
            ),
            "b.md": PageTagsEntry(src_uri="b.md", url="b/", tags=["api", "oauth"]),
        }

        # score between a and b is 0.25 -> excluded by a stricter threshold
        related = self.plg_utils.compute_related_pages(
            tags_index=index, min_score=0.5, max_related=5
        )
        self.assertEqual(related["a.md"], [])

    def test_resolve_related_pages_uses_fallback_title_without_page(self):
        index = {
            "a.md": PageTagsEntry(src_uri="a.md", url="a/", tags=["api"]),
            "b.md": PageTagsEntry(
                src_uri="b.md", url="b/", tags=["api"], fallback_title="Title B"
            ),
        }

        class _FakeFiles:
            """Stand-in for `mkdocs.structure.files.Files`: no Page resolved yet."""

            def get_file_from_path(self, path):
                return None

        resolved = self.plg_utils.resolve_related_pages(
            related=[(1.0, "b.md")],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="a/",
        )

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].title, "Title B")
        # relative to current_page_url ("a/"), not root-relative ("b/")
        self.assertEqual(resolved[0].url, "../b/")
        self.assertEqual(resolved[0].shared_tags, ["api"])
        self.assertEqual(resolved[0].score, 1.0)

    def test_resolve_related_pages_prefers_real_page_title(self):
        index = {
            "b.md": PageTagsEntry(
                src_uri="b.md", url="b/", tags=["api"], fallback_title="Fallback title"
            ),
        }

        class _FakePage:
            title = "Resolved Mkdocs Title"

        class _FakeFile:
            page = _FakePage()

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()

        resolved = self.plg_utils.resolve_related_pages(
            related=[(1.0, "b.md")],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="a/",
        )

        self.assertEqual(resolved[0].title, "Resolved Mkdocs Title")

    def test_resolve_related_pages_manual_links_appear_first(self):
        """Manual links come before automatic ones, in the author's own
        frontmatter order - regardless of automatic score.
        """
        index = {
            "auto.md": PageTagsEntry(src_uri="auto.md", url="auto/", tags=["api"]),
            "manual-1.md": PageTagsEntry(
                src_uri="manual-1.md", url="m1/", tags=["api"]
            ),
            "manual-2.md": PageTagsEntry(
                src_uri="manual-2.md", url="m2/", tags=["api"]
            ),
        }

        class _FakeFile:
            page = None
            url = "fake/"

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()  # every manual/auto src_uri "exists"

        resolved = self.plg_utils.resolve_related_pages(
            related=[(1.0, "auto.md")],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(
                ManualLink(target="manual-1.md"),
                ManualLink(target="manual-2.md"),
            ),
        )

        self.assertEqual(
            [r.title for r in resolved], ["manual-1.md", "manual-2.md", "auto.md"]
        )
        self.assertEqual([r.manual for r in resolved], [True, True, False])

    def test_resolve_related_pages_label_wins_over_resolved_title(self):
        """A manual link's own `label` always wins, even when the real
        page title is available via `Page.title`.
        """
        index = {
            "b.md": PageTagsEntry(
                src_uri="b.md", url="b/", tags=["api"], fallback_title="Fallback"
            ),
        }

        class _FakePage:
            title = "Real Mkdocs Title"

        class _FakeFile:
            page = _FakePage()
            url = "fake/"

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()

        resolved = self.plg_utils.resolve_related_pages(
            related=[],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(ManualLink(target="b.md", label="My Own Label"),),
        )

        self.assertEqual(resolved[0].title, "My Own Label")

    def test_resolve_related_pages_external_manual_link(self):
        class _FakeFiles:
            def get_file_from_path(self, path):
                return None

        resolved = self.plg_utils.resolve_related_pages(
            related=[],
            tags_index={},
            current_tags=set(),
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(ManualLink(target="https://example.org/resource/"),),
        )

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].title, "https://example.org/resource/")
        self.assertEqual(resolved[0].url, "https://example.org/resource/")
        self.assertEqual(resolved[0].shared_tags, [])
        self.assertEqual(resolved[0].score, 1.0)
        self.assertTrue(resolved[0].manual)

    def test_resolve_related_pages_external_manual_link_with_label(self):
        class _FakeFiles:
            def get_file_from_path(self, path):
                return None

        resolved = self.plg_utils.resolve_related_pages(
            related=[],
            tags_index={},
            current_tags=set(),
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(
                ManualLink(target="https://example.org/resource/", label="Clean Label"),
            ),
        )

        self.assertEqual(resolved[0].title, "Clean Label")
        self.assertEqual(resolved[0].url, "https://example.org/resource/")

    def test_resolve_related_pages_broken_manual_link_is_skipped(self):
        """A `related_content.links` entry pointing to a page that doesn't
        exist must be skipped, not crash the build.
        """

        class _FakeFiles:
            def get_file_from_path(self, path):
                return None

        resolved = self.plg_utils.resolve_related_pages(
            related=[],
            tags_index={},
            current_tags=set(),
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(ManualLink(target="this-page-does-not-exist.md"),),
        )

        self.assertEqual(resolved, [])

    def test_resolve_related_pages_respects_max_manual_related(self):
        index = {
            f"m{i}.md": PageTagsEntry(src_uri=f"m{i}.md", url=f"m{i}/", tags=["api"])
            for i in range(4)
        }

        class _FakeFile:
            page = None
            url = "fake/"

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()

        resolved = self.plg_utils.resolve_related_pages(
            related=[],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=tuple(ManualLink(target=t) for t in index),
            max_manual_related=2,
        )

        self.assertEqual(len(resolved), 2)

    def test_resolve_related_pages_auto_budget_shrinks_with_manual_count(self):
        """`max_related` is the *combined* total: 2 manual links leave
        only 1 slot for automatic candidates, even though 2 are available.
        """
        index = {
            "manual-1.md": PageTagsEntry(
                src_uri="manual-1.md", url="m1/", tags=["api"]
            ),
            "manual-2.md": PageTagsEntry(
                src_uri="manual-2.md", url="m2/", tags=["api"]
            ),
            "auto-1.md": PageTagsEntry(src_uri="auto-1.md", url="a1/", tags=["api"]),
            "auto-2.md": PageTagsEntry(src_uri="auto-2.md", url="a2/", tags=["api"]),
        }

        class _FakeFile:
            page = None
            url = "fake/"

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()

        resolved = self.plg_utils.resolve_related_pages(
            related=[(0.9, "auto-1.md"), (0.8, "auto-2.md")],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(
                ManualLink(target="manual-1.md"),
                ManualLink(target="manual-2.md"),
            ),
            max_related=3,
        )

        self.assertEqual(len(resolved), 3)
        self.assertEqual(
            [r.title for r in resolved], ["manual-1.md", "manual-2.md", "auto-1.md"]
        )

    def test_resolve_related_pages_no_duplicate_between_manual_and_auto(self):
        """Even if `related` (automatic candidates) somehow still contains
        a src_uri that's also manually linked, it must not be shown twice.
        """
        index = {
            "shared.md": PageTagsEntry(src_uri="shared.md", url="s/", tags=["api"]),
        }

        class _FakeFile:
            page = None
            url = "fake/"

        class _FakeFiles:
            def get_file_from_path(self, path):
                return _FakeFile()

        resolved = self.plg_utils.resolve_related_pages(
            related=[(1.0, "shared.md")],
            tags_index=index,
            current_tags={"api"},
            files=_FakeFiles(),
            current_page_url="current/",
            manual_links=(ManualLink(target="shared.md"),),
        )

        self.assertEqual(len(resolved), 1)
        self.assertTrue(resolved[0].manual)


class TestParseManualLinks(unittest.TestCase):
    """Test `_parse_manual_links` in isolation - the `nav`-like syntax
    parsing for `related_content.links`, independent of any file I/O.
    """

    def test_bare_string_has_no_label(self):
        parsed = _parse_manual_links(["some-page.md"], self_src_uri="current.md")
        self.assertEqual(parsed, (ManualLink(target="some-page.md", label=None),))

    def test_single_key_mapping_sets_label(self):
        parsed = _parse_manual_links(
            [{"Custom label": "some-page.md"}], self_src_uri="current.md"
        )
        self.assertEqual(
            parsed, (ManualLink(target="some-page.md", label="Custom label"),)
        )

    def test_mixed_shapes_preserve_order(self):
        parsed = _parse_manual_links(
            ["a.md", {"B label": "b.md"}, "https://example.org/c/"],
            self_src_uri="current.md",
        )
        self.assertEqual(
            parsed,
            (
                ManualLink(target="a.md"),
                ManualLink(target="b.md", label="B label"),
                ManualLink(target="https://example.org/c/"),
            ),
        )

    def test_nested_section_is_skipped(self):
        """A mapping whose value is a list (blog plugin's nav-like
        sections) isn't supported for a flat related-content list.
        """
        parsed = _parse_manual_links(
            [{"Section": ["a.md", "b.md"]}, "c.md"], self_src_uri="current.md"
        )
        self.assertEqual(parsed, (ManualLink(target="c.md"),))

    def test_multi_key_mapping_is_skipped(self):
        """Ambiguous - which key is the label? - so skipped entirely."""
        parsed = _parse_manual_links(
            [{"Label 1": "a.md", "Label 2": "b.md"}, "c.md"],
            self_src_uri="current.md",
        )
        self.assertEqual(parsed, (ManualLink(target="c.md"),))

    def test_unexpected_type_is_skipped(self):
        parsed = _parse_manual_links([123, "a.md"], self_src_uri="current.md")
        self.assertEqual(parsed, (ManualLink(target="a.md"),))

    def test_self_reference_is_dropped(self):
        parsed = _parse_manual_links(["current.md", "a.md"], self_src_uri="current.md")
        self.assertEqual(parsed, (ManualLink(target="a.md"),))

    def test_duplicate_target_keeps_first_occurrence(self):
        parsed = _parse_manual_links(
            [{"First": "a.md"}, {"Second": "a.md"}], self_src_uri="current.md"
        )
        self.assertEqual(parsed, (ManualLink(target="a.md", label="First"),))


class TestUtilTagsIndex(unittest.TestCase):
    """Test `build_tags_index` and `write_tags_json` against a real,
    disk-backed MkDocs `Files` collection.
    """

    @classmethod
    def setUpClass(cls):
        cls.plg_utils = Util()
        cls.mkdocs_config = load_config(
            str(Path("tests/fixtures/mkdocs_minimal.yml").resolve())
        )
        cls.mkdocs_config.docs_dir = str(Path("tests/fixtures/docs").resolve())
        cls.files = get_files(cls.mkdocs_config)

    # -- TESTS ---------------------------------------------------------
    def test_build_tags_index_finds_tagged_pages(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertIn("page-a.md", index)
        self.assertEqual(set(index["page-a.md"].tags), {"api", "auth", "python"})

    def test_build_tags_index_skips_pages_without_tags(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertNotIn("page-no-tags.md", index)

    def test_build_tags_index_fallback_title_from_heading(self):
        """`page-b.md` has no `title` in its frontmatter."""
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertEqual(index["page-b.md"].fallback_title, "API OAuth2")

    def test_build_tags_index_respects_allowed_tags(self):
        index = self.plg_utils.build_tags_index(
            files=self.files, allowed_tags={"api", "auth"}
        )

        # 'python' is not allowed, but 'page-a.md' still qualifies (api, auth)
        self.assertEqual(set(index["page-a.md"].tags), {"api", "auth"})
        # 'page-c.md' only has 'gardening', filtered out entirely
        self.assertNotIn("page-c.md", index)

    def test_build_tags_index_respects_match_path_pattern(self):
        # only pages under sub/ are indexed
        pattern = re.compile(r"sub/.*")

        index = self.plg_utils.build_tags_index(
            files=self.files, match_path_pattern=pattern
        )

        self.assertIn("sub/page-nested.md", index)
        # tagged, but outside sub/ - excluded regardless of its own tags
        self.assertNotIn("page-a.md", index)

    def test_build_tags_index_none_pattern_matches_everything(self):
        with_none = self.plg_utils.build_tags_index(
            files=self.files, match_path_pattern=None
        )
        without_arg = self.plg_utils.build_tags_index(files=self.files)

        self.assertEqual(set(with_none), set(without_arg))

    def test_build_tags_index_respects_exclude_from_scoring(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertNotIn("page-excluded.md", index)
        # tagged and otherwise indexable - only excluded by its own
        # frontmatter, not by match_path or allowed_tags
        self.assertIn("page-a.md", index)

    def test_build_tags_index_ignores_malformed_related_content_frontmatter(self):
        """`related_content: true` (not a mapping) must not crash the
        indexing pass, and must not be treated as an opt-out either - only
        the documented `exclude_from_scoring: true` shape does that.
        """
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertIn("page-malformed-related-content.md", index)

    def test_build_tags_index_parses_manual_links_with_labels(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        self.assertEqual(
            index["page-with-manual-links.md"].manual_links,
            (
                ManualLink(target="page-c.md", label=None),
                ManualLink(target="page-d.md", label="Custom label"),
                ManualLink(target="https://example.org/external-resource/", label=None),
                ManualLink(
                    target="https://example.org/other-resource/",
                    label="Clean external label",
                ),
            ),
        )
        self.assertEqual(index["page-a.md"].manual_links, ())

    def test_build_tags_index_keeps_tagless_page_with_manual_links_only(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        entry = index["tagless-page-with-manual-links-only.md"]
        self.assertEqual(entry.tags, [])
        self.assertIn(ManualLink(target="page-a.md"), entry.manual_links)

    def test_build_tags_index_manual_links_excludes_self_reference(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        targets = [
            link.target
            for link in index["tagless-page-with-manual-links-only.md"].manual_links
        ]
        self.assertNotIn("tagless-page-with-manual-links-only.md", targets)

    def test_build_tags_index_manual_links_keeps_broken_reference(self):
        """A nonexistent page in `related_content.links` isn't validated
        against the Files collection at index time - only parsed here.
        It's `resolve_related_pages` that later looks it up and skips it
        gracefully - see the dedicated test in `test_build.py`.
        """
        index = self.plg_utils.build_tags_index(files=self.files)

        targets = [
            link.target
            for link in index["tagless-page-with-manual-links-only.md"].manual_links
        ]
        self.assertIn("this-page-does-not-exist.md", targets)

    def test_write_tags_json_shape(self):
        index = self.plg_utils.build_tags_index(files=self.files)

        with tempfile.TemporaryDirectory() as tmpdirname:
            self.plg_utils.write_tags_json(
                tags_index=index,
                files=self.files,
                site_dir=tmpdirname,
                filename="tags.json",
            )

            output_file = Path(tmpdirname) / "tags.json"
            self.assertTrue(output_file.exists())

            payload = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertIn("mappings", payload)

            urls = {entry["item"]["url"] for entry in payload["mappings"]}
            self.assertIn("page-a/", urls)


# ##############################################################################
# ##### Stand alone program ########
# ##################################
if __name__ == "__main__":
    unittest.main()

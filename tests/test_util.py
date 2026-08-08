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
import tempfile
import unittest
from pathlib import Path

# 3rd party
from mkdocs.config import load_config
from mkdocs.structure.files import get_files

# plugin target
from mkdocs_related_content.models import PageTagsEntry
from mkdocs_related_content.util import Util

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

        self.assertEqual(len(related["a.md"]), 2)

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

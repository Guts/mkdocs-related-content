#! python3  # noqa: E265

"""Usage from the repo root folder:

.. code-block:: python

    # for whole test module
    python -m unittest tests.test_build
"""

# #############################################################################
# ########## Libraries #############
# ##################################

# Standard library
import json
import logging
import re
import tempfile
import unittest
from pathlib import Path
from traceback import format_exception

# test suite
from tests.base import BaseTest

# -- Globals --
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _extract_related_section(html: str, css_class: str = "related-pages") -> str:
    """Isolate the plugin's own block from a full rendered page.

    The default `mkdocs` theme's navbar (and other page chrome) also uses
    `<div class="...">` elements, so a class-agnostic regex would grab the
    wrong one - this only matches the block using the given `css_class`
    (the plugin's `related_content_css_class`, `related-pages` by default).
    """
    pattern = re.compile(rf'<div class="{re.escape(css_class)}">.*?</div>', re.DOTALL)
    match = pattern.search(html)
    return match.group(0) if match else ""


# #############################################################################
# ########## Classes ###############
# ##################################


class TestBuildRelatedContent(BaseTest):
    """Test full `mkdocs build` runs with the Related Content plugin."""

    @classmethod
    def setUpClass(cls):
        """Executed when module is loaded before any test."""
        cls.config_files = sorted(Path("tests/fixtures/").glob("mkdocs_*.yml"))

    def _assert_build_succeeded(self, cli_result):
        if cli_result.exception is not None:
            e = cli_result.exception
            logger.debug("".join(format_exception(type(e), e, e.__traceback__)))
        self.assertIsNone(cli_result.exception)
        self.assertEqual(cli_result.exit_code, 0)

    # -- TESTS ---------------------------------------------------------
    def test_every_fixture_builds_without_error(self):
        """Every fixture mkdocs.yml must produce a successful, strict build."""
        for config_filepath in self.config_files:
            with self.subTest(config_file=config_filepath.name):
                with tempfile.TemporaryDirectory() as tmpdirname:
                    testproject_path = self.setup_clean_mkdocs_folder(
                        mkdocs_yml_filepath=config_filepath,
                        output_path=Path(tmpdirname),
                    )
                    cli_result = self.build_docs_setup(
                        mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                        output_path=Path(tmpdirname) / "site",
                        strict=True,
                    )
                    self._assert_build_succeeded(cli_result)

    def test_related_pages_appear_in_rendered_html(self):
        """`page-a` and `page-b` share the `api` tag: `page-a`'s HTML must
        link to `page-b`, and must NOT link to the unrelated `page-c`.
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path("tests/fixtures/mkdocs_minimal.yml"),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)

            page_a_html = (site_dir / "page-a" / "index.html").read_text(
                encoding="utf-8"
            )
            related_section = _extract_related_section(page_a_html)
            self.assertIn("page-b/", related_section)
            self.assertNotIn("page-c/", related_section)

    def test_max_related_and_min_score_are_applied(self):
        """`mkdocs_custom_options.yml` sets `max_related: 1` and a strict
        `min_score: 0.5`: `page-a` should end up related only to `page-d`
        (identical tags, score 1.0), not to `page-b` (score 0.25).
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path("tests/fixtures/mkdocs_custom_options.yml"),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)

            page_a_html = (site_dir / "page-a" / "index.html").read_text(
                encoding="utf-8"
            )
            related_section = _extract_related_section(
                page_a_html, css_class="voir-aussi"
            )
            self.assertIn("Voir aussi", related_section)  # custom section_title
            self.assertIn("page-d/", related_section)
            self.assertNotIn("page-b/", related_section)  # excluded by min_score

    def test_disabled_plugin_adds_nothing(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path("tests/fixtures/mkdocs_disabled.yml"),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)
            self.assertFalse((site_dir / "related-tags.json").exists())

    def test_fallback_json_export_without_material_tags(self):
        """No Material `tags` plugin declared: our own export must appear."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path(
                    "tests/fixtures/mkdocs_material_no_tags_plugin.yml"
                ),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)

            export_file = site_dir / "related-tags.json"
            self.assertTrue(export_file.exists())

            payload = json.loads(export_file.read_text(encoding="utf-8"))
            self.assertIn("mappings", payload)
            self.assertGreater(len(payload["mappings"]), 0)

    def test_no_duplicate_json_export_with_material_tags(self):
        """Material's own `tags` plugin is active: our fallback export must
        be skipped, but Material's own `tags.json` must still be produced.
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path(
                    "tests/fixtures/mkdocs_material_tags_enabled.yml"
                ),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)

            self.assertFalse((site_dir / "related-tags.json").exists())
            self.assertTrue((site_dir / "tags.json").exists())

    def test_export_tags_json_false_disables_fallback_export(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path("tests/fixtures/mkdocs_export_disabled.yml"),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)
            self.assertFalse((site_dir / "related-tags.json").exists())

    def test_page_without_tags_has_no_related_section(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            testproject_path = self.setup_clean_mkdocs_folder(
                mkdocs_yml_filepath=Path("tests/fixtures/mkdocs_minimal.yml"),
                output_path=Path(tmpdirname),
            )
            site_dir = Path(tmpdirname) / "site"
            cli_result = self.build_docs_setup(
                mkdocs_yml_filepath=testproject_path / "mkdocs.yml",
                output_path=site_dir,
                strict=True,
            )
            self._assert_build_succeeded(cli_result)

            html = (site_dir / "page-no-tags" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("related-pages", html)


# ##############################################################################
# ##### Stand alone program ########
# ##################################
if __name__ == "__main__":
    unittest.main()

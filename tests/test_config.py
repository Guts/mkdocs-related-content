#! python3  # noqa: E265

"""Usage from the repo root folder:

.. code-block:: python

    # for whole test module
    python -m unittest tests.test_config
"""

# #############################################################################
# ########## Libraries #############
# ##################################

# Standard library
import unittest
from pathlib import Path

# 3rd party
from mkdocs.config.base import Config

# plugin target
from mkdocs_related_content.config import RelatedContentPluginConfig
from mkdocs_related_content.constants import (
    DEFAULT_MAX_RELATED,
    DEFAULT_MIN_SCORE,
    DEFAULT_SECTION_TITLE,
    DEFAULT_TAGS_JSON_FILENAME,
)
from mkdocs_related_content.plugin import RelatedContentPlugin

# test suite
from tests.base import BaseTest

# #############################################################################
# ########## Classes ###############
# ##################################


class TestConfig(BaseTest):
    """Test plugin configuration."""

    @classmethod
    def setUpClass(cls):
        """Executed when module is loaded before any test."""
        cls.fixtures_dir = Path("tests/fixtures/")

    # -- TESTS ---------------------------------------------------------
    def test_plugin_config_defaults(self):
        """An un-configured plugin instance falls back to documented defaults."""
        expected = {
            "enabled": True,
            "section_title": DEFAULT_SECTION_TITLE,
            "max_related": DEFAULT_MAX_RELATED,
            "min_score": DEFAULT_MIN_SCORE,
            "use_material_tags": True,
            "export_tags_json": True,
            "tags_json_filename": DEFAULT_TAGS_JSON_FILENAME,
        }

        plugin = RelatedContentPlugin()
        errors, warnings = plugin.load_config({})

        self.assertIsInstance(plugin.config, RelatedContentPluginConfig)
        self.assertIsInstance(plugin.config, Config)
        self.assertEqual(plugin.config, expected)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_plugin_config_custom_options(self):
        """Custom options passed in mkdocs.yml override the defaults."""
        custom_cfg = {
            "section_title": "Voir aussi",
            "max_related": 1,
            "min_score": 0.5,
            "tags_json_filename": "custom-tags.json",
        }

        plugin = RelatedContentPlugin()
        errors, warnings = plugin.load_config(custom_cfg)

        self.assertEqual(plugin.config.section_title, "Voir aussi")
        self.assertEqual(plugin.config.max_related, 1)
        self.assertEqual(plugin.config.min_score, 0.5)
        self.assertEqual(plugin.config.tags_json_filename, "custom-tags.json")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_plugin_config_disabled(self):
        """`enabled: false` is honored and surfaced on the loaded config."""
        plugin = RelatedContentPlugin()
        errors, warnings = plugin.load_config({"enabled": False})

        self.assertFalse(plugin.config.enabled)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_plugin_config_through_mkdocs(self):
        """Every fixture mkdocs.yml loads without raising, through Mkdocs itself."""
        config_files = sorted(self.fixtures_dir.glob("mkdocs_*.yml"))
        self.assertGreater(len(config_files), 0, "No mkdocs.yml fixture found")

        for config_filepath in config_files:
            with self.subTest(config_file=config_filepath.name):
                plg_cfg = self.get_plugin_config_from_mkdocs(config_filepath)
                self.assertIsInstance(plg_cfg, Config)


# ##############################################################################
# ##### Stand alone program ########
# ##################################
if __name__ == "__main__":
    unittest.main()

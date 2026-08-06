#! python3  # noqa: E265

"""Usage from the repo root folder:

.. code-block:: python

    # for whole test module
    python -m unittest tests.test_integrations_material_tags
"""

# #############################################################################
# ########## Libraries #############
# ##################################

# Standard library
import unittest
from pathlib import Path

# 3rd party
from mkdocs.config import load_config

# package
from src.mkdocs_related_content.integrations.theme_material_base import (
    IntegrationMaterialThemeBase,
)
from src.mkdocs_related_content.integrations.theme_material_tags import (
    IntegrationMaterialTags,
)

# #############################################################################
# ########## Classes ###############
# ##################################


class TestIntegrationMaterialThemeBase(unittest.TestCase):
    """Test bare theme detection (Material vs anything else)."""

    def test_theme_material_detected(self):
        cfg = load_config(
            str(Path("tests/fixtures/mkdocs_material_no_tags_plugin.yml").resolve())
        )
        integration = IntegrationMaterialThemeBase(mkdocs_config=cfg)
        self.assertTrue(integration.IS_THEME_MATERIAL)

    def test_theme_not_material(self):
        cfg = load_config(str(Path("tests/fixtures/mkdocs_minimal.yml").resolve()))
        integration = IntegrationMaterialThemeBase(mkdocs_config=cfg)
        self.assertFalse(integration.IS_THEME_MATERIAL)


class TestIntegrationMaterialTags(unittest.TestCase):
    """Test detection of Material's built-in `tags` plugin."""

    def test_disabled_when_theme_is_not_material(self):
        cfg = load_config(str(Path("tests/fixtures/mkdocs_minimal.yml").resolve()))
        integration = IntegrationMaterialTags(mkdocs_config=cfg)

        self.assertFalse(integration.IS_THEME_MATERIAL)
        self.assertFalse(integration.IS_TAGS_PLUGIN_ENABLED)
        self.assertFalse(integration.IS_ENABLED)

    def test_disabled_when_material_but_no_tags_plugin(self):
        cfg = load_config(
            str(Path("tests/fixtures/mkdocs_material_no_tags_plugin.yml").resolve())
        )
        integration = IntegrationMaterialTags(mkdocs_config=cfg)

        self.assertTrue(integration.IS_THEME_MATERIAL)
        self.assertFalse(integration.IS_TAGS_PLUGIN_ENABLED)
        self.assertFalse(integration.IS_ENABLED)
        self.assertIsNone(integration.allowed_tags)

    def test_enabled_when_material_and_tags_plugin(self):
        cfg = load_config(
            str(Path("tests/fixtures/mkdocs_material_tags_enabled.yml").resolve())
        )
        integration = IntegrationMaterialTags(mkdocs_config=cfg)

        self.assertTrue(integration.IS_THEME_MATERIAL)
        self.assertTrue(integration.IS_TAGS_PLUGIN_ENABLED)
        self.assertTrue(integration.IS_ENABLED)

    def test_switch_force_disables_integration(self):
        """Even with Material + tags active, `use_material_tags: false` wins."""
        cfg = load_config(
            str(
                Path(
                    "tests/fixtures/mkdocs_material_tags_integration_disabled.yml"
                ).resolve()
            )
        )
        # this fixture instantiates the plugin itself with the option, so we
        # just re-create the integration the same way the plugin would
        integration = IntegrationMaterialTags(mkdocs_config=cfg, switch_force=False)

        self.assertTrue(integration.IS_TAGS_PLUGIN_ENABLED)
        self.assertFalse(integration.IS_ENABLED)

    def test_allowed_tags_reflects_material_config(self):
        cfg = load_config(
            str(Path("tests/fixtures/mkdocs_material_tags_allowed.yml").resolve())
        )
        integration = IntegrationMaterialTags(mkdocs_config=cfg)

        self.assertIsNotNone(integration.allowed_tags)
        self.assertIn("api", integration.allowed_tags)
        self.assertIn("gardening", integration.allowed_tags)


# ##############################################################################
# ##### Stand alone program ########
# ##################################
if __name__ == "__main__":
    unittest.main()

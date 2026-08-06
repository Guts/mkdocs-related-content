#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

from __future__ import annotations

# 3rd party
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import get_plugin_logger

# package
from src.mkdocs_related_content.constants import MKDOCS_LOGGER_NAME

# ############################################################################
# ########## Globals #############
# ################################

logger = get_plugin_logger(MKDOCS_LOGGER_NAME)

# ############################################################################
# ########## Classes ###############
# ##################################


class IntegrationMaterialThemeBase:
    """Shared base to detect whether the active theme is Material (or MaterialX).

    Same pattern as mkdocs-rss-plugin's own `IntegrationMaterialThemeBase`:
    https://github.com/Guts/mkdocs-rss-plugin
    """

    IS_THEME_MATERIAL: bool = False
    THEME_NAME: str = "mkdocs"

    def __init__(self, mkdocs_config: MkDocsConfig) -> None:
        """Integration instantiation.

        Args:
            mkdocs_config: Mkdocs website configuration object.
        """
        self.mkdocs_config = mkdocs_config
        self.IS_THEME_MATERIAL = self.is_mkdocs_theme_material()

    def is_mkdocs_theme_material(
        self, mkdocs_config: MkDocsConfig | None = None
    ) -> bool:
        """Check if the theme set in mkdocs.yml is material or not.

        Args:
            mkdocs_config: Mkdocs website configuration object.

        Returns:
            True if the theme's name is 'material' or 'materialx'.
        """
        if mkdocs_config is None and isinstance(self.mkdocs_config, MkDocsConfig):
            mkdocs_config = self.mkdocs_config

        if isinstance(mkdocs_config, MkDocsConfig):
            self.THEME_NAME = (
                mkdocs_config.theme.name if mkdocs_config.theme else "mkdocs"
            )
            self.IS_THEME_MATERIAL = mkdocs_config.theme.name in (
                "material",
                "materialx",
            )
            return self.IS_THEME_MATERIAL

        logger.warning(
            "Impossible de vérifier le thème : la configuration Mkdocs "
            "n'est pas disponible."
        )
        return False

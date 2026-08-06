#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

from __future__ import annotations

from typing import TYPE_CHECKING

# 3rd party
from mkdocs.plugins import get_plugin_logger

# package
from src.mkdocs_related_content.constants import MKDOCS_LOGGER_NAME
from src.mkdocs_related_content.integrations.theme_material_base import (
    IntegrationMaterialThemeBase,
)

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

# ############################################################################
# ########## Globals #############
# ################################

logger = get_plugin_logger(MKDOCS_LOGGER_NAME)

# ############################################################################
# ########## Classes ###############
# ##################################


class IntegrationMaterialTags(IntegrationMaterialThemeBase):
    """Detects Material's built-in `tags` plugin and exposes its *configuration*.

    Timing note - why we read config, not runtime state
    -----------------------------------------------------
    Material's tags plugin builds its own page/tag mapping incrementally,
    page by page, exactly like our own plugin would if it used the same
    hooks. That mapping - and the `tags.json` file it can export - is only
    complete once *every* page has been processed, i.e. at `on_post_build`.
    That's *after* every page's Jinja context (and therefore its rendered
    HTML) has already been produced.

    Consequence: we can't read `tags.json`, nor the tags plugin's internal
    mapping, to fill `related_pages` for a given page - that data doesn't
    exist yet at that point of the build (see plugin.py's `on_files` for how
    we work around this for our own index).

    What *is* safely available at any point of the build is the tags
    plugin's static **configuration** (e.g. `tags_allowed`). We use it so
    our own, independently-computed tag index stays consistent with what
    readers see on Material's tags index page.
    """

    IS_ENABLED: bool = False
    IS_TAGS_PLUGIN_ENABLED: bool = False

    def __init__(self, mkdocs_config: MkDocsConfig, switch_force: bool = True) -> None:
        """Integration instantiation.

        Args:
            mkdocs_config: Mkdocs website configuration object.
            switch_force: set to False to disable this integration even if
                Material's tags plugin is enabled. Defaults to True.
        """
        super().__init__(mkdocs_config=mkdocs_config)

        self.tags_plugin_cfg = None
        self.IS_TAGS_PLUGIN_ENABLED = self._detect_tags_plugin(mkdocs_config)
        self.IS_ENABLED = all([self.IS_THEME_MATERIAL, self.IS_TAGS_PLUGIN_ENABLED])

        if switch_force is False:
            self.IS_ENABLED = False
            logger.debug(
                "Intégration avec le plugin 'tags' de Material désactivée "
                "explicitement dans la configuration du plugin."
            )

    def _detect_tags_plugin(self, mkdocs_config: MkDocsConfig) -> bool:
        """Check if the tags plugin (Material or MaterialX) is declared and enabled.

        Args:
            mkdocs_config: Mkdocs website configuration object.

        Returns:
            True if theme is Material/MaterialX and its tags plugin is enabled.
        """
        if not self.is_mkdocs_theme_material(mkdocs_config=mkdocs_config):
            logger.debug(
                "Le thème installé n'est pas 'material'. Intégration 'tags' désactivée."
            )
            return False

        tags_cfg = mkdocs_config.plugins.get(f"{self.THEME_NAME}/tags")
        if tags_cfg is None:
            logger.debug(
                "Le plugin 'tags' de Material n'est pas déclaré dans la configuration."
            )
            return False

        if not getattr(tags_cfg.config, "enabled", True):
            logger.debug("Le plugin 'tags' de Material est déclaré mais désactivé.")
            return False

        self.tags_plugin_cfg = tags_cfg
        logger.debug("Plugin 'tags' de Material détecté et activé.")
        return True

    @property
    def allowed_tags(self) -> set[str] | None:
        """Allow-list configured on Material's tags plugin (`tags_allowed`), if any.

        `tags_allowed` isn't a plain list of strings: Material's `TagSet`
        config option validates it into a `set` of its own `Tag` objects
        (`material.plugins.tags.structure.tag.Tag`). That class overrides
        `__eq__` to only compare against other `Tag` instances - comparing
        one to a plain `str` raises `AssertionError` instead of returning
        `False`. `Tag.__str__` does return the plain tag name, so we
        normalize to strings here rather than leaking `Tag` objects into
        `util.build_tags_index`, which compares against plain frontmatter
        strings.

        Returns:
            None when no restriction is configured (every tag found in a
            page's frontmatter is considered valid), otherwise the set of
            allowed tag names, as plain strings.
        """
        if self.tags_plugin_cfg is None:
            return None

        allowed = getattr(self.tags_plugin_cfg.config, "tags_allowed", None)
        if not allowed:
            return None
        return {str(tag) for tag in allowed}

    def exports_own_json(self) -> bool:
        """Best-effort check of whether Material's tags plugin will export its
        own `tags.json` for this build.

        This inspects a couple of plausible, undocumented attribute names
        that have been used across Material versions and is deliberately
        conservative: if none match, it assumes export is active (Material's
        default), so our own fallback export in `plugin.on_post_build` stays
        opt-in rather than risking a silent duplicate file.

        Returns:
            True if Material's tags plugin appears to already export JSON.
        """
        if self.tags_plugin_cfg is None:
            return False

        for attr_name in ("tags_file_json", "json_export", "export"):
            value = getattr(self.tags_plugin_cfg.config, attr_name, None)
            if isinstance(value, bool):
                return value

        return True

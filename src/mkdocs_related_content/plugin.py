#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

from __future__ import annotations

# standard library
from typing import TYPE_CHECKING, Literal

# 3rd party
from mkdocs.plugins import BasePlugin, get_plugin_logger

# package modules
from mkdocs_related_content.config import RelatedContentPluginConfig
from mkdocs_related_content.constants import MKDOCS_LOGGER_NAME
from mkdocs_related_content.integrations.theme_material_tags import (
    IntegrationMaterialTags,
)
from mkdocs_related_content.util import Util

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.nav import Navigation
    from mkdocs.structure.pages import Page

    from mkdocs_related_content.models import PageTagsEntry

# ############################################################################
# ########## Globals #############
# ################################

logger = get_plugin_logger(MKDOCS_LOGGER_NAME)

# ############################################################################
# ########## Classes ###############
# ##################################


class RelatedContentPlugin(BasePlugin[RelatedContentPluginConfig]):
    """Main class for the Related Content Mkdocs plugin.

    Computes, for every tagged page, a list of related pages based on
    shared tags, and exposes it to the Jinja context so a theme override
    (e.g. `overrides/partials/related.html`) can render it.

    Build lifecycle used, and why
    ------------------------------
    `on_files`   - read every page's frontmatter straight from disk to
                   build a full-site tags index. This has to happen before
                   any page is rendered, and `Page.meta` isn't populated
                   yet at this point - see `util.Util.build_tags_index`.
    `on_nav`     - precompute every page's related pages in one pass, now
                   that the index (built from disk, not from the render
                   pipeline) is guaranteed complete.
    `on_page_context` - expose the precomputed result for the current page.
    `on_post_build`   - optionally write our own `tags.json`-shaped export,
                   only when Material's tags plugin isn't already doing so.
    """

    # allow to set the plugin multiple times in the same mkdocs config
    supports_multiple_instances = True

    def __init__(self, *args, **kwargs) -> None:
        """Instantiation."""
        super().__init__(*args, **kwargs)
        self.util = Util()

    def on_startup(
        self, *, command: Literal["build", "gh-deploy", "serve"], dirty: bool
    ) -> None:
        """Runs once at the very beginning of an `mkdocs` invocation.

        See: https://www.mkdocs.org/user-guide/plugins/#on_startup

        Args:
            command: the command Mkdocs was invoked with.
            dirty: whether `--dirty` flag was passed.
        """
        self.files: Files | None = None
        self.tags_index: dict[str, PageTagsEntry] = {}
        self.related_pages_by_uri: dict[str, list[tuple[float, str]]] = {}

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig:
        """First event called on build, right after config is loaded.

        See: https://www.mkdocs.org/user-guide/plugins/#on_config

        Args:
            config: global configuration object.

        Returns:
            The (possibly unmodified) global configuration object.
        """
        if not self.config.enabled:
            return config

        self.integration_material_tags = IntegrationMaterialTags(
            mkdocs_config=config,
            switch_force=self.config.use_material_tags,
        )

        if self.integration_material_tags.IS_ENABLED:
            logger.debug(
                "Thème Material + plugin 'tags' détectés : filtrage des "
                "tags aligné sur la configuration de ce plugin."
            )

        return config

    def on_files(self, files: Files, config: MkDocsConfig) -> Files:
        """Called after the global Files collection is populated.

        This is the step that makes the whole plugin possible: every File
        is known at this point, so we can read every page's YAML
        frontmatter straight from disk and know every tag on the site -
        something `Page.meta` can't give us yet, page by page.

        See: https://www.mkdocs.org/user-guide/plugins/#on_files

        Args:
            files: global files collection.
            config: global configuration object.

        Returns:
            The (unmodified) global files collection.
        """
        if not self.config.enabled:
            return files

        self.files = files

        allowed_tags = None
        if self.integration_material_tags.IS_ENABLED:
            allowed_tags = self.integration_material_tags.allowed_tags

        self.tags_index = self.util.build_tags_index(
            files=files, allowed_tags=allowed_tags
        )

        return files

    def on_nav(self, nav: Navigation, config: MkDocsConfig, files: Files) -> Navigation:
        """Called after the site navigation is created.

        Precomputes every page's related pages in a single pass. Safe to do
        here - rather than lazily on the first `on_page_context` call -
        because `self.tags_index` no longer depends on the page render
        order: it was built from raw frontmatter in `on_files`.

        See: https://www.mkdocs.org/user-guide/plugins/#on_nav

        Args:
            nav: global navigation object.
            config: global configuration object.
            files: global files collection.

        Returns:
            The (unmodified) global navigation object.
        """
        if not self.config.enabled or not self.tags_index:
            return nav

        self.related_pages_by_uri = self.util.compute_related_pages(
            tags_index=self.tags_index,
            min_score=self.config.min_score,
            max_related=self.config.max_related,
        )

        return nav

    def on_page_context(
        self, context: dict, page: Page, config: MkDocsConfig, nav: Navigation
    ) -> dict:
        """Called after the page context is created, before rendering.

        Exposes `related_pages` and the configured section title to Jinja.

        See: https://www.mkdocs.org/user-guide/plugins/#on_page_context

        Args:
            context: template context for the current page.
            page: `mkdocs.structure.pages.Page` instance.
            config: global configuration object.
            nav: global navigation object.

        Returns:
            The enriched template context.
        """
        if not self.config.enabled:
            return context

        entry = self.tags_index.get(page.file.src_uri)
        if entry is None:
            context["related_pages"] = []
            return context

        related = self.related_pages_by_uri.get(page.file.src_uri, [])
        context["related_pages"] = self.util.resolve_related_pages(
            related=related,
            tags_index=self.tags_index,
            current_tags=set(entry.tags),
            files=self.files,
        )
        context["related_content_section_title"] = self.config.section_title

        return context

    def on_post_build(self, config: MkDocsConfig) -> None:
        """Called once the whole site has been built.

        Writes our own `tags.json`-shaped export, but only as a fallback:
        if Material's tags plugin is active and already exports its own
        JSON, we skip this to avoid a redundant, possibly inconsistent file.

        See: https://www.mkdocs.org/user-guide/plugins/#on_post_build

        Args:
            config: global configuration object.
        """
        if not self.config.enabled or not self.config.export_tags_json:
            return

        if (
            self.integration_material_tags.IS_ENABLED
            and self.integration_material_tags.exports_own_json()
        ):
            logger.debug(
                "Le plugin 'tags' de Material exporte déjà son propre "
                "tags.json : export interne ignoré pour éviter un doublon."
            )
            return

        self.util.write_tags_json(
            tags_index=self.tags_index,
            files=self.files,
            site_dir=config.site_dir,
            filename=self.config.tags_json_filename,
        )

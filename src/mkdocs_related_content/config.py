#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

# 3rd party
from mkdocs.config import config_options
from mkdocs.config.base import Config

# package
from mkdocs_related_content.constants import (
    DEFAULT_CSS_CLASS,
    DEFAULT_MAX_RELATED,
    DEFAULT_MIN_SCORE,
    DEFAULT_SECTION_TITLE,
    DEFAULT_TAGS_JSON_FILENAME,
    DEFAULT_WEIGHT_BY_TAG_RARITY,
)

# ############################################################################
# ########## Classes ###############
# ##################################


class RelatedContentPluginConfig(Config):
    """Configuration for the Related Content plugin for Mkdocs."""

    enabled = config_options.Type(bool, default=True)

    # display
    section_title = config_options.Type(str, default=DEFAULT_SECTION_TITLE)
    css_class = config_options.Type(str, default=DEFAULT_CSS_CLASS)

    # scoring
    max_related = config_options.Type(int, default=DEFAULT_MAX_RELATED)
    min_score = config_options.Type(float, default=DEFAULT_MIN_SCORE)
    weight_by_tag_rarity = config_options.Type(
        bool, default=DEFAULT_WEIGHT_BY_TAG_RARITY
    )

    # Material integration - see integrations/theme_material_tags.py
    use_material_tags = config_options.Type(bool, default=True)

    # fallback tags.json export, only written when Material's tags plugin
    # isn't already producing one (see plugin.on_post_build)
    export_tags_json = config_options.Type(bool, default=True)
    tags_json_filename = config_options.Type(str, default=DEFAULT_TAGS_JSON_FILENAME)

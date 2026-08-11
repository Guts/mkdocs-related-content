#! python3  # noqa: E265

# ############################################################################
# ########## Libraries #############
# ##################################

# standard library
from pathlib import Path

# ############################################################################
# ########## Globals #############
# ################################

MKDOCS_LOGGER_NAME: str = "[related-content]"

# default plugin option values
DEFAULT_CSS_CLASS: str = "related-pages"
DEFAULT_MATCH_PATH: str = ".*"
DEFAULT_MAX_RELATED: int = 5
DEFAULT_MIN_SCORE: float = 0.1
DEFAULT_SECTION_TITLE: str = "Related contents"
DEFAULT_TAGS_JSON_FILENAME: str = "related-tags.json"
DEFAULT_WEIGHT_BY_TAG_RARITY: bool = False

# heuristic used only to derive a *temporary* title from a page's own
# Markdown body when no `title` is set in its frontmatter - see
# `util.Util._guess_title` for how (and why) it's used.
FIRST_HEADING_PATTERN: str = r"^#\s+(.+?)\s*$"

# unused for now, kept for parity with plugins (like mkdocs-rss-plugin) that
# cache heavier computations across builds
DEFAULT_CACHE_FOLDER: Path = Path(".cache/plugins/related_content")

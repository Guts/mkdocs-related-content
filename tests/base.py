#! python3  # noqa: E265

"""Base class for unit tests. Pattern reused from mkdocs-rss-plugin's own
`tests/base.py`: https://github.com/Guts/mkdocs-rss-plugin
"""

# #############################################################################
# ########## Libraries #############
# ##################################

# Standard library
import logging
import shutil
import unittest
from pathlib import Path

# 3rd party
from click.testing import CliRunner
from mkdocs.__main__ import build_command
from mkdocs.config import load_config
from mkdocs.config.base import Config

# package
from src.mkdocs_related_content.plugin import RelatedContentPlugin

# #############################################################################
# ########## Classes ###############
# ##################################


class BaseTest(unittest.TestCase):
    """Base test class to be inherited by Related Content plugin tests."""

    def get_plugin_config_from_mkdocs(self, mkdocs_yml_filepath: Path) -> Config:
        """Load a mkdocs.yml and return the Related Content plugin's configuration.

        Args:
            mkdocs_yml_filepath: path to a MkDocs configuration file.

        Returns:
            The plugin's own configuration, loaded through `on_config`.
        """
        cfg_mkdocs = load_config(str(mkdocs_yml_filepath.resolve()))

        plugin_instances = [
            plg
            for plg in cfg_mkdocs.plugins.items()
            if isinstance(plg[1], RelatedContentPlugin)
        ]
        if not len(plugin_instances):
            logging.warning(
                "Le plugin related-content n'est pas activé dans le fichier "
                f"MkDocs : {mkdocs_yml_filepath}"
            )
            return cfg_mkdocs

        plugin = plugin_instances[0][1]
        self.assertIsInstance(plugin, RelatedContentPlugin)
        plugin.on_config(cfg_mkdocs)

        return plugin.config

    def build_docs_setup(
        self,
        mkdocs_yml_filepath: Path,
        output_path: Path,
        strict: bool = True,
    ):
        """Run the `mkdocs build` command through Click's test runner.

        Args:
            mkdocs_yml_filepath: filepath to the MkDocs configuration file
                passed as `--config-file`.
            output_path: folder path where to store the built website,
                passed as `--site-dir`.
            strict: whether to pass `--strict` to the build command.

        Returns:
            The `click.testing.Result` of the invoked command.
        """
        cmd_args = [
            "--clean",
            "--config-file",
            f"{mkdocs_yml_filepath}",
            "--site-dir",
            f"{output_path}",
            "--verbose",
        ]
        if strict:
            cmd_args.append("--strict")

        runner = CliRunner()
        return runner.invoke(build_command, cmd_args)

    def setup_clean_mkdocs_folder(
        self, mkdocs_yml_filepath: Path, output_path: Path
    ) -> Path:
        """Set up a clean, throwaway MkDocs project:

            outputpath/testproject
            ├── docs/
            └── mkdocs.yml

        Args:
            mkdocs_yml_filepath: path of the mkdocs.yml fixture to use.
            output_path: path of the folder in which to create the project.

        Returns:
            Path to the throwaway project.
        """
        testproject_path = Path(output_path) / "testproject"

        if testproject_path.exists():
            shutil.rmtree(testproject_path)

        shutil.copytree("tests/fixtures/docs", testproject_path / "docs")
        shutil.copyfile(mkdocs_yml_filepath, testproject_path / "mkdocs.yml")

        # theme override used to render `related_pages` in the built HTML -
        # only copied when a fixture's `custom_dir` actually points to it
        overrides_src = Path("tests/fixtures/overrides")
        if overrides_src.exists():
            shutil.copytree(overrides_src, testproject_path / "overrides")

        return testproject_path

import importlib


def test_pipeline_package_imports():
    assert importlib.import_module("pipeline")


def test_fixtures_dir_exists(fixtures_dir):
    assert fixtures_dir.is_dir()


def test_core_dependencies_import():
    for name in ("bs4", "lxml", "pypdf", "pydantic"):
        importlib.import_module(name)

"""Cleanup guards for translation coverage and importable conversation modules."""

import ast
import importlib
from pathlib import Path

from app.handlers import build_router
from app.menus import MENUS
from app.services.test_creation_service import FIELDS
from app.texts import _LOCALES, headers, t

ROOT = Path(__file__).resolve().parents[1] / "app"


def test_conversation_modules_import_without_deferred_imports():
    for name in (
        "menu_service",
        "nav_service",
        "reporting_service",
        "settings_ui_service",
        "broadcast_ui_service",
        "application_service",
    ):
        importlib.import_module("app.services." + name)
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        top_level = {id(node) for node in tree.body}
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in top_level
            for node in ast.walk(tree)
        ), path
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            for node in ast.walk(tree)
        ), path


def test_uzbek_catalog_covers_dynamic_menus_prompts_and_reports():
    assert set(_LOCALES) == {"uz"}
    for entry in MENUS.values():
        assert t(entry.title)
    for field in FIELDS:
        assert t("prompt_" + field, code="1234", channels="")
    for kind in ("results", "access", "users", "refs"):
        assert headers("headers_" + kind)
    assert (
        not {"broadcast_prompt", "left_btn", "settings_prompt", "channel_prompt", "pending_action"}
        & _LOCALES["uz"].keys()
    )


def test_router_uses_shared_message_adapter_and_subscription_only():
    router = build_router()
    assert len({entry.callback for entry in router.message.handlers}) == 1
    assert len(router.callback_query.handlers) == 1
    assert router.callback_query.handlers[0].callback.__module__ == "app.handlers.user.subscription"

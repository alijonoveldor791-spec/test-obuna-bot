"""Declarative Uzbek navigation with role and lifecycle permissions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Menu:
    """A button, its parent, permission and dispatch action."""

    title: str
    parent: str | None
    buttons: tuple[str, ...] = ()
    permission: str | None = None
    action: str = "menu"
    setting: str | None = None
    visible: bool = True


MENUS: dict[str, Menu] = {
    "test_list": Menu(
        "test_list", "tests", permission="tests_view", action="test_flow", visible=False
    ),
    "test_card": Menu(
        "test_card", "test_list", permission="tests_view", action="test_flow", visible=False
    ),
    "edit_post": Menu(
        "edit_post", "test_card", permission="tests", action="test_flow", visible=False
    ),
    "delete": Menu("delete", "test_card", permission="tests", action="test_flow", visible=False),
    "test_stats": Menu(
        "test_stats", "test_card", permission="stats", action="test_flow", visible=False
    ),
    "excel_results": Menu(
        "excel_results", "test_card", permission="exports", action="test_flow", visible=False
    ),
    "key": Menu("key", "test_card", permission="tests", action="test_flow", visible=False),
    "close": Menu("close", "test_card", permission="tests", action="test_flow", visible=False),
    "announce": Menu(
        "announce", "test_card", permission="tests", action="test_flow", visible=False
    ),
    "user": Menu("nav_prompt", None, ("latest", "submit_btn", "results", "referral", "help_btn")),
    "admin": Menu(
        "admin_menu",
        None,
        ("new_test", "tests", "stats", "exports", "broadcast", "users", "settings", "user_mode"),
        "panel",
    ),
    "new_test": Menu("new_test", "admin", permission="tests", action="test_flow"),
    "tests": Menu("tests", "admin", ("active", "closed"), "tests_view"),
    "stats": Menu("stats", "admin", ("general", "ref_top"), "stats"),
    "exports": Menu("exports", "admin", ("export_users", "export_refs"), "exports"),
    "broadcast": Menu(
        "broadcast", "admin", ("all_btn", "participants_btn", "pending_btn"), "broadcast"
    ),
    "users": Menu("users", "admin", ("ban_btn", "unban_btn", "banned_btn"), "users"),
    "settings": Menu(
        "settings",
        "admin",
        ("channels", "admins", "protect_btn", "reminders_btn", "key_btn"),
        "settings",
    ),
    "channels": Menu(
        "channels", "settings", ("add_channel", "list_channels", "del_channel"), "channels"
    ),
    "admins": Menu("admins", "settings", ("add_admin", "list_admins", "del_admin"), "admins"),
    "user_mode": Menu("user_mode", "admin", permission="panel", action="user"),
    "latest": Menu("latest", "user", action="latest"),
    "submit_btn": Menu("submit_btn", "user", action="answers"),
    "results": Menu("results", "user", action="results"),
    "referral": Menu("referral", "user", action="referral"),
    "help_btn": Menu("help_btn", "user", action="help"),
    "active": Menu("active", "tests", permission="tests_view", action="test_flow"),
    "closed": Menu("closed", "tests", permission="tests_view", action="test_flow"),
    "general": Menu("general", "stats", permission="stats", action="report_flow"),
    "ref_top": Menu("ref_top", "stats", permission="stats", action="report_flow"),
    "export_users": Menu("export_users", "exports", permission="exports", action="report_flow"),
    "export_refs": Menu("export_refs", "exports", permission="exports", action="report_flow"),
    "ban_btn": Menu("ban_btn", "users", permission="users", action="report_flow"),
    "unban_btn": Menu("unban_btn", "users", permission="users", action="report_flow"),
    "banned_btn": Menu("banned_btn", "users", permission="users", action="report_flow"),
    "all_btn": Menu("all_btn", "broadcast", permission="broadcast", action="broadcast_flow"),
    "participants_btn": Menu(
        "participants_btn", "broadcast", permission="broadcast", action="broadcast_flow"
    ),
    "pending_btn": Menu(
        "pending_btn", "broadcast", permission="broadcast", action="broadcast_flow"
    ),
    "add_channel": Menu("add_channel", "channels", permission="channels", action="settings_flow"),
    "list_channels": Menu(
        "list_channels", "channels", permission="channels", action="settings_flow"
    ),
    "del_channel": Menu("del_channel", "channels", permission="channels", action="settings_flow"),
    "add_admin": Menu("add_admin", "admins", permission="admins", action="settings_flow"),
    "list_admins": Menu("list_admins", "admins", permission="admins", action="settings_flow"),
    "del_admin": Menu("del_admin", "admins", permission="admins", action="settings_flow"),
    "protect_btn": Menu(
        "protect_btn",
        "settings",
        permission="settings",
        action="settings_flow",
        setting="protect_content",
    ),
    "reminders_btn": Menu(
        "reminders_btn",
        "settings",
        permission="settings",
        action="settings_flow",
        setting="reminders",
    ),
    "key_btn": Menu(
        "key_btn",
        "settings",
        permission="settings",
        action="settings_flow",
        setting="show_key_after_close",
    ),
}


def permissions_for(menu_id: str) -> set[str]:
    """Inherit parent permissions so a new row cannot bypass its section."""
    permissions: set[str] = set()
    seen: set[str] = set()
    while menu_id:
        if menu_id in seen:
            raise ValueError("Menu parent cycle")
        seen.add(menu_id)
        menu = MENUS[menu_id]
        if menu.permission:
            permissions.add(menu.permission)
        menu_id = menu.parent
    return permissions


def children(menu_id: str) -> tuple[str, ...]:
    """Preserve declared order and automatically include newly added child rows."""
    ordered = MENUS[menu_id].buttons
    return ordered + tuple(
        key
        for key, entry in MENUS.items()
        if entry.parent == menu_id and key not in ordered and entry.visible
    )

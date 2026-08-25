"""OrangeHRM — end-to-end user-management lifecycle.

Manual scenario (low complexity):
    Login → Admin → capture employee → Add user → verify →
    Edit user → verify → Delete user → verify absence.
"""
from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page

from pages.admin_user_page import AdminUserPage
from pages.login_page import LoginPage
from utils.config import Settings
from utils.logger import SESSION_ID, get_logger
from utils.test_data import build_new_user, unique_username


log = get_logger(__name__)


@allure.epic("OrangeHRM")
@allure.feature("Admin — User Management")
@allure.story("Create → Edit → Delete lifecycle")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
@pytest.mark.admin

def test_create_update_delete_user(logged_in_page: Page) -> None:
    allure.dynamic.label("session_id", SESSION_ID)
    log.info("Test: create -> verify -> edit -> verify -> delete -> verify")
    admin = AdminUserPage(logged_in_page)

    with allure.step("Open Admin > User Management"):
        admin.open()

    with allure.step("Capture an existing employee name"):
        employee_name = admin.pick_any_existing_employee_name()
        assert employee_name, "Failed to capture an existing employee name"

    with allure.step("Create a new user"):
        new_user = build_new_user(employee_name)
        admin.create_user(new_user)

    with allure.step("Verify the new user is visible"):
        admin.search_by_username(new_user.username)
        admin.assert_username_visible(new_user.username)

    updated_username = unique_username(prefix="qa_user_upd")
    updates = new_user.with_updates(username=updated_username, status="Disabled")
    with allure.step("Edit the user (rename + disable)"):
        admin.edit_user(current_username=new_user.username, updates=updates)

    with allure.step("Verify the edit — new username present, old absent"):
        admin.search_by_username(updated_username)
        admin.assert_username_visible(updated_username)
        admin.search_by_username(new_user.username)
        admin.assert_username_absent(new_user.username)

    with allure.step("Delete the (renamed) user"):
        admin.search_by_username(updated_username)
        admin.delete_user(updated_username)

    with allure.step("Verify the user is gone"):
        admin.search_by_username(updated_username)
        admin.assert_username_absent(updated_username)

    log.info("Test finished: full CRUD lifecycle verified")


# ---------------------------------------------------------------------------
# Negative scenarios
# ---------------------------------------------------------------------------


@allure.epic("OrangeHRM")
@allure.feature("Authentication")
@allure.story("Login — invalid credentials")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.negative
def test_login_invalid_credentials(page: Page, settings: Settings) -> None:
    allure.dynamic.label("session_id", SESSION_ID)
    log.info("Negative: login with invalid credentials is rejected")
    login = LoginPage(page)
    login.open(settings.base_url)

    with allure.step("Wrong username"):
        login.attempt_login("definitely_not_a_user", settings.password)
        login.expect_invalid_credentials()

    with allure.step("Wrong password"):
        login.attempt_login(settings.username, "wrong_password_xyz")
        login.expect_invalid_credentials()


@allure.epic("OrangeHRM")
@allure.feature("Authentication")
@allure.story("Login — empty required fields")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.negative
def test_login_empty_fields_show_required(page: Page, settings: Settings) -> None:
    allure.dynamic.label("session_id", SESSION_ID)
    log.info("Negative: empty login submission surfaces Required errors")
    login = LoginPage(page)
    login.open(settings.base_url)
    login.submit_empty_login()
    login.expect_login_required_errors()


@allure.epic("OrangeHRM")
@allure.feature("Admin — User Management")
@allure.story("Create user — duplicate username rejected")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.negative
@pytest.mark.admin
def test_create_user_duplicate_username_rejected(logged_in_page: Page) -> None:
    allure.dynamic.label("session_id", SESSION_ID)
    log.info("Negative: duplicate username on Add User is rejected")
    admin = AdminUserPage(logged_in_page)
    admin.open()

    with allure.step("Seed a user we can then duplicate"):
        employee_name = admin.pick_any_existing_employee_name()
        seeded = build_new_user(employee_name)
        admin.create_user(seeded)

    with allure.step("Attempt to create another user with the same username"):
        duplicate = build_new_user(employee_name).with_updates(username=seeded.username)
        admin.attempt_create_user(duplicate)
        admin.expect_username_already_exists()

    with allure.step("Cleanup — delete the seeded user"):
        admin.return_to_list()
        admin.search_by_username(seeded.username)
        admin.delete_user(seeded.username)
        admin.search_by_username(seeded.username)
        admin.assert_username_absent(seeded.username)


@allure.epic("OrangeHRM")
@allure.feature("Admin — User Management")
@allure.story("Create user — required-field validation")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.negative
@pytest.mark.admin
def test_create_user_required_fields(logged_in_page: Page) -> None:
    allure.dynamic.label("session_id", SESSION_ID)
    log.info("Negative: empty Add User form surfaces Required errors")
    admin = AdminUserPage(logged_in_page)
    admin.open()
    admin.submit_empty_add_form()
    # Status defaults to 'Enabled'; Confirm Password shows 'Passwords do not
    # match' (not 'Required') when both password inputs are empty.
    admin.expect_add_form_field_errors({
        "User Role": "Required",
        "Employee Name": "Required",
        "Username": "Required",
        "Password": "Required",
        "Confirm Password": "Passwords do not match",
    })
    admin.return_to_list()

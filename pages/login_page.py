"""OrangeHRM login screen."""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator, expect

from .base_page import BasePage


class LoginPage(BasePage):
    PATH = "/web/index.php/auth/login"

    @allure.step("Open login page")
    def open(self, base_url: str) -> None:
        url = f"{base_url.rstrip('/')}{self.PATH}"
        self.log.info("Opening login page: %s", url)
        self.page.goto(url)
        expect(self.page.get_by_role("button", name="Login")).to_be_visible()

    @allure.step("Log in as {username}")
    def login(self, username: str, password: str) -> None:
        self.log.info("Logging in as %s", username)
        self.page.get_by_placeholder("Username").fill(username)
        self.page.get_by_placeholder("Password").fill(password)
        self.page.get_by_role("button", name="Login").click()
        try:
            expect(self.page).to_have_url(re.compile(r"/dashboard"), timeout=15_000)
            expect(
                self.page.get_by_role("heading", name="Dashboard")
            ).to_be_visible()
        except Exception:
            self.log.error("Login failed for user %s", username)
            raise
        self.log.info("Login successful")

    # ---------- negative-flow helpers ----------

    @allure.step("Attempt login as {username} (expecting failure)")
    def attempt_login(self, username: str, password: str) -> None:
        """Fill credentials and submit — do NOT assert dashboard.

        Callers expecting rejection follow up with `expect_invalid_credentials`.
        """
        self.log.info("Attempting login as %s (expecting failure)", username)
        self.page.get_by_placeholder("Username").fill(username)
        self.page.get_by_placeholder("Password").fill(password)
        self.page.get_by_role("button", name="Login").click()

    @allure.step("Submit login form with empty credentials")
    def submit_empty_login(self) -> None:
        self.log.info("Submitting empty login form")
        # Clear both fields defensively — the page may retain a prior value.
        self.page.get_by_placeholder("Username").fill("")
        self.page.get_by_placeholder("Password").fill("")
        self.page.get_by_role("button", name="Login").click()

    @allure.step("Assert 'Invalid credentials' alert is visible")
    def expect_invalid_credentials(self) -> None:
        self.log.info("Asserting invalid-credentials alert")
        alert = self.page.locator(
            "div.oxd-alert-content--error", has_text=re.compile(r"Invalid credentials")
        )
        expect(alert).to_be_visible()

    @allure.step("Assert 'Required' errors on Username and Password")
    def expect_login_required_errors(self) -> None:
        self.log.info("Asserting login required-field errors")
        expect(self._field_error("Username")).to_have_text("Required")
        expect(self._field_error("Password")).to_have_text("Required")

    def _field_error(self, placeholder: str) -> Locator:
        """The 'Required' / error span inside the field with the given placeholder."""
        return (
            self.page.locator(".oxd-input-group")
            .filter(has=self.page.get_by_placeholder(placeholder))
            .locator(".oxd-input-field-error-message")
        )

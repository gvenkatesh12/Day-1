"""Admin → User Management page (list + Add / Edit forms + delete dialog)."""
from __future__ import annotations

import re

import allure
from playwright.sync_api import Locator, expect

from utils.test_data import UserRecord

from .base_page import BasePage


class AdminUserPage(BasePage):
    LIST_PATH = "/web/index.php/admin/viewSystemUsers"

    # ---------- navigation ----------

    @allure.step("Navigate to Admin > User Management")
    def open(self) -> None:
        self.log.info("Navigating to Admin > User Management")
        self.page.get_by_role("link", name="Admin").click()
        expect(self.page).to_have_url(re.compile(r"/admin/viewSystemUsers"))
        expect(
            self.page.get_by_role("heading", name="User Management")
        ).to_be_visible()
        # Wait for the initial (unfiltered) list to render so the record-count
        # element is stable before the test starts interacting with it.
        expect(self._record_count_label()).to_be_visible()
        self.log.info("User Management list is ready")

    # ---------- reading state ----------

    @allure.step("Capture an existing employee name from the autocomplete")
    def pick_any_existing_employee_name(self) -> str:
        """Return an employee name from the autocomplete on the Add form.

        The manual step is "capture the name of an existing employee to
        associate with the new user"; the autocomplete is the natural source
        because it is populated from the employee directory.
        """
        self.log.info("Capturing an existing employee name from the autocomplete")
        self.click_add()
        input_box = self._field_by_label("Employee Name").locator("input")
        input_box.click()
        # press_sequentially fires keydown/input events the autocomplete listens to;
        # fill() sets the value directly and can leave the dropdown unrefreshed.
        input_box.press_sequentially("a", delay=50)
        option = self.page.locator(
            "div[role='listbox'] div[role='option']"
        ).first
        expect(option).not_to_have_text("Searching....", timeout=15_000)
        name = option.inner_text().strip()
        self.log.info("Captured employee name: %s", name)
        # Return to the list. Cancel can be blocked when the form is dirty with
        # an invalid autocomplete value, so re-navigate via the Admin sidebar link.
        self.page.get_by_role("link", name="Admin").click()
        expect(
            self.page.get_by_role("heading", name="User Management")
        ).to_be_visible()
        return name

    # ---------- create ----------

    def click_add(self) -> None:
        self.log.debug("Clicking + Add on the User Management list")
        self.page.get_by_role("button").filter(
            has_text=re.compile(r"^\s*\+?\s*Add\s*$")
        ).first.click()
        expect(
            self.page.get_by_role("heading", name="Add User")
        ).to_be_visible()

    @allure.step("Create user")
    def create_user(self, user: UserRecord) -> None:
        allure.attach(
            f"username={user.username}\nrole={user.user_role}\nstatus={user.status}",
            name="user details",
            attachment_type=allure.attachment_type.TEXT,
        )
        self.log.info("Creating user: %s (role=%s, status=%s)",
                      user.username, user.user_role, user.status)
        try:
            self.click_add()
            self.select_dropdown_option("User Role", user.user_role)
            self.pick_autocomplete_option("Employee Name", user.employee_name[:3])
            self.select_dropdown_option("Status", user.status)
            self.fill_text_field("Username", user.username)
            self._fill_password_fields(user.password, user.password)
            self._click_save()
            self._expect_toast("Successfully Saved")
            expect(
                self.page.get_by_role("heading", name="User Management")
            ).to_be_visible()
        except Exception:
            self.log.error("User creation failed for %s", user.username)
            raise
        self.log.info("User created successfully: %s", user.username)

    # ---------- search / verify ----------

    @allure.step("Search users by username: {username}")
    def search_by_username(self, username: str) -> None:
        self.log.info("Searching for username: %s", username)
        input_box = self._field_by_label("Username").locator("input")
        # Clear any stale value from a prior search before typing the new one.
        input_box.fill("")
        input_box.fill(username)
        self.page.get_by_role("button", name=re.compile(r"^\s*Search\s*$")).click()
        # After a filtered search the results panel re-renders; wait for the
        # network round-trip so the count text reflects the new filter, not
        # the pre-search value.
        self.page.wait_for_load_state("networkidle", timeout=15_000)
        expect(self._record_count_label()).to_be_visible()

    @allure.step("Assert username is visible: {username}")
    def assert_username_visible(self, username: str) -> None:
        self.log.info("Asserting username is visible: %s", username)
        expect(self._row_for(username)).to_be_visible()
        expect(self._record_count_label()).to_contain_text("(1) Record Found")

    @allure.step("Assert username is absent: {username}")
    def assert_username_absent(self, username: str) -> None:
        self.log.info("Asserting username is absent: %s", username)
        expect(self._record_count_label()).to_contain_text("No Records Found")
        expect(self._row_for(username)).to_have_count(0)

    # ---------- edit ----------

    @allure.step("Edit user: {current_username}")
    def edit_user(self, current_username: str, updates: UserRecord) -> None:
        self.log.info("Editing user %s (new username=%s, status=%s)",
                      current_username, updates.username, updates.status)
        try:
            row = self._row_for(current_username)
            row.locator("button").filter(has=self.page.locator("i.bi-pencil-fill")).click()
            expect(
                self.page.get_by_role("heading", name="Edit User")
            ).to_be_visible()

            if updates.user_role:
                self.select_dropdown_option("User Role", updates.user_role)
            if updates.status:
                self.select_dropdown_option("Status", updates.status)
            if updates.username and updates.username != current_username:
                self.fill_text_field("Username", updates.username)

            self._click_save()
            self._expect_toast("Successfully Updated")
            expect(
                self.page.get_by_role("heading", name="User Management")
            ).to_be_visible()
        except Exception:
            self.log.error("User edit failed for %s", current_username)
            raise
        self.log.info("User updated successfully: %s -> %s",
                      current_username, updates.username or current_username)

    # ---------- delete ----------

    @allure.step("Delete user: {username}")
    def delete_user(self, username: str) -> None:
        self.log.info("Deleting user: %s", username)
        try:
            row = self._row_for(username)
            row.locator("button").filter(
                has=self.page.locator("[class*='bi-trash']")
            ).click()
            # OrangeHRM keeps a hidden dialog overlay in the DOM alongside the real
            # one; the visible one is the currently-shown confirmation.
            dialog = self.page.locator("div[role='dialog']:visible")
            expect(dialog).to_be_visible()
            dialog.get_by_role("button", name=re.compile(r"Yes,\s*Delete")).click()
            self._expect_toast("Successfully Deleted")
        except Exception:
            self.log.error("User deletion failed for %s", username)
            raise
        self.log.info("User deleted successfully: %s", username)

    # ---------- internals ----------

    def _record_count_label(self) -> Locator:
        # Matches "(N) Record(s) Found" or "No Records Found".
        return self.page.locator(
            "span.oxd-text.oxd-text--span",
            has_text=re.compile(r"Record"),
        )

    def _row_for(self, username: str) -> Locator:
        """A results-table row whose Username cell equals `username` exactly."""
        return self.page.locator("div.oxd-table-card").filter(
            has=self.page.locator(
                "div.oxd-table-cell >> div",
                has_text=re.compile(rf"^\s*{re.escape(username)}\s*$"),
            )
        )

    def _fill_password_fields(self, password: str, confirm: str) -> None:
        password_group = self._field_by_label("Password")
        password_group.locator("input").fill(password)
        confirm_group = self._field_by_label("Confirm Password")
        confirm_group.locator("input").fill(confirm)

    def _click_save(self) -> None:
        self.page.get_by_role("button", name=re.compile(r"^\s*Save\s*$")).click()

    def _expect_toast(self, message: str) -> None:
        # Multiple toasts can be on-screen at once (e.g., a lingering info toast
        # from a prior action); filter to the one containing the expected message.
        toast = self.page.locator("div.oxd-toast").filter(has_text=message)
        expect(toast).to_be_visible()

    # ---------- negative-flow helpers ----------

    @allure.step("Attempt to create user (expecting rejection)")
    def attempt_create_user(self, user: UserRecord) -> None:
        """Fill the Add User form and click Save — do NOT wait for success toast."""
        self.log.info("Attempting to create user: %s (expecting rejection)", user.username)
        self.click_add()
        self.select_dropdown_option("User Role", user.user_role)
        self.pick_autocomplete_option("Employee Name", user.employee_name[:3])
        self.select_dropdown_option("Status", user.status)
        self.fill_text_field("Username", user.username)
        self._fill_password_fields(user.password, user.password)
        self._click_save()

    @allure.step("Submit an empty Add User form")
    def submit_empty_add_form(self) -> None:
        self.log.info("Submitting empty Add User form")
        self.click_add()
        self._click_save()

    @allure.step("Assert Add User form field errors: {expected}")
    def expect_add_form_field_errors(self, expected: dict[str, str]) -> None:
        """Assert each `label -> message` pair matches the inline error on that field.

        Confirm Password on OrangeHRM shows "Passwords do not match" when both
        password fields are empty (not "Required"), so callers pass per-field
        expectations rather than one blanket message.
        """
        self.log.info("Asserting field errors on: %s", expected)
        for label, message in expected.items():
            expect(self._field_error_by_label(label)).to_have_text(message)

    @allure.step("Assert Username field shows 'Already exists'")
    def expect_username_already_exists(self) -> None:
        self.log.info("Asserting duplicate-username error on Username field")
        expect(self._field_error_by_label("Username")).to_have_text("Already exists")

    @allure.step("Return to the User Management list")
    def return_to_list(self) -> None:
        """Leave the current form (Add / Edit) and go back to the users list."""
        self.log.info("Returning to User Management list")
        self.page.get_by_role("link", name="Admin").click()
        expect(
            self.page.get_by_role("heading", name="User Management")
        ).to_be_visible()

    def _field_error_by_label(self, label: str) -> Locator:
        return self._field_by_label(label).locator(".oxd-input-field-error-message")

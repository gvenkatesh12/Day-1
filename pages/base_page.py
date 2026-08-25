"""Shared behaviour for every OrangeHRM page object."""
from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from utils.logger import get_logger


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page
        # One logger per page-object subclass, named for its module so log
        # lines identify which page emitted them (pages.admin_user_page, ...).
        self.log = get_logger(self.__class__.__module__)

    # ---------- OrangeHRM custom-widget helpers ----------
    #
    # OrangeHRM uses Angular-style custom dropdowns (oxd-select) rather than
    # native <select>, and an autocomplete input for employee names. These
    # helpers keep that quirk out of individual page objects.

    def select_dropdown_option(self, label: str, option_text: str) -> None:
        """Open the oxd-select associated with `label` and pick `option_text`."""
        self.log.debug("Selecting %r from dropdown %r", option_text, label)
        field = self._field_by_label(label)
        field.locator(".oxd-select-text").click()
        listbox = self.page.locator("div[role='listbox']")
        expect(listbox).to_be_visible()
        listbox.get_by_role("option", name=option_text, exact=True).click()
        expect(field.locator(".oxd-select-text-input")).to_have_text(option_text)

    def fill_text_field(self, label: str, value: str) -> None:
        self.log.debug("Filling %r with %r", label, value)
        field = self._field_by_label(label)
        input_box = field.locator("input")
        input_box.fill(value)
        expect(input_box).to_have_value(value)

    def pick_autocomplete_option(self, label: str, typed: str) -> str:
        """Type into an autocomplete and select the first suggestion.

        Returns the option's visible text so callers can assert on it.
        """
        self.log.debug("Picking autocomplete option for %r (typed=%r)", label, typed)
        field = self._field_by_label(label)
        input_box = field.locator("input")
        input_box.click()
        input_box.press_sequentially(typed, delay=20)
        options = self.page.locator("div[role='listbox'] div[role='option']")
        # Wait until suggestions load (the transient "Searching..." entry disappears).
        expect(options.first).not_to_have_text("Searching....", timeout=15_000)
        first = options.first
        # text_content() preserves the raw text that OrangeHRM will write into the
        # input on click; inner_text() would collapse repeated spaces and diverge
        # from the input value for names like "Ranga  Akunuri".
        chosen = (first.text_content() or "").strip()
        first.click()
        expect(input_box).to_have_value(chosen)
        self.log.info("Selected autocomplete option: %s", chosen)
        return chosen

    # ---------- internals ----------

    def _field_by_label(self, label: str) -> Locator:
        """Return the .oxd-input-group wrapper whose label matches `label`.

        Exact match (allowing optional trailing '*' for required-field markers)
        so "Password" does not also match "Confirm Password".
        """
        return self.page.locator(".oxd-input-group").filter(
            has=self.page.locator(
                ".oxd-label",
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*\*?\s*$"),
            )
        )

"""
browser_booking.py — Kiwi booking helper.

  Given name  : input[name="passengers.0.firstname"]
  Surname     : input[name="passengers.0.surname"]
  Nationality : select[name="passengers.0.nationality"]  (247 opts, e.g. "China")
  Gender      : select[name="passengers.0.title"]        (Male / Female)
  DOB Day     : input[data-test="day"]
  DOB Month   : select[data-test="month"]                (January … December)
  DOB Year    : input[data-test="year"]
  No baggage  : input[data-test="Baggage-NoBagsToCheckIn"]  (checkbox)
  No insurance: radio — text "No insurance"
"""

from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

HEADLESS = True

QUESTION_TEXT = {
    "given_name":  "What is the passenger's given name as shown on the passport?",
    "surname":     "What is the passenger's surname as shown on the passport?",
    "nationality": "What is the passenger's nationality? (e.g. CN, US, GB, JP, KR)",
    "gender":      "What is the passenger's gender? (male / female)",
    "dob_day":     "What is the passenger's birth day? (1-31)",
    "dob_month":   "What is the passenger's birth month? (1-12)",
    "dob_year":    "What is the passenger's birth year? (YYYY)",
    "email":       "What email should Kiwi use for booking updates?",
    "phone":       "What phone number should Kiwi use for booking updates?",
}

ORDERED_FIELDS = [
    "given_name", "surname", "nationality", "gender",
    "dob_day", "dob_month", "dob_year", "email", "phone",
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# 2-letter ISO → Kiwi option label (从诊断结果第2个 select 的 options 里确认)
NAT_MAP = {
    "AF": "Afghanistan", "AL": "Albania", "DZ": "Algeria",
    "AU": "Australia", "AT": "Austria", "BE": "Belgium",
    "BR": "Brazil", "CA": "Canada", "CL": "Chile",
    "CN": "China", "CO": "Colombia", "HR": "Croatia",
    "CZ": "Czechia", "DK": "Denmark", "EG": "Egypt",
    "FI": "Finland", "FR": "France", "DE": "Germany",
    "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary",
    "IN": "India", "ID": "Indonesia", "IE": "Ireland",
    "IL": "Israel", "IT": "Italy", "JP": "Japan",
    "KZ": "Kazakhstan", "KE": "Kenya", "KR": "South Korea",
    "KW": "Kuwait", "MY": "Malaysia", "MX": "Mexico",
    "MA": "Morocco", "NL": "Netherlands", "NZ": "New Zealand",
    "NG": "Nigeria", "NO": "Norway", "PK": "Pakistan",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal",
    "QA": "Qatar", "RO": "Romania", "RU": "Russia",
    "SA": "Saudi Arabia", "SG": "Singapore", "ZA": "South Africa",
    "ES": "Spain", "SE": "Sweden", "CH": "Switzerland",
    "TW": "Taiwan", "TH": "Thailand", "TR": "Turkey",
    "UA": "Ukraine", "AE": "United Arab Emirates",
    "GB": "United Kingdom", "US": "United States",
    "VN": "Vietnam",
}


def c(text, code):
    return f"\033[{code}m{text}\033[0m"

GREEN = "32"; YELLOW = "33"; RED = "31"; CYAN = "36"; BOLD = "1"; DIM = "2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def shot(page, name: str) -> str:
    path = str(SCREENSHOT_DIR / f"{name}_{int(time.time() * 1000)}.png")
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        pass
    return path


def read_page(page) -> str:
    try:
        return page.inner_text("body", timeout=5000)
    except Exception:
        return ""


def dismiss_cookie(page) -> None:
    for sel in [
        'button:has-text("Reject all")',
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=500):
                loc.click()
                page.wait_for_timeout(700)
                return
        except Exception:
            pass


def passenger_form_present(page) -> bool:
    for sel in [
        'input[name="passengers.0.firstname"]',
        'input[name="passengers.0.surname"]',
        'select[name="passengers.0.nationality"]',
        'select[name="passengers.0.title"]',
        'input[data-test="day"]',
        'select[data-test="month"]',
        'input[data-test="year"]',
    ]:
        try:
            if page.locator(sel).first.count() > 0:
                return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Step detection
# ---------------------------------------------------------------------------

def detect_step(page) -> str:
    text = read_page(page).lower()
    if "price has increased" in text or "continue with this price" in text:
        return "confirmation"
    if any(k in text for k in ["pay with", "apple pay", "google pay", "paypal", "billing details"]):
        return "payment"
    try:
        if passenger_form_present(page):
            return "passengers"
    except Exception:
        pass
    try:
        if page.locator('input[type="email"], input[name*="email" i], input[data-test*="email" i]').count() > 0:
            if any(k in text for k in ["passenger", "contact", "date of birth", "nationality"]):
                return "passengers"
    except Exception:
        pass
    if any(k in text for k in ["we use cookies", "reject all", "cookie policy"]):
        return "cookie"
    if any(k in text for k in ["credit card", "card number", "name on card",
                                "security code", "cvv", "pay now"]):
        return "payment"
    if any(k in text for k in ["primary passenger", "given names", "surnames",
                                "nationality", "date of birth", "travel insurance",
                                "checked baggage", "cabin or carry-on baggage"]):
        return "passengers"
    # Ticket fare pages (multiple variants)
    if any(k in text for k in [
        "no thanks, i'll take the risk",
        "medical cancellation",
        "no medical cancellation",
        "continue with saver",
        "continue with standard",
        "basic saver",
        "basic standard",
        "basic flexi",
        "get the option to change or cancel",
        "select airline fare",
    ]):
        return "fare"
    if "select your seat" in text or "seat map" in text:
        return "seating"
    if "customize your trip" in text:
        return "customize"
    # Step 4 seating — skip
    if "seating" in text:
        return "seating"
    return "unknown"


# ---------------------------------------------------------------------------
# Field fillers — all use exact selectors from DOM dump
# ---------------------------------------------------------------------------

def _fill(page, selector: str, value: str, label: str) -> bool:
    try:
        loc = page.locator(selector).first
        if loc.count() == 0 or not loc.is_visible(timeout=1000):
            print(c(f"  ✗ {label}: selector not found [{selector}]", RED))
            return False
        loc.scroll_into_view_if_needed(timeout=1000)
        loc.click(timeout=1000)
        loc.fill("")
        loc.type(value, delay=40)
        try:
            actual = loc.input_value(timeout=500)
            if actual.strip() != value.strip():
                loc.fill(value, timeout=1000)
                actual = loc.input_value(timeout=500)
            if actual.strip() != value.strip():
                loc.evaluate(
                    """(el, value) => {
                        el.value = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                    }""",
                    value,
                )
        except Exception:
            pass
        print(c(f"  ✓ {label}: '{value}'", GREEN))
        return True
    except Exception as e:
        print(c(f"  ✗ {label}: {e}", RED))
        return False


def _select(page, selector: str, label_value: str, label: str) -> bool:
    """原生 <select> select_option，先精确再模糊匹配"""
    try:
        loc = page.locator(selector).first
        if loc.count() == 0 or not loc.is_visible(timeout=1000):
            print(c(f"  ✗ {label}: selector not found [{selector}]", RED))
            return False
        loc.scroll_into_view_if_needed(timeout=1000)

        # 精确匹配
        try:
            loc.select_option(label=label_value, timeout=2000)
            print(c(f"  ✓ {label}: '{label_value}'", GREEN))
            return True
        except Exception:
            pass

        # 模糊匹配：遍历 options 找包含目标文字的
        opt_loc = loc.locator("option")
        count = opt_loc.count()
        for i in range(count):
            try:
                opt_text = opt_loc.nth(i).inner_text()
                if label_value.lower() in opt_text.lower():
                    loc.select_option(label=opt_text, timeout=1000)
                    print(c(f"  ✓ {label}: '{opt_text}' (fuzzy)", GREEN))
                    return True
            except Exception:
                pass

        print(c(f"  ✗ {label}: '{label_value}' not found in options", RED))
        return False
    except Exception as e:
        print(c(f"  ✗ {label}: {e}", RED))
        return False


def fill_given_name(page, value: str) -> bool:
    print(c(f"  → Given Name: {value}", CYAN))
    return _fill(page, 'input[name="passengers.0.firstname"]', value, "Given Name")


def fill_surname(page, value: str) -> bool:
    print(c(f"  → Surname: {value}", CYAN))
    return _fill(page, 'input[name="passengers.0.surname"]', value, "Surname")


def select_nationality(page, value: str) -> bool:
    nat_full = NAT_MAP.get(value.upper(), value)
    print(c(f"  → Nationality: {nat_full}", CYAN))
    return _select(
        page,
        'select[name="passengers.0.nationality"]',
        nat_full,
        "Nationality",
    )


def select_gender(page, value: str) -> bool:
    gender_value = "Male" if value.lower().startswith("m") else "Female"
    print(c(f"  → Gender: {gender_value}", CYAN))
    return _select(
        page,
        'select[name="passengers.0.title"]',
        gender_value,
        "Gender",
    )


def fill_dob_day(page, value: str) -> bool:
    print(c(f"  → DOB Day: {value}", CYAN))
    return _fill(page, 'input[data-test="day"]', value, "DOB Day")


def select_dob_month(page, value: str) -> bool:
    try:
        month_name = MONTH_NAMES[int(value) - 1]
    except Exception:
        print(c(f"  ✗ Month: invalid value '{value}'", RED))
        return False
    print(c(f"  → Birth Month: {month_name}", CYAN))
    return _select(page, 'select[data-test="month"]', month_name, "Month")


def fill_dob_year(page, value: str) -> bool:
    print(c(f"  → DOB Year: {value}", CYAN))
    return _fill(page, 'input[data-test="year"]', value, "DOB Year")


def fill_email(page, value: str) -> bool:
    print(c(f"  → Email: {value}", CYAN))
    for sel in [
        'input[type="email"]',
        'input[placeholder*="email" i]',
        'input[placeholder*="@" i]',
        'input[name*="email" i]',
        'input[data-test*="email" i]',
        'input[aria-label*="email" i]',
        'input[autocomplete="email"]',
    ]:
        if _fill(page, sel, value, "Email"):
            return True
    return False


def split_phone(value: str) -> tuple[str | None, str]:
    raw = value.strip()
    match = re.match(r"^\s*(\+\d{1,3})[\s\-().]*(.*)$", raw)
    if not match:
        return None, re.sub(r"\D+", "", raw)
    country_code = match.group(1)
    national_number = re.sub(r"\D+", "", match.group(2))
    return country_code, national_number


def select_phone_country(page, country_code: str) -> bool:
    country_labels = {
        "+1": ["United States", "United States of America", "+1"],
        "+44": ["United Kingdom", "+44"],
        "+86": ["China", "+86"],
        "+81": ["Japan", "+81"],
        "+82": ["South Korea", "Korea", "+82"],
    }
    labels = country_labels.get(country_code, [country_code])
    try:
        clicked = page.evaluate(
            """(countryCode) => {
                const candidates = Array.from(document.querySelectorAll('button, [role="button"], div'))
                    .filter((el) => (el.innerText || '').trim() === countryCode);
                const target = candidates[0] || Array.from(document.querySelectorAll('button, [role="button"]'))
                    .find((el) => /^\\+\\d{1,4}$/.test((el.innerText || '').trim()));
                if (!target) return false;
                target.scrollIntoView({ block: 'center' });
                target.click();
                return true;
            }""",
            country_code,
        )
        if not clicked:
            return False
        page.wait_for_timeout(500)
        for label in labels:
            for sel in [
                f'text="{label}"',
                f'[role="option"]:has-text("{label}")',
                f'li:has-text("{label}")',
                f'button:has-text("{label}")',
            ]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible(timeout=700):
                        loc.scroll_into_view_if_needed()
                        loc.click(timeout=1200)
                        page.wait_for_timeout(300)
                        print(c(f"  ✓ Phone country: '{country_code}'", GREEN))
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    print(c(f"  ⚠ Phone country '{country_code}' not selected", YELLOW))
    return False


def fill_phone(page, value: str) -> bool:
    print(c(f"  → Phone: {value}", CYAN))
    country_code, national_number = split_phone(value)
    if country_code:
        select_phone_country(page, country_code)
    phone_value = national_number or re.sub(r"\D+", "", value)
    for sel in [
        'input[type="tel"]',
        'input[name*="phone" i]',
        'input[name*="telephone" i]',
        'input[data-test*="phone" i]',
        'input[aria-label*="phone" i]',
        'input[placeholder*="phone" i]',
        'input[autocomplete="tel"]',
    ]:
        if _fill(page, sel, phone_value, "Phone"):
            return True
    try:
        changed = page.evaluate(
            """(value) => {
                const labels = Array.from(document.querySelectorAll('label, div, span'))
                    .filter((el) => /phone/i.test(el.textContent || ''));
                for (const label of labels) {
                    let root = label.closest('section, form, div');
                    for (let depth = 0; root && depth < 5; depth += 1, root = root.parentElement) {
                        const inputs = Array.from(root.querySelectorAll('input'));
                        const target = inputs.find((input) => {
                            const current = input.value || '';
                            const type = (input.getAttribute('type') || '').toLowerCase();
                            return type !== 'hidden' && !current.includes('@') && !/^\\+\\d{1,4}$/.test(current);
                        });
                        if (target) {
                            target.value = value;
                            target.dispatchEvent(new Event('input', { bubbles: true }));
                            target.dispatchEvent(new Event('change', { bubbles: true }));
                            target.dispatchEvent(new Event('blur', { bubbles: true }));
                            return true;
                        }
                    }
                }
                return false;
            }""",
            phone_value,
        )
        if changed:
            print(c(f"  ✓ Phone: '{phone_value}' (label fallback)", GREEN))
            return True
    except Exception:
        pass
    return False


def fill_contact_details(page, collected: dict[str, Any]) -> None:
    if collected.get("email"):
        fill_email(page, str(collected["email"]))
        page.wait_for_timeout(150)
    if collected.get("phone"):
        fill_phone(page, str(collected["phone"]))
        page.wait_for_timeout(150)


def select_no_checked_baggage(page) -> bool:
    print(c(f"  → No checked baggage", CYAN))
    # data-test="Baggage-NoBagsToCheckIn" 是 checkbox
    try:
        loc = page.locator('input[data-test="Baggage-NoBagsToCheckIn"]').first
        if loc.count() > 0 and loc.is_visible(timeout=1000):
            if not loc.is_checked():
                loc.scroll_into_view_if_needed(timeout=500)
                loc.click(timeout=1200)
                page.wait_for_timeout(300)
            print(c(f"  ✓ No checked baggage selected", GREEN))
            return True
    except Exception as e:
        print(c(f"  ✗ No checked baggage (data-test): {e}", YELLOW))

    # 兜底：点击 label 文字
    try:
        loc = page.locator("text=I don't need checked baggage").first
        if loc.count() > 0 and loc.is_visible(timeout=500):
            loc.scroll_into_view_if_needed()
            loc.click(timeout=1200)
            page.wait_for_timeout(300)
            print(c(f"  ✓ No checked baggage (text click)", GREEN))
            return True
    except Exception:
        pass

    print(c(f"  ⚠ No checked baggage not found", YELLOW))
    return False


def select_no_insurance(page) -> bool:
    print(c(f"  → No insurance", CYAN))
    # DOM 里是 radio input，共3个 (Travel Plus / Travel Basic / No insurance)
    # data-test 未知，用 label 文字定位
    for sel in [
        "text=No insurance",
        'label:has-text("No insurance")',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=700):
                loc.scroll_into_view_if_needed()
                loc.click(timeout=1200)
                page.wait_for_timeout(300)
                print(c(f"  ✓ No insurance selected", GREEN))
                return True
        except Exception:
            pass
    print(c(f"  ⚠ No insurance not found", YELLOW))
    return False


def click_no_thanks(page) -> bool:
    """
    fare 步骤：按默认/最便宜选项推进。
    处理两种子页面：
      A) 医疗取消险页  → 点 "No thanks, I'll take the risk"
      B) Fare 选择页   → 点 "Continue with Saver"（最便宜）
    """
    attempts = [
        # A: 医疗取消险
        'button:has-text("No thanks")',
        "text=No thanks, I'll take the risk",
        # B: Fare 选择（按价格从低到高）
        'button:has-text("Continue with Saver")',
        'button:has-text("Continue with Basic")',
        'button:has-text("Continue")',
    ]
    for sel in attempts:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=700):
                loc.scroll_into_view_if_needed()
                txt = (loc.inner_text(timeout=300) or "").strip()
                loc.click(timeout=1500)
                page.wait_for_timeout(2500)
                print(f"  \033[32m✓ Fare step: clicked '{txt}'\033[0m")
                return True
        except Exception:
            pass
    return False


def click_continue(page) -> bool:
    for sel in [
        'button:has-text("Continue")',
        '[role="button"]:has-text("Continue")',
        'button[type="submit"]',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=700):
                loc.scroll_into_view_if_needed()
                loc.click(timeout=1500)
                page.wait_for_timeout(2500)
                return True
        except Exception:
            pass
    return False


def confirmation_question(page) -> str:
    text = read_page(page)
    if "price has increased" in text.lower():
        return "Kiwi says the price has increased. Reply 'continue' to accept the new price, or 'back' to return to search."
    return "Kiwi needs confirmation before continuing. Reply 'continue' to proceed or tell me what to choose."


# ---------------------------------------------------------------------------
# Main passenger page handler
# ---------------------------------------------------------------------------

def handle_kiwi_passenger_page(page, collected: dict[str, Any]) -> None:
    print(c("\n[handle_kiwi_passenger_page] Starting...", BOLD))
    shot(page, "passenger_start")

    if collected.get("given_name"):
        fill_given_name(page, str(collected["given_name"]))
        page.wait_for_timeout(150)

    if collected.get("surname"):
        fill_surname(page, str(collected["surname"]))
        page.wait_for_timeout(150)

    if collected.get("nationality"):
        select_nationality(page, str(collected["nationality"]))
        page.wait_for_timeout(200)

    if collected.get("gender"):
        select_gender(page, str(collected["gender"]))
        page.wait_for_timeout(200)

    if collected.get("dob_day"):
        fill_dob_day(page, str(collected["dob_day"]))
        page.wait_for_timeout(150)

    if collected.get("dob_month"):
        select_dob_month(page, str(collected["dob_month"]))
        page.wait_for_timeout(200)

    if collected.get("dob_year"):
        fill_dob_year(page, str(collected["dob_year"]))
        page.wait_for_timeout(150)

    fill_contact_details(page, collected)

    select_no_checked_baggage(page)
    select_no_insurance(page)

    shot(page, "passenger_filled")
    print(c("[handle_kiwi_passenger_page] Done.", GREEN))



def _advance_one_step(page) -> None:
    """
    根据 data-test 属性精准点击，已通过 DOM 诊断确认：
      - Fare选择页  : div[data-test*="FareType"] 或内含 "Continue with Saver" 的 div
      - 医疗取消险页: div[data-test="tripCancellation-free-Button"]
      - 其他页面    : button:has-text("Continue")
    """
    text = read_page(page).lower()

    # 1. 医疗取消险页 — data-test 精准定位（已确认）
    if "no thanks" in text or "no medical cancellation" in text or "tripCancellation" in page.content():
        for sel in [
            '[data-test="tripCancellation-free-Button"]',
            '[data-test*="tripCancellation-free"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible(timeout=700):
                    loc.scroll_into_view_if_needed()
                    loc.click(timeout=1500)
                    page.wait_for_timeout(2000)
                    print(c("  ✓ Skipped medical cancellation", GREEN))
                    return
            except Exception:
                pass
        # JS 兜底
        try:
            page.evaluate("""
                () => {
                    const el = document.querySelector('[data-test="tripCancellation-free-Button"]');
                    if (el) { el.click(); return; }
                    // 找所有含 No thanks 文字的可点击元素
                    const all = Array.from(document.querySelectorAll('[role="button"], button, li'));
                    const t = all.find(e => e.innerText && e.innerText.includes('No thanks'));
                    if (t) t.click();
                }
            """)
            page.wait_for_timeout(2000)
            print(c("  ✓ Skipped medical cancellation (JS)", GREEN))
            return
        except Exception:
            pass

    # 2. Fare 选择页 — Continue with Saver 也是 div[role="button"]
    if "continue with saver" in text:
        try:
            page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('[role="button"], button, div, li'));
                    const t = all.find(e => e.innerText && e.innerText.trim().startsWith('Continue with Saver'));
                    if (t) t.click();
                }
            """)
            page.wait_for_timeout(2000)
            print(c("  ✓ Fare: selected Saver (JS)", GREEN))
            return
        except Exception:
            pass

    # 3. 通用 Continue 按钮
    click_continue(page)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

@dataclass
class BookingSession:
    booking_url: str
    headless: bool = HEADLESS
    browser: Any = None
    page: Any = None
    screenshots: list[str] = field(default_factory=list)
    _collected_cache: dict[str, Any] = field(default_factory=dict)

    def open(self) -> dict:
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        ctx = self.browser.new_context(
            viewport={"width": 1440, "height": 1100},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = ctx.new_page()
        self.page.goto(self.booking_url, wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(2500)
        dismiss_cookie(self.page)
        self.page.wait_for_timeout(800)
        return self.snapshot_status()

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if hasattr(self, "_pw"):
                self._pw.stop()

    def snapshot_status(self) -> dict:
        step = detect_step(self.page)
        snap = shot(self.page, f"status_{step}")
        self.screenshots.append(snap)
        return {
            "step": step,
            "missing_fields": self.get_missing_fields(),
            "screenshot": snap,
            "url": self.page.url,
        }

    def get_missing_fields(self) -> list[str]:
        if detect_step(self.page) != "passengers":
            return []
        page_text = read_page(self.page).lower()
        missing = []
        try:
            if self.page.locator('input[name="passengers.0.firstname"]').count() > 0:
                missing.append("given_name")
            if self.page.locator('input[name="passengers.0.surname"]').count() > 0:
                missing.append("surname")
            if self.page.locator('select[name="passengers.0.nationality"]').count() > 0:
                missing.append("nationality")
            if self.page.locator('select[name="passengers.0.title"]').count() > 0:
                missing.append("gender")
            if self.page.locator('input[data-test="day"]').count() > 0:
                missing.append("dob_day")
            if self.page.locator('select[data-test="month"]').count() > 0:
                missing.append("dob_month")
            if self.page.locator('input[data-test="year"]').count() > 0:
                missing.append("dob_year")
            if self.page.locator('input[type="email"], input[name*="email" i], input[data-test*="email" i]').count() > 0:
                missing.append("email")
            if self.page.locator('input[type="tel"], input[name*="phone" i], input[data-test*="phone" i]').count() > 0:
                missing.append("phone")
        except Exception:
            pass

        if not missing:
            if "given names" in page_text:   missing.append("given_name")
            if "surnames" in page_text:      missing.append("surname")
            if "nationality" in page_text:   missing.append("nationality")
            if "gender" in page_text:        missing.append("gender")
            if "date of birth" in page_text: missing.extend(["dob_day", "dob_month", "dob_year"])
            if "email" in page_text:         missing.append("email")
            if "phone" in page_text:         missing.append("phone")

        ordered = []
        for f in ORDERED_FIELDS:
            if f in missing and not self._collected_cache.get(f):
                ordered.append(f)
        return ordered

    def next_question(self, collected: dict[str, Any]) -> dict | None:
        self._collected_cache = dict(collected)
        status = self.snapshot_status()
        if status["step"] == "payment":
            return None
        if status["step"] == "confirmation":
            return {
                "field": None,
                "question": confirmation_question(self.page),
                "status": status,
            }
        for field_name in status["missing_fields"]:
            if not collected.get(field_name):
                return {
                    "field": field_name,
                    "question": QUESTION_TEXT[field_name],
                    "status": status,
                }
        return {"field": None, "question": None, "status": status}

    def apply_collected_fields(self, collected: dict[str, Any]) -> dict:
        step = detect_step(self.page)
        if step == "cookie":
            dismiss_cookie(self.page)
            self.page.wait_for_timeout(500)
        elif step == "payment":
            fill_contact_details(self.page, collected)
            self.page.wait_for_timeout(700)
        elif step == "passengers" or passenger_form_present(self.page):
            handle_kiwi_passenger_page(self.page, collected)
            self.page.wait_for_timeout(700)
        else:
            _advance_one_step(self.page)
        return self.snapshot_status()

    def continue_if_possible(self) -> dict:
        """
        从当前页面推进，循环处理所有中间页面，直到到达 passengers 或 payment。
        - passengers页: 点 Continue 按钮离开
        - fare页(医疗险/fare选择): 用 _advance_one_step 处理对应按钮
        - seating/customize: 点 Continue
        """
        for _ in range(10):
            step = detect_step(self.page)
            if step == "payment":
                break
            if step == "passengers":
                # 乘客页：点 Continue 离开
                clicked = click_continue(self.page)
                self.page.wait_for_timeout(1500)
                if not clicked:
                    break
                # 点完后检查是否真的离开了
                if detect_step(self.page) == "passengers":
                    break  # 还在passengers页说明有验证错误，停下
            else:
                # fare/seating/customize/unknown: 智能推进
                _advance_one_step(self.page)
                self.page.wait_for_timeout(1500)
                new_step = detect_step(self.page)
                if new_step in {"passengers", "payment"}:
                    break

        return self.snapshot_status()

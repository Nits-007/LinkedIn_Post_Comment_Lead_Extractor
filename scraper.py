import re
import time
import logging
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)


def open_browser_and_login(headless: bool = False, slow_mo: int = 100):

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
    logger.info("Log in manually in the browser")

    try:
        page.wait_for_url(
            lambda url: "linkedin.com" in url and "/login" not in url,
            timeout=300_000,  # 5 minutes
        )
    except Exception as e:
        raise TimeoutError(f"Login timed out or failed: {e}")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    logger.info(f"Redirected to: {page.url}")
    return pw, browser, page


def _switch_to_most_recent(page: Page):
    logger.info("Attempting to switch comment sort to Most recent")

    try:
        page.evaluate("window.scrollBy(0, 600)")
        time.sleep(1.5)

        sort_button = None

        sort_button_selectors = [
            "button.comments-sort-order-toggle__trigger",
            ".comments-sort-order-toggle button.artdeco-dropdown__trigger",
            ".comments-sort-order-toggle button",
        ]

        for selector in sort_button_selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    sort_button = btn
                    logger.info(f"Found sort button via: {selector}")
                    break
            except Exception:
                continue

        if not sort_button:
            try:
                sort_button_handle = page.evaluate_handle("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const btn of btns) {
                            const text = (btn.textContent || '').trim().toLowerCase();
                            if ((text.includes('most relevant') || text.includes('most recent'))
                                && btn.offsetParent !== null
                                && btn.getBoundingClientRect().height > 0) {
                                return btn;
                            }
                        }
                        return null;
                    }
                """)
                if sort_button_handle:
                    sort_button = sort_button_handle.as_element()
                    if sort_button:
                        logger.info("Found sort button via JS text search fallback.")
            except Exception:
                pass

        if not sort_button:
            logger.info("Sort dropdown not found, sort is not available.")
            return

        try:
            btn_text = sort_button.inner_text().strip().lower()
            if "most recent" in btn_text:
                logger.info("Comments are already sorted by Most recent")
                return
        except Exception:
            pass

        try:
            sort_button.scroll_into_view_if_needed()
            time.sleep(0.3)
        except Exception:
            pass

        sort_button.click()
        logger.info("Clicked sort dropdown")

        dropdown_visible = False
        try:
            page.wait_for_selector(
                'ul[role="listbox"], .artdeco-dropdown__content--is-open',
                state="visible",
                timeout=5000,
            )
            dropdown_visible = True
            logger.info("Dropdown menu")
        except Exception:
            logger.info("wait_for_selector timed out for dropdown, trying anyway")

        time.sleep(0.5) 

        clicked = False

        # Method A: Playwright locator with auto-wait (most reliable)
        if not clicked:
            try:
                recent_locator = page.locator('li[role="option"]').filter(has_text="Most recent")
                recent_locator.first.click(timeout=3000)
                clicked = True
                logger.info("Switched to 'Most recent' via Playwright locator (auto-wait).")
                time.sleep(2)
            except Exception as e:
                logger.info(f"Method A (Playwright locator) failed: {e}")

        if not clicked:
            logger.warning("Could not switch to most recent sort order, moving with most relevant.")

    except Exception as e:
        logger.warning(f"Failed to switch comment sort order: {e}. Proceeding anyway.")


def _expand_all_comments(page: Page, max_scrolls: int, scroll_delay: float):

    logger.info("Expanding all comments")

    for attempt in range(max_scrolls):
        expanded = False

        load_more_selectors = [
            "button.comments-comments-list__load-more-comments-button",
            "button[aria-label*='Load more comments']",
            "button[aria-label*='Show previous comments']",
            "button.show-prev-replies",
        ]
        for selector in load_more_selectors:
            buttons = page.query_selector_all(selector)
            for btn in buttons:
                try:
                    if btn.is_visible():
                        btn.click()
                        expanded = True
                        time.sleep(scroll_delay * 0.5)
                except Exception:
                    pass

        see_more_buttons = page.query_selector_all(
            "button.comments-item-text-content__see-more-button, "
            "button[aria-label*='see more']"
        )
        for btn in see_more_buttons:
            try:
                if btn.is_visible():
                    btn.click()
                    time.sleep(0.3)
            except Exception:
                pass

        reply_buttons = page.query_selector_all(
            "button.show-replies-button, "
            "button[aria-label*='replies']"
        )
        for btn in reply_buttons:
            try:
                if btn.is_visible():
                    btn.click()
                    expanded = True
                    time.sleep(scroll_delay * 0.5)
            except Exception:
                pass

        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(scroll_delay)

        if not expanded and attempt > 5:
            at_bottom = page.evaluate(
                "() => (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100"
            )
            if at_bottom:
                logger.info(f"Reached at last after {attempt + 1} scrolls.")
                break

    logger.info("Finished expanding comments.")


def _extract_comments(page: Page, post_url: str) -> list[dict]:
    leads = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    comment_selectors = [
        "article.comments-comment-item",
        "div.comments-comment-entity",
        "[data-test-id='comments-comment-item']",
        "article.comments-comment-entity",
    ]

    comment_elements = []
    for selector in comment_selectors:
        comment_elements = page.query_selector_all(selector)
        if comment_elements:
            logger.info(f"Found {len(comment_elements)} comments using selector: {selector}")
            break

    if not comment_elements:
        comment_elements = page.query_selector_all(
            "[class*='comments-comment-item'], [class*='comments-comment-entity']"
        )
        logger.info(f"Fallback found {len(comment_elements)} comments.")

    seen_profiles = set()

    for elem in comment_elements:
        try:
            name_el = (
                elem.query_selector("span.comments-post-meta__name-text")
                or elem.query_selector("span.comment-item__inline-show-more-text")
                or elem.query_selector("[class*='comment'] a[href*='/in/'] span")
                or elem.query_selector("a[data-test-id='comments-post-meta__actor-link'] span")
            )
            commenter_name = name_el.inner_text().strip() if name_el else "Unknown"

            profile_link_el = (
                elem.query_selector("a.comments-post-meta__name-text")
                or elem.query_selector("a[href*='/in/']")
                or elem.query_selector("a[data-test-id='comments-post-meta__actor-link']")
            )
            commenter_profile_url = ""
            if profile_link_el:
                href = profile_link_el.get_attribute("href") or ""
                if href.startswith("/"):
                    href = "https://www.linkedin.com" + href
                commenter_profile_url = href.split("?")[0]

            text_el = (
                elem.query_selector("span.comments-comment-item__main-content")
                or elem.query_selector("span.comment-item__inline-show-more-text")
                or elem.query_selector("[class*='comments-comment-item-content-body'] span")
                or elem.query_selector("span[class*='comment-item__main-content']")
            )
            comment_text = text_el.inner_text().strip() if text_el else ""

            dedup_key = f"{commenter_profile_url}|{comment_text[:100]}"
            if dedup_key in seen_profiles:
                continue
            seen_profiles.add(dedup_key)

            emails_found = EMAIL_REGEX.findall(comment_text) if comment_text else []
            email = emails_found[0] if emails_found else ""

            leads.append({
                "extracted_at": now,
                "post_url": post_url,
                "commenter_name": commenter_name,
                "commenter_profile_url": commenter_profile_url,
                "comment_text": comment_text,
                "email": email,
            })

        except Exception as e:
            logger.warning(f"Failed to parse a comment element: {e}")
            continue

    logger.info(f"Extracted {len(leads)} unique leads.")
    return leads


def scrape_post_comments(
    page: Page,
    post_url: str,
    max_scrolls: int = 50,
    scroll_delay: float = 2.0,
) -> list[dict]:

    logger.info(f"Navigating to post: {post_url}")

    page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
    logger.info("Post page loaded. Waiting for comments section")

    try:
        page.wait_for_selector(
            "[class*='comments-comment'], [class*='social-details-social-counts']",
            timeout=15000,
        )
    except Exception:
        logger.warning("Comments section not found, trying to trigger it")

    time.sleep(2)  
   
    comments_trigger_selectors = [
        "button[aria-label*='comment']",
        "button.social-details-social-counts__comments-count",
        "li.social-details-social-counts__comments",
    ]
    for selector in comments_trigger_selectors:
        trigger = page.query_selector(selector)
        if trigger and trigger.is_visible():
            try:
                trigger.click()
                time.sleep(2)
                break
            except Exception:
                pass

    _switch_to_most_recent(page)

    _expand_all_comments(page, max_scrolls, scroll_delay)

    leads = _extract_comments(page, post_url)

    return leads

"""
Airbnb search & filter tool.

Searches Airbnb listings and filters by custom keywords/amenities that are not
available in the standard Airbnb search filters.

The structured search parameters (location, dates, budget, amenities, etc.) are
passed to the agent via dependency injection (`deps`) and read directly from
`RunContext`, so they are never parsed or invented by the model:

    from pydantic_ai import Agent
    from api.tools.filter import SearchParams, filter_listings_tool

    agent = Agent(model, deps_type=SearchParams, tools=[filter_listings_tool])

    result = await agent.run(
        "Find me the best match",
        deps=SearchParams(location="Lima, Peru", checkin="2026-09-01", nights=5,
                          max_price=500, amenities=["pool", "gym"]),
    )

It can also be used from the command line:

    python -m api.tools.filter "Lima, Peru" --checkin 2026-09-01 --nights 5 \
        -k sauna -a pool gym --max-price 500 --match-all --superhost -o out.json
"""

import asyncio
import html as html_lib
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from enum import Enum
from typing import Literal, Optional
from urllib.parse import urlencode, urlparse, parse_qs, urljoin

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field, PrivateAttr, field_validator
from pydantic_ai import ModelRetry, RunContext, Tool
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

RoomTypeName = Literal[
    "apartment", "entire_home", "private_room", "shared_room", "hotel_room"
]
ProgressCallback = Callable[[str], Awaitable[None]]

# Search volume defaults — override via env without changing code.
DEFAULT_MAX_LISTINGS = max(1, int(os.getenv("SEARCH_MAX_LISTINGS", "50")))
DEFAULT_TOP_K = max(1, int(os.getenv("SEARCH_TOP_K", "10")))


class RoomType(str, Enum):
    """Airbnb room types."""
    ENTIRE_HOME = "Entire home/apt"
    APARTMENT = "Entire home/apt"  # Alias for entire home (most common)
    PRIVATE_ROOM = "Private room"
    SHARED_ROOM = "Shared room"
    HOTEL_ROOM = "Hotel room"


class AmenityID(int, Enum):
    """Common Airbnb amenity IDs."""
    WIFI = 4
    KITCHEN = 8
    WASHER = 33
    DRYER = 34
    AIR_CONDITIONING = 5
    HEATING = 30
    POOL = 7
    HOT_TUB = 25
    GYM = 15
    FREE_PARKING = 9
    EV_CHARGER = 57
    CRIB = 286
    BBQ_GRILL = 99
    BREAKFAST = 16
    FIREPLACE = 27
    WORKSPACE = 47
    TV = 58
    PETS_ALLOWED = 12
    SMOKING_ALLOWED = 11
    WHEELCHAIR_ACCESSIBLE = 6
    ELEVATOR = 21
    BEACH_ACCESS = 671
    WATERFRONT = 671
    SELF_CHECKIN = 51


# Backwards compatibility dict
AMENITIES = {
    "wifi": AmenityID.WIFI,
    "kitchen": AmenityID.KITCHEN,
    "washer": AmenityID.WASHER,
    "dryer": AmenityID.DRYER,
    "air_conditioning": AmenityID.AIR_CONDITIONING,
    "heating": AmenityID.HEATING,
    "pool": AmenityID.POOL,
    "hot_tub": AmenityID.HOT_TUB,
    "gym": AmenityID.GYM,
    "free_parking": AmenityID.FREE_PARKING,
    "ev_charger": AmenityID.EV_CHARGER,
    "crib": AmenityID.CRIB,
    "bbq_grill": AmenityID.BBQ_GRILL,
    "breakfast": AmenityID.BREAKFAST,
    "fireplace": AmenityID.FIREPLACE,
    "workspace": AmenityID.WORKSPACE,
    "tv": AmenityID.TV,
    "pets_allowed": AmenityID.PETS_ALLOWED,
    "smoking_allowed": AmenityID.SMOKING_ALLOWED,
    "wheelchair_accessible": AmenityID.WHEELCHAIR_ACCESSIBLE,
    "elevator": AmenityID.ELEVATOR,
    "beach_access": AmenityID.BEACH_ACCESS,
    "waterfront": AmenityID.WATERFRONT,
    "self_checkin": AmenityID.SELF_CHECKIN,
}


# ============================================================================
# DEFAULT FILTER THRESHOLDS
# ============================================================================
# When results exceed this threshold, apply stricter filters to reduce volume
LISTINGS_THRESHOLD = 200

# When > LISTINGS_THRESHOLD listings found, enforce minimum rating
DEFAULT_MIN_RATING = 4.8

# Concurrent scraping control: enough parallelism to reduce latency without
# opening an unbounded number of Airbnb pages.
MAX_CONCURRENT_LISTINGS = 8

# Cap gallery harvesting: the vision rerank analyzes at most 12 photos per
# listing, so scrolling for more is wasted work.
MAX_GALLERY_PHOTOS = 15
# ============================================================================


class AirbnbSearchFilter(BaseModel):
    """Pydantic model for Airbnb search filters."""

    location: str = Field(..., description="Location to search (e.g., 'Lima, Peru')")

    # Date filters
    checkin: Optional[str] = Field(None, description="Check-in date (YYYY-MM-DD)")
    checkout: Optional[str] = Field(None, description="Check-out date (YYYY-MM-DD)")

    # Guest & room filters
    guests: int = Field(default=1, ge=1, le=16, description="Number of guests")
    room_type: Optional[RoomType] = Field(None, description="Room type")
    min_bedrooms: Optional[int] = Field(None, ge=1, description="Minimum bedrooms")
    min_beds: Optional[int] = Field(None, ge=1, description="Minimum beds")
    min_bathrooms: Optional[int] = Field(None, ge=1, description="Minimum bathrooms")

    # Price filters
    min_price: Optional[int] = Field(None, ge=0, description="Minimum price per night")
    max_price: Optional[int] = Field(None, ge=0, description="Maximum price per night")

    # Rating filter
    min_rating: Optional[float] = Field(None, ge=1.0, le=5.0, description="Minimum host rating")

    # Amenities
    amenities: Optional[list] = Field(None, description="List of amenity IDs")

    # Host filters
    superhost: bool = Field(default=False, description="Only show superhosts")
    instant_book: bool = Field(default=False, description="Only show instant book listings")
    self_checkin: bool = Field(default=False, description="Only show self check-in listings")

    @field_validator("checkin", "checkout", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        """Validate date format is YYYY-MM-DD."""
        if v is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("max_price", mode="before")
    @classmethod
    def validate_prices(cls, v, info):
        """Validate max_price >= min_price."""
        if v is not None and info.data.get("min_price"):
            if v < info.data["min_price"]:
                raise ValueError("max_price must be >= min_price")
        return v

    def build_url(self) -> str:
        """Build Airbnb search URL from filter parameters using urllib."""
        base_url = f"https://www.airbnb.com/s/{self.location.replace(' ', '-').replace(',', '--')}/homes"

        params = {}

        # Date parameters
        if self.checkin:
            params["checkin"] = self.checkin
        if self.checkout:
            params["checkout"] = self.checkout

        # Guest count
        params["adults"] = self.guests

        # Price parameters
        if self.min_price is not None:
            params["price_min"] = self.min_price
        if self.max_price is not None:
            params["price_max"] = self.max_price

        # Room type filter
        if self.room_type:
            params["room_types[]"] = self.room_type.value

        # Amenities (build array params)
        if self.amenities:
            params["amenities[]"] = self.amenities

        # Boolean filters
        if self.superhost:
            params["superhost"] = "true"
        if self.instant_book:
            params["ib"] = "true"
        if self.self_checkin:
            if not params.get("amenities[]"):
                params["amenities[]"] = []
            if isinstance(params["amenities[]"], list):
                params["amenities[]"].append(AmenityID.SELF_CHECKIN.value)

        # Bedroom/bed/bathroom filters
        if self.min_bedrooms is not None:
            params["min_bedrooms"] = self.min_bedrooms
        if self.min_beds is not None:
            params["min_beds"] = self.min_beds
        if self.min_bathrooms is not None:
            params["min_bathrooms"] = self.min_bathrooms

        # Build query string with urlencode
        # Handle list params (amenities[])
        query_parts = []
        for key, value in params.items():
            if isinstance(value, list):
                for item in value:
                    query_parts.append((key, item))
            else:
                query_parts.append((key, value))

        query_string = urlencode(query_parts)
        return f"{base_url}?{query_string}" if query_string else base_url


def build_search_url(
    location: str,
    checkin: str = None,
    checkout: str = None,
    guests: int = 1,
    min_price: int = None,
    max_price: int = None,
    amenities: list = None,
    room_type: str = None,
    superhost: bool = False,
    instant_book: bool = False,
    self_checkin: bool = False,
    min_bedrooms: int = None,
    min_beds: int = None,
    min_bathrooms: int = None,
) -> str:
    """
    Build Airbnb search URL with parameters (backwards compatible wrapper).

    Args:
        location: Location to search
        checkin: Check-in date (YYYY-MM-DD)
        checkout: Check-out date (YYYY-MM-DD)
        guests: Number of guests
        min_price: Minimum price per night
        max_price: Maximum price per night
        amenities: List of amenity IDs
        room_type: Room type string
        superhost: Only superhosts
        instant_book: Only instant book
        self_checkin: Only self check-in
        min_bedrooms: Minimum bedrooms
        min_beds: Minimum beds
        min_bathrooms: Minimum bathrooms

    Returns:
        Airbnb search URL
    """
    # Convert room_type string to enum if provided
    room_type_enum = None
    if room_type:
        room_type_map = {
            "apartment": RoomType.APARTMENT,
            "entire_home": RoomType.ENTIRE_HOME,
            "private_room": RoomType.PRIVATE_ROOM,
            "shared_room": RoomType.SHARED_ROOM,
            "hotel_room": RoomType.HOTEL_ROOM,
        }
        room_type_enum = room_type_map.get(room_type)

    filter_obj = AirbnbSearchFilter(
        location=location,
        checkin=checkin,
        checkout=checkout,
        guests=guests,
        min_price=min_price,
        max_price=max_price,
        amenities=amenities,
        room_type=room_type_enum,
        superhost=superhost,
        instant_book=instant_book,
        self_checkin=self_checkin,
        min_bedrooms=min_bedrooms,
        min_beds=min_beds,
        min_bathrooms=min_bathrooms,
    )
    return filter_obj.build_url()


def resolve_amenity_ids(amenity_names: Optional[list]) -> Optional[list]:
    """Resolve amenity names (e.g. 'pool', 'gym') to Airbnb amenity IDs."""
    if not amenity_names:
        return None
    ids = []
    for name in amenity_names:
        key = str(name).strip().lower().replace(" ", "_")
        if key not in AMENITIES:
            raise ValueError(
                f"Unknown amenity: '{name}'. Available: {', '.join(sorted(AMENITIES.keys()))}"
            )
        ids.append(AMENITIES[key].value)
    return ids


def create_stealth_browser(playwright):
    """Create a browser with stealth settings to avoid detection."""
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )

    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-US",
        timezone_id="America/New_York",
        geolocation={"longitude": -73.935242, "latitude": 40.730610},
        permissions=["geolocation"],
    )

    # Add stealth scripts
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """)

    return browser, context


# Only photo *URLs* are collected from the page (the vision rerank downloads
# image bytes itself over HTTP), so the browser can skip the heavy responses.
_BLOCKED_RESOURCE_TYPES = frozenset({"image", "media", "font"})


async def _abort_heavy_resources(route) -> None:
    if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
        await route.abort()
    else:
        await route.continue_()


async def create_stealth_browser_async(playwright):
    """Async version: create a browser with stealth settings to avoid detection."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            # NB: --disable-blink-features=AutomationControlled was removed — it
            # no longer hides anything in current Chromium and is itself a known
            # headless-CDP bot tell.
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        # No user_agent override: the bundled UA matches the real Chromium build —
        # a stale hardcoded UA is an easy bot signal.
        locale="en-US",
        timezone_id="America/New_York",
        geolocation={"longitude": -73.935242, "latitude": 40.730610},
        permissions=["geolocation"],
    )

    # Add stealth scripts
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """)

    await context.route("**/*", _abort_heavy_resources)

    return browser, context


def get_listing_urls(page, url: str, max_listings: int = 20, max_pages: int = 5) -> list:
    """
    Step 1: Use the filter URL to generate listings then compile a list of listing URLs.
    Get listing URLs from search results pages with pagination.
    """

    all_listings = []
    seen_urls = set()
    current_page = 1

    # First, load the page and check total listings reported by Airbnb
    print("   📄 Loading search page...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
    except Exception as e:
        print("   ⚠️ Navigation timeout, continuing anyway...")

    # Scroll to load content
    for _ in range(3):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(0.5)

    # Try to find the total count Airbnb reports
    try:
        # Look for text like "1,000+ places" or "Over 1,000 places"
        body_text = page.inner_text("body")
        # Match patterns like "1,000+ places", "300 places", "Over 1,000 places"
        match = re.search(r"([\d,]+)\+?\s*places?", body_text, re.IGNORECASE)
        if match:
            total_reported = match.group(1).replace(",", "")
            print(f"   📊 Airbnb reports: ~{match.group(0)}")
        else:
            # Try alternate pattern
            match = re.search(r"Over\s*([\d,]+)", body_text)
            if match:
                print(f"   📊 Airbnb reports: Over {match.group(1)} places")
    except Exception as e:
        print("   ⚠️ Could not find total count")

    while current_page <= max_pages:
        print(f"   📄 Scraping page {current_page}...")

        if current_page > 1:
            # Navigate to next page by clicking Next button
            try:
                # Scroll down multiple times to ensure pagination is visible
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)

                next_button = page.query_selector("a[aria-label='Next']")
                if next_button:
                    is_disabled = next_button.get_attribute("aria-disabled")
                    if is_disabled == "true":
                        print("   ✓ Reached last page (Next button disabled)")
                        break

                    # Use JavaScript click - more reliable than Playwright click
                    page.evaluate("document.querySelector('a[aria-label=\"Next\"]').click()")
                    time.sleep(5)
                else:
                    print("   ✓ No Next button found - this may be the last page")
                    break
            except Exception as e:
                print(f"   ⚠️ Pagination error: {e}")
                break

        # Scroll to load all listings on current page
        for _ in range(5):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(0.5)

        # Extra scroll to bottom and back
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        # Find listing links on current page
        links = page.query_selector_all("a[href*='/rooms/']")

        page_listings = 0
        for link in links:
            href = link.get_attribute("href")
            if href and "/rooms/" in href:
                # Clean up the URL
                if href.startswith("/"):
                    href = "https://www.airbnb.com" + href
                # Remove query params for deduplication
                base_url = href.split("?")[0]
                if base_url not in seen_urls:
                    seen_urls.add(base_url)
                    all_listings.append(href)
                    page_listings += 1
                    if len(all_listings) >= max_listings:
                        print(f"   ✓ Reached max_listings ({max_listings})")
                        return all_listings

        print(f"      Found {page_listings} new listings on page {current_page} (total: {len(all_listings)})")

        # Check if we got any new listings on this page
        if page_listings == 0 and current_page > 1:
            print("   ✓ No more new listings found")
            break

        current_page += 1

    return all_listings


async def get_listing_urls_async(page, url: str, max_listings: int = 20, max_pages: int = 5) -> list:
    """
    Async version: compile a list of listing URLs from search results pages with pagination.

    Args:
        page: Async Playwright page object
        url: Airbnb search URL
        max_listings: Stop after collecting this many listing URLs
        max_pages: Maximum number of result pages to walk

    Returns:
        List of listing detail URLs
    """

    all_listings = []
    seen_urls = set()
    current_page = 1

    # First, load the page and check total listings reported by Airbnb
    print("   📄 Loading search page...")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("a[href*='/rooms/']", timeout=10000)
    except Exception:
        print("   ⚠️ Navigation timeout, continuing anyway...")

    # Try to find the total count Airbnb reports
    try:
        body_text = await page.inner_text("body")
        match = re.search(r"([\d,]+)\+?\s*places?", body_text, re.IGNORECASE)
        if match:
            print(f"   📊 Airbnb reports: ~{match.group(0)}")
        else:
            match = re.search(r"Over\s*([\d,]+)", body_text)
            if match:
                print(f"   📊 Airbnb reports: Over {match.group(1)} places")
    except Exception:
        print("   ⚠️ Could not find total count")

    while current_page <= max_pages:
        print(f"   📄 Scraping page {current_page}...")

        if current_page > 1:
            # The pagination footer renders after the results list is scrolled
            # through; one jump to the bottom usually triggers it.
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try:
                next_button = await page.wait_for_selector("a[aria-label='Next']", timeout=8000)
            except Exception:
                print("   ✓ No Next button found - this may be the last page")
                break

            if await next_button.get_attribute("aria-disabled") == "true":
                print("   ✓ Reached last page (Next button disabled)")
                break

            first_link = await page.query_selector("a[href*='/rooms/']")
            prev_href = (await first_link.get_attribute("href")) if first_link else ""
            prev_url = page.url
            try:
                await page.evaluate("document.querySelector('a[aria-label=\"Next\"]').click()")
            except Exception as e:
                print(f"   ⚠️ Pagination error: {e}")
                break
            try:
                # Resolve as soon as the new page's results replace the old ones
                # instead of sleeping a fixed amount.
                await page.wait_for_function(
                    """([prevUrl, prevHref]) => {
                        if (location.href !== prevUrl) return true;
                        const el = document.querySelector("a[href*='/rooms/']");
                        return el && el.getAttribute('href') !== prevHref;
                    }""",
                    arg=[prev_url, prev_href],
                    timeout=15000,
                )
            except Exception:
                print("   ⚠️ Timed out waiting for the next page; scanning whatever loaded")

        # Scroll until the listing-link count stops growing (results lazy-load).
        # Require two consecutive stable readings so a slow first render or a
        # brief lull between lazy batches doesn't end the scroll early.
        links = []
        prev_count = -1
        stable_passes = 0
        for _ in range(10):
            links = await page.query_selector_all("a[href*='/rooms/']")
            count = len(links)
            if count > 0 and count == prev_count:
                stable_passes += 1
                if stable_passes >= 2:
                    break
            else:
                stable_passes = 0
            prev_count = count
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.5)

        page_listings = 0
        for link in links:
            href = await link.get_attribute("href")
            if href and "/rooms/" in href:
                if href.startswith("/"):
                    href = "https://www.airbnb.com" + href
                base_url = href.split("?")[0]
                if base_url not in seen_urls:
                    seen_urls.add(base_url)
                    all_listings.append(href)
                    page_listings += 1
                    if len(all_listings) >= max_listings:
                        print(f"   ✓ Reached max_listings ({max_listings})")
                        return all_listings

        print(f"      Found {page_listings} new listings on page {current_page} (total: {len(all_listings)})")

        if page_listings == 0 and current_page > 1:
            print("   ✓ No more new listings found")
            break

        current_page += 1

    return all_listings


def get_listing_details(page, listing_url: str) -> dict:
    """
    Extract comprehensive details from a single Airbnb listing page.

    Args:
        page: Playwright page object with an active browser session
        listing_url: Full URL to the Airbnb listing page

    Returns:
        Dictionary containing listing details
    """
    try:
        page.goto(listing_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
    except Exception:
        print("   ⚠️ Navigation timeout, continuing anyway...")

    details = {
        "url": listing_url,
        "title": "",
        "description": "",
        "amenities": [],
        "house_rules": [],
        "host_info": "",
        "price": None,  # Per-night price in USD
        "rating": None,  # Host rating (1-5)
        "image_url": "",
        "image_urls": [],
        "full_text": "",
    }

    try:
        # Get title
        title_el = page.query_selector("h1")
        if title_el:
            details["title"] = title_el.inner_text()

        # Extract nightly price (usually in header or booking panel)
        try:
            page_text = page.inner_text("body")
            price_match = re.search(r"\$?([\d,]+)\s*(?:per night|\/night|night)", page_text, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1).replace(",", "")
                details["price"] = int(price_str)
        except Exception:
            pass

        # Extract host rating (usually "4.8" or "4.8 (123 reviews)")
        try:
            page_text = page.inner_text("body")
            rating_match = re.search(r"(\d+\.\d+)\s*(?:\([\d,]+\s*reviews?\))?", page_text)
            if rating_match:
                details["rating"] = float(rating_match.group(1))
        except Exception:
            pass

        # Extract ALL listing photos by opening the photo gallery.
        try:
            image_urls = []
            try:
                show_photos = page.query_selector("button:has-text('Show all photos')")
                if show_photos:
                    show_photos.click()
                    time.sleep(2)
                    for _ in range(15):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        time.sleep(0.4)
            except Exception:
                pass

            imgs = page.query_selector_all("img")
            seen = set()
            for img in imgs:
                src = img.get_attribute("src") or ""
                if (
                    "muscache.com/im/pictures/" in src
                    and "platform-assets" not in src
                    and "search-bar-icons" not in src
                    and "/user/" not in src
                ):
                    base = src.split("?")[0]
                    if base not in seen:
                        seen.add(base)
                        image_urls.append(src)

            try:
                close_btn = page.query_selector("button[aria-label='Close']")
                if close_btn:
                    close_btn.click()
                    time.sleep(0.5)
            except Exception:
                pass

            details["image_urls"] = image_urls
            details["image_url"] = image_urls[0] if image_urls else ""
        except Exception:
            pass  # Image extraction is optional

        # Try to click "Show all amenities" button
        try:
            amenities_btn = page.query_selector("button:has-text('Show all')")
            if amenities_btn and "amenities" in amenities_btn.inner_text().lower():
                amenities_btn.click()
                time.sleep(1)
                amenity_els = page.query_selector_all("[data-testid='amenity-row']")
                for el in amenity_els:
                    details["amenities"].append(el.inner_text())
                close_btn = page.query_selector("button[aria-label='Close']")
                if close_btn:
                    close_btn.click()
        except Exception:
            pass

        # Extract house rules from the listing page
        try:
            house_rules_list = []
            try:
                show_rules_btn = page.query_selector("button:has-text('Show')")
                if show_rules_btn and "rules" in page.inner_text().lower():
                    parent = show_rules_btn.evaluate_handle("el => el.closest('div')")
                    parent_text = parent.evaluate("el => el.innerText.toLowerCase()")
                    if "house rules" in parent_text or "rules" in parent_text:
                        show_rules_btn.click()
                        time.sleep(1)
            except Exception:
                pass

            rule_els = page.query_selector_all("[data-testid='rule-item'], li:has-text('rule')")
            if rule_els:
                for el in rule_els:
                    rule_text = el.inner_text().strip()
                    if rule_text:
                        house_rules_list.append(rule_text)

            if not house_rules_list:
                page_text = page.inner_text("body")
                if "house rules" in page_text.lower():
                    match = re.search(r"house\s*rules[\s\S]*?(?=\n\n|[A-Z][a-z]+\s*rules|$)", page_text, re.IGNORECASE)
                    if match:
                        rules_section = match.group(0)
                        rules = re.split(r"\n(?=\d+\.)", rules_section)
                        for rule in rules:
                            rule_text = rule.strip()
                            if rule_text and not rule_text.lower().startswith("house rules"):
                                house_rules_list.append(rule_text)

            details["house_rules"] = house_rules_list
        except Exception:
            pass

        # Get full page text for keyword matching
        details["full_text"] = page.inner_text("body")

    except Exception as e:
        print(f"Error scraping {listing_url}: {e}")

    return details


def _filter_photo_srcs(srcs: list) -> list:
    """Keep listing-photo URLs only (deduped by base URL), skipping avatars/icons."""
    urls = []
    seen = set()
    for src in srcs:
        if (
            src
            and "muscache.com/im/pictures/" in src
            and "platform-assets" not in src
            and "search-bar-icons" not in src
            and "/user/" not in src
        ):
            base = src.split("?")[0]
            if base not in seen:
                seen.add(base)
                urls.append(src)
    return urls


# ============================================================================
# FAST PATH: plain-HTTP detail fetch + embedded-JSON parsing
# ============================================================================
# Airbnb listing pages are server-rendered and ship a
# <script id="data-deferred-state-0"> JSON blob containing title, rating,
# photos, house rules, room type, superhost status and more. Fetching that with
# plain HTTP is far faster than driving a browser — and it also sidesteps the
# bot challenge Airbnb intermittently serves to headless Chromium.

# A desktop UA is enough for Airbnb to serve the full SSR page over plain HTTP.
_HTTP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_DEFERRED_STATE_RE = re.compile(
    r'<script id="data-deferred-state-0"[^>]*>(.*?)</script>', re.S
)
# Photo CDN URLs live on subdomains (a0.muscache.com, ...), not the bare domain.
_PHOTO_URL_RE = re.compile(
    r"https://[a-z0-9]+\.muscache\.com/im/pictures/[a-zA-Z0-9_./%-]+?\.(?:jpeg|jpg|png|webp)"
)
_RATING_RE = re.compile(r'"guestSatisfactionOverall":([\d.]+)')
_REVIEW_COUNT_RE = re.compile(r'"visibleReviewCount":"?([\d,]+)"?')
_META_DESC_RE = re.compile(r'"metaDescription":"((?:[^"\\]|\\.)*)"')
_META_TITLE_RE = re.compile(r'"title":"((?:[^"\\]|\\.)*?)\s+-\s+')
_PRICE_RE = re.compile(
    r'[$€£]\s?([\d,]+)\s*(?:per night|/night)|"priceString":"\$?([\d,]+)', re.IGNORECASE
)
_TAG_RE = re.compile(r"<[^>]+>")


def _unescape_json_string(s: str) -> str:
    """Decode a JSON string fragment that was extracted with a regex."""
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


def _iter_dicts(obj):
    """Yield every dict in a nested structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


def _extract_pdp_details(raw: str, data: dict) -> dict:
    """Parse the fields we need from the embedded Airbnb state JSON."""
    out = {
        "title": "",
        "description": "",
        "amenities": [],
        "house_rules": [],
        "host_info": "",
        "price": None,
        "rating": None,
        "review_count": None,
        "superhost": None,
        "room_type": "",
        "max_guests": None,
        "image_urls": _filter_photo_srcs(_PHOTO_URL_RE.findall(raw)),
    }

    def first(pattern, cast=str):
        m = pattern.search(raw)
        if not m:
            return None
        val = next((g for g in m.groups() if g is not None), None)
        if val is None:
            return None
        try:
            return cast(val.replace(",", ""))
        except (ValueError, TypeError):
            return None

    out["rating"] = first(_RATING_RE, float)
    out["review_count"] = first(_REVIEW_COUNT_RE, int)
    out["price"] = first(_PRICE_RE, int)

    meta = data.get("niobeClientData") or []
    root = None
    try:
        root = meta[0][1]["data"]["presentation"]["stayProductDetailPage"]
    except (IndexError, KeyError, TypeError):
        root = None

    # Title / meta-description live on the SEO metadata object.
    m = _META_DESC_RE.search(raw)
    if m:
        out["description"] = _unescape_json_string(m.group(1))
    m = _META_TITLE_RE.search(raw)
    if m:
        out["title"] = _unescape_json_string(m.group(1))

    if root:
        sections = (root.get("sections") or {}).get("sections") or []
        for section in sections:
            sec = section.get("section") or {}
            tname = sec.get("__typename")
            if tname == "PdpTitleSection" and not out["title"]:
                title = sec.get("title")
                if title:
                    out["title"] = title
            elif tname == "PdpDescriptionSection" and not out["description"]:
                html_desc = (sec.get("htmlDescription") or {}).get("htmlText") or ""
                if html_desc:
                    out["description"] = html_lib.unescape(
                        _TAG_RE.sub(" ", html_desc)
                    ).strip()
            elif tname == "PoliciesSection":
                # The top-level houseRules list is only Airbnb's short
                # preview. houseRulesSections contains the complete grouped
                # rules, including subtitles and custom "Additional rules".
                rules = []
                seen_rules = set()
                for rule_section in sec.get("houseRulesSections") or []:
                    if not isinstance(rule_section, dict):
                        continue
                    section_title = (rule_section.get("title") or "").strip()
                    for item in rule_section.get("items") or []:
                        if not isinstance(item, dict):
                            continue
                        title = (item.get("title") or "").strip()
                        if not title:
                            continue
                        subtitle = (item.get("subtitle") or "").strip()
                        text = f"{title}: {subtitle}" if subtitle else title
                        html_text = ((item.get("html") or {}).get("htmlText") or "").strip()
                        if html_text:
                            additional_rules = [
                                line.strip(" -\t")
                                for line in html_text.splitlines()
                                if line.strip(" -\t")
                            ]
                            if additional_rules:
                                text += ": " + "; ".join(additional_rules)
                        if section_title:
                            text = f"{section_title}: {text}"
                        key = " ".join(text.casefold().split())
                        if key not in seen_rules:
                            seen_rules.add(key)
                            rules.append(text)

                # Preserve the preview as a fallback for older payloads that
                # do not include houseRulesSections.
                if not rules:
                    rules = [
                        item.get("title").strip()
                        for item in sec.get("houseRules") or []
                        if isinstance(item, dict) and item.get("title")
                    ]
                out["house_rules"] = rules

    # These scalar fields sit on the logging/sharing objects; a scan is simpler
    # and more robust than depending on a fixed section layout.
    for d in _iter_dicts(data):
        if out["superhost"] is None and isinstance(d.get("isSuperhost"), bool):
            out["superhost"] = d["isSuperhost"]
        if not out["room_type"] and isinstance(d.get("roomType"), str):
            out["room_type"] = d["roomType"]
        if out["max_guests"] is None and isinstance(d.get("personCapacity"), int):
            out["max_guests"] = d["personCapacity"]
        if out["superhost"] is not None and out["room_type"] and out["max_guests"]:
            break

    return out


async def get_listing_details_http(
    client: httpx.AsyncClient, listing_url: str, harvest_photos: bool = True
) -> Optional[dict]:
    """Fetch a listing page over plain HTTP and parse its embedded state JSON.

    Returns a details dict on success, or None when the response doesn't contain
    the SSR state (bot challenge, layout change, ...) so callers can fall back
    to the browser path. Photos always come from the embedded JSON, so
    harvest_photos only controls how many are kept.
    """
    try:
        resp = await client.get(listing_url, timeout=30, follow_redirects=True)
    except Exception as e:
        print(f"   ⚠️ HTTP fetch failed for {listing_url}: {e}")
        return None
    if resp.status_code != 200 or "data-deferred-state" not in resp.text:
        return None

    m = _DEFERRED_STATE_RE.search(resp.text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    details = _extract_pdp_details(m.group(1), data)
    details["url"] = listing_url
    if not harvest_photos:
        details["image_urls"] = details["image_urls"][:1]
    details["image_url"] = details["image_urls"][0] if details["image_urls"] else ""

    # Keyword search needs readable listing copy, not the raw page: the 500KB
    # HTML/JS would drown the real text in noise. Compose it from the fields
    # we actually extracted instead.
    text_parts = [
        details["title"],
        details["description"],
        "Amenities: " + ", ".join(details["amenities"]) if details["amenities"] else "",
        "House rules: " + ". ".join(details["house_rules"]) if details["house_rules"] else "",
        details["room_type"],
    ]
    details["full_text"] = "\n".join(p for p in text_parts if p)
    return details


async def _harvest_gallery_photos(page, max_photos: int = MAX_GALLERY_PHOTOS) -> list:
    """Open the photo gallery and scroll until the photo count stops growing.

    Accumulates URLs across scrolls so virtualized galleries that unmount
    off-screen photos don't lose earlier ones.
    """
    try:
        show_photos = await page.query_selector("button:has-text('Show all photos')")
        if not show_photos:
            return _filter_photo_srcs(
                await page.eval_on_selector_all("img", "els => els.map(e => e.src)")
            )

        await show_photos.click()
        try:
            await page.wait_for_selector("img[src*='muscache.com/im/pictures/']", timeout=5000)
        except Exception:
            pass
        image_urls: list = []
        seen: set = set()
        prev_count = -1
        stable_passes = 0
        for _ in range(12):
            srcs = await page.eval_on_selector_all("img", "els => els.map(e => e.src)")
            for url in _filter_photo_srcs(srcs):
                base = url.split("?")[0]
                if base not in seen:
                    seen.add(base)
                    image_urls.append(url)
            count = len(image_urls)
            if count >= max_photos:
                break
            if count > 0 and count == prev_count:
                stable_passes += 1
                if stable_passes >= 2:
                    break
            else:
                stable_passes = 0
            prev_count = count
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.4)

        try:
            close_btn = await page.query_selector("button[aria-label='Close']")
            if close_btn:
                await close_btn.click()
        except Exception:
            pass

        return image_urls[:max_photos]
    except Exception:
        return []


async def get_listing_details_async(page, listing_url: str, harvest_photos: bool = True) -> dict:
    """
    Async version: Extract comprehensive details from a single Airbnb listing page.

    Args:
        page: Async Playwright page object with an active browser session
        listing_url: Full URL to the Airbnb listing page
        harvest_photos: When True, open the photo gallery and scroll it to collect
            all photo URLs (needed for vision reranking). When False, only collect
            photo URLs already present in the initial DOM (cover photo, etc.).

    Returns:
        Dictionary containing listing details
    """
    details = {
        "url": listing_url,
        "title": "",
        "description": "",
        "amenities": [],
        "house_rules": [],
        "host_info": "",
        "price": None,  # Per-night price in USD
        "rating": None,  # Host rating (1-5)
        "image_url": "",
        "image_urls": [],
        "full_text": "",
    }

    # Airbnb sometimes serves an unhydrated shell page (bot heuristics): the DOM
    # loads but no listing content ever renders. Wait for real content (title or
    # listing photos) rather than a fixed sleep, and retry the page once.
    loaded = False
    for attempt in range(2):
        try:
            await page.goto(listing_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(
                "h1, img[src*='muscache.com/im/pictures/']", timeout=15000
            )
            loaded = True
            break
        except Exception:
            if attempt == 0:
                print("   ⚠️ Listing page rendered no content, retrying once...")
            else:
                print("   ⚠️ Navigation timeout, continuing anyway...")

    if not loaded:
        return details

    try:
        # Get title
        title_el = await page.query_selector("h1")
        if title_el:
            details["title"] = await title_el.inner_text()

        # One body-text snapshot feeds price, rating and the house-rules parsing
        # below — each inner_text() call is a full-DOM round trip to the browser.
        try:
            page_text = await page.inner_text("body")
        except Exception:
            page_text = ""

        # Extract nightly price (usually in header or booking panel)
        price_match = re.search(r"\$?([\d,]+)\s*(?:per night|\/night|night)", page_text, re.IGNORECASE)
        if price_match:
            try:
                details["price"] = int(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Extract host rating (usually "4.8" or "4.8 (123 reviews)")
        rating_match = re.search(r"(\d+\.\d+)\s*(?:\([\d,]+\s*reviews?\))?", page_text)
        if rating_match:
            try:
                details["rating"] = float(rating_match.group(1))
            except ValueError:
                pass

        # Photo URLs (only the URLs are used downstream — the vision rerank
        # downloads the bytes itself, and image responses are blocked anyway).
        try:
            if harvest_photos:
                image_urls = await _harvest_gallery_photos(page)
            else:
                srcs = await page.eval_on_selector_all("img", "els => els.map(e => e.src)")
                image_urls = _filter_photo_srcs(srcs)
            details["image_urls"] = image_urls
            details["image_url"] = image_urls[0] if image_urls else ""
        except Exception:
            pass  # Image extraction is optional

        # Try to click "Show all amenities" button
        try:
            amenities_btn = await page.query_selector("button:has-text('Show all')")
            if amenities_btn:
                btn_text = await amenities_btn.inner_text()
                if "amenities" in btn_text.lower():
                    await amenities_btn.click()
                    try:
                        await page.wait_for_selector("[data-testid='amenity-row']", timeout=3000)
                    except Exception:
                        pass
                    amenity_els = await page.query_selector_all("[data-testid='amenity-row']")
                    for el in amenity_els:
                        details["amenities"].append(await el.inner_text())
                    close_btn = await page.query_selector("button[aria-label='Close']")
                    if close_btn:
                        await close_btn.click()
        except Exception:
            pass

        # Extract house rules from the listing page
        try:
            house_rules_list = []
            try:
                show_rules_btn = await page.query_selector("button:has-text('Show')")
                if show_rules_btn and "rules" in page_text.lower():
                    parent = await show_rules_btn.evaluate_handle("el => el.closest('div')")
                    parent_text = await parent.evaluate("el => el.innerText.toLowerCase()")
                    if "house rules" in parent_text or "rules" in parent_text:
                        await show_rules_btn.click()
                        try:
                            await page.wait_for_selector("[data-testid='rule-item']", timeout=2000)
                        except Exception:
                            pass
            except Exception:
                pass

            rule_els = await page.query_selector_all("[data-testid='rule-item'], li:has-text('rule')")
            if rule_els:
                for el in rule_els:
                    rule_text = await el.inner_text()
                    rule_text = rule_text.strip()
                    if rule_text:
                        house_rules_list.append(rule_text)

            if not house_rules_list:
                if "house rules" in page_text.lower():
                    match = re.search(r"house\s*rules[\s\S]*?(?=\n\n|[A-Z][a-z]+\s*rules|$)", page_text, re.IGNORECASE)
                    if match:
                        rules_section = match.group(0)
                        rules = re.split(r"\n(?=\d+\.)", rules_section)
                        for rule in rules:
                            rule_text = rule.strip()
                            if rule_text and not rule_text.lower().startswith("house rules"):
                                house_rules_list.append(rule_text)

            details["house_rules"] = house_rules_list
        except Exception:
            pass

        # Get full page text for keyword matching
        details["full_text"] = await page.inner_text("body")

    except Exception as e:
        print(f"Error scraping {listing_url}: {e}")

    return details


def filter_by_keywords(listings_data: list, keywords: list, match_all: bool = False) -> list:
    """Filter listings by keywords found in description/amenities."""
    matched = []

    for listing in listings_data:
        full_text = listing.get("full_text", "").lower()
        amenities_text = " ".join(listing.get("amenities", [])).lower()
        search_text = full_text + " " + amenities_text

        keywords_lower = [k.lower() for k in keywords]

        if match_all:
            if all(kw in search_text for kw in keywords_lower):
                listing["matched_keywords"] = keywords
                matched.append(listing)
        else:
            found = [kw for kw in keywords_lower if kw in search_text]
            if found:
                listing["matched_keywords"] = found
                matched.append(listing)

    return matched


async def scrape_listings_concurrent(
    context,
    listing_urls: list,
    max_price: int = None,
    progress: ProgressCallback | None = None,
    harvest_photos: bool = True,
    http_client: "httpx.AsyncClient | None" = None,
) -> list:
    """
    Scrape listing details concurrently.

    Uses the plain-HTTP embedded-JSON fast path first; only listings that fail
    it (bot challenge, layout change) fall back to a Playwright browser page.

    Args:
        context: Async Playwright browser context (fallback path)
        listing_urls: List of listing URLs to scrape
        max_price: Optional price filter to skip expensive listings
        harvest_photos: When True, keep the full photo set from the listing
            (only needed when vision reranking will run)
        http_client: Shared httpx client for the fast path; one is created
            internally when not provided

    Returns:
        List of listing detail dictionaries
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LISTINGS)
    completed = 0
    completed_lock = asyncio.Lock()
    owns_client = http_client is None
    if owns_client:
        http_client = httpx.AsyncClient(
            headers={"User-Agent": _HTTP_UA, "Accept-Language": "en-US,en;q=0.9"},
        )

    async def scrape_with_semaphore(url, index):
        """Wrap scraping with semaphore to limit concurrency."""
        nonlocal completed
        async with semaphore:
            try:
                print(f"   Scraping listing {index + 1}/{len(listing_urls)}...")

                # Fast path: plain HTTP + embedded JSON. No browser involved.
                details = await get_listing_details_http(
                    http_client, url, harvest_photos=harvest_photos
                )

                # Fallback: drive a browser page for this listing only.
                if details is None:
                    page = await context.new_page()
                    try:
                        details = await get_listing_details_async(
                            page, url, harvest_photos=harvest_photos
                        )
                    finally:
                        await page.close()

                # Filter by max_price (post-check in case Airbnb didn't filter server-side)
                if max_price and details.get("price") and details["price"] > max_price:
                    print(f"      ⏭️ Skipped (${details['price']}/night > ${max_price} limit)")
                    return None

                return details
            except Exception as e:
                print(f"   ⚠️ Error scraping listing {index + 1}: {e}")
                return None
            finally:
                if progress:
                    async with completed_lock:
                        completed += 1
                        await progress(f"Scraping listing {completed}/{len(listing_urls)}")

    try:
        tasks = [scrape_with_semaphore(url, i) for i, url in enumerate(listing_urls)]
        results = await asyncio.gather(*tasks)
    finally:
        if owns_client:
            await http_client.aclose()

    return [r for r in results if r is not None]


# ============================================================================
# TOOL OUTPUT MODELS
# ============================================================================


class AirbnbListing(BaseModel):
    """A single Airbnb listing that matched the search filters."""

    title: str = Field(default="", description="Listing title")
    url: str = Field(default="", description="Link to the Airbnb listing")
    city: str = Field(default="", description="City / location searched for")
    price: Optional[int] = Field(default=None, description="Nightly price in USD")
    rating: Optional[float] = Field(default=None, description="Host rating (1-5)")
    amenities: list[str] = Field(default_factory=list, description="Amenities found on the listing")
    house_rules: list[str] = Field(default_factory=list, description="House rules for the listing")
    description: str = Field(default="", description="Listing description")
    image_url: str = Field(default="", description="Cover photo URL")
    image_urls: list[str] = Field(default_factory=list, description="All listing photo URLs")
    full_text: str = Field(default="", description="Full listing page text (used for keyword/embedding search)")
    matched_keywords: list[str] = Field(default_factory=list, description="Keywords matched by custom keyword search")


class AirbnbSearchResponse(BaseModel):
    """Result of an Airbnb search."""

    location: str = Field(description="Location that was searched")
    checkin: str = Field(description="Check-in date (YYYY-MM-DD)")
    checkout: str = Field(description="Check-out date (YYYY-MM-DD)")
    nights: int = Field(description="Number of nights")
    total: int = Field(description="Total number of matching listings")
    listings: list[AirbnbListing] = Field(default_factory=list, description="Matching Airbnb listings")


class AirbnbFilters(BaseModel):
    """Structured Airbnb search parameters.

    These values are known precisely by the app (e.g. from a search form), so they
    are passed to the agent as dependency injection (`deps`) and read directly by
    the tool via RunContext — the model never sees or parses them from text.
    """

    location: Optional[str] = Field(default=None, description="Location to search (e.g., 'Lima, Peru')")
    checkin: Optional[str] = Field(default=None, description="Check-in date (YYYY-MM-DD)")
    nights: Optional[int] = Field(default=None, ge=1, description="Number of nights; checkout = checkin + nights")
    checkout: Optional[str] = Field(default=None, description="Optional explicit check-out date (YYYY-MM-DD)")
    keywords: Optional[list[str]] = Field(
        default=None,
        description=(
            "Free-text keywords matched against listing page text "
            "(for features not available as Airbnb amenities, e.g. balcony, sauna)"
        ),
    )
    match_all_keywords: bool = Field(default=False, description="Match ALL keywords (default: match ANY)")
    amenities: Optional[list[str]] = Field(
        default=None,
        description="Airbnb amenity names from the known set (e.g. pool, gym, wifi, workspace)",
    )
    min_price: Optional[int] = Field(default=None, ge=0, description="Minimum price per night in USD")
    max_price: Optional[int] = Field(default=None, ge=0, description="Maximum price per night in USD")
    guests: int = Field(default=1, ge=1, le=16, description="Number of guests")
    room_type: RoomTypeName = Field(default="apartment", description="Room type")
    superhost: bool = Field(default=False, description="Only Superhost listings")
    instant_book: bool = Field(default=False, description="Only Instant Book listings")
    self_checkin: bool = Field(default=False, description="Only self check-in listings")
    min_bedrooms: Optional[int] = Field(default=None, ge=1, description="Minimum bedrooms")
    min_beds: Optional[int] = Field(default=None, ge=1, description="Minimum beds")
    min_bathrooms: Optional[int] = Field(default=None, ge=1, description="Minimum bathrooms")
    max_listings: int = Field(
        default_factory=lambda: DEFAULT_MAX_LISTINGS,
        ge=1,
        description="Max listings to scrape",
    )
    max_pages: int = Field(default=5, ge=1, description="Max search result pages to walk")
    use_vision: bool = Field(default=False, description="Rerank results by analyzing listing photos with Gemini Vision")
    top_k: int = Field(
        default_factory=lambda: DEFAULT_TOP_K,
        ge=1,
        description="Number of ranked results to return to the UI",
    )
    _progress: ProgressCallback | None = PrivateAttr(default=None)
    _query_image: bytes | None = PrivateAttr(default=None)
    _query_image_media_type: str | None = PrivateAttr(default=None)
    _listing_results: list[dict] = PrivateAttr(default_factory=list)

    @field_validator("checkin", "checkout", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        if v is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("max_price", mode="after")
    @classmethod
    def validate_prices(cls, v, info):
        min_price = info.data.get("min_price")
        if v is not None and min_price is not None and v < min_price:
            raise ValueError("max_price must be >= min_price")
        return v

    def has_required(self) -> bool:
        return bool(self.location and self.checkin and self.nights)

    async def report_progress(self, message: str) -> None:
        """Send a transient processing update when this request supports it."""
        if self._progress:
            await self._progress(message)


class FilterUpdate(BaseModel):
    """Partial search-form update extracted from conversation.

    Only include fields the user actually mentioned. Omitted fields are left unchanged.
    """

    location: Optional[str] = Field(default=None, description="Location to search (e.g., 'Lima, Peru')")
    checkin: Optional[str] = Field(default=None, description="Check-in date (YYYY-MM-DD)")
    nights: Optional[int] = Field(default=None, ge=1, description="Number of nights")
    checkout: Optional[str] = Field(default=None, description="Check-out date (YYYY-MM-DD)")
    keywords: Optional[list[str]] = Field(
        default=None,
        description=(
            "Free-text keywords to add for features NOT in the amenities list. "
            "Use this for anything Airbnb cannot filter structurally "
            "(e.g. balcony, patio, sauna, ping pong, rooftop, ocean view). "
            "Matched against listing page text after the amenity filter runs."
        ),
    )
    match_all_keywords: Optional[bool] = Field(default=None, description="Match ALL keywords instead of ANY")
    amenities: Optional[list[str]] = Field(
        default=None,
        description=(
            "Airbnb amenity names to add — ONLY values from this list: "
            "wifi, kitchen, washer, dryer, air_conditioning, heating, pool, hot_tub, "
            "gym, free_parking, ev_charger, crib, bbq_grill, breakfast, fireplace, "
            "workspace, tv, pets_allowed, smoking_allowed, wheelchair_accessible, "
            "elevator, beach_access, waterfront, self_checkin. "
            "If the user asks for something not on this list (e.g. balcony), put it in keywords instead."
        ),
    )
    min_price: Optional[int] = Field(default=None, ge=0, description="Minimum price per night in USD")
    max_price: Optional[int] = Field(default=None, ge=0, description="Maximum price per night in USD")
    guests: Optional[int] = Field(default=None, ge=1, le=16, description="Number of guests")
    room_type: Optional[RoomTypeName] = Field(default=None, description="Room type")
    superhost: Optional[bool] = Field(default=None, description="Only Superhost listings")
    instant_book: Optional[bool] = Field(default=None, description="Only Instant Book listings")
    self_checkin: Optional[bool] = Field(default=None, description="Only self check-in listings")
    min_bedrooms: Optional[int] = Field(default=None, ge=1, description="Minimum bedrooms")
    min_beds: Optional[int] = Field(default=None, ge=1, description="Minimum beds")
    min_bathrooms: Optional[int] = Field(default=None, ge=1, description="Minimum bathrooms")
    use_vision: Optional[bool] = Field(default=None, description="Rerank results with listing photos")

    @field_validator("checkin", "checkout", mode="before")
    @classmethod
    def validate_date_format(cls, v):
        if v is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v)):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v


_LIST_FIELDS = frozenset({"keywords", "amenities"})


_FORM_KEYS = frozenset({
    "location",
    "checkin",
    "nights",
    "checkout",
    "keywords",
    "match_all_keywords",
    "amenities",
    "min_price",
    "max_price",
    "guests",
    "room_type",
    "superhost",
    "instant_book",
    "self_checkin",
    "min_bedrooms",
    "min_beds",
    "min_bathrooms",
    "use_vision",
})


def form_snapshot(filters: AirbnbFilters) -> dict:
    """JSON-safe form fields to send back to the UI."""
    data = filters.model_dump(mode="json", exclude_none=True)
    return {key: value for key, value in data.items() if key in _FORM_KEYS}


def apply_filter_update(current: AirbnbFilters, update: FilterUpdate) -> AirbnbFilters:
    """Merge conversationally extracted fields into the current search-form deps."""
    data = current.model_dump()
    patch = update.model_dump(exclude_none=True)
    for key, value in patch.items():
        if key in _LIST_FIELDS and isinstance(value, list):
            existing = data.get(key) or []
            data[key] = list(dict.fromkeys([*existing, *value]))
        else:
            data[key] = value
    return AirbnbFilters.model_validate(data)


def update_search_filters(ctx: RunContext[AirbnbFilters], filters: FilterUpdate) -> AirbnbFilters:
    """Update the search form from criteria the user mentioned in conversation.

    Call this whenever the user states or changes location, dates, budget, guests,
    room type, amenities, keywords, or other filters in chat — even if you will
    search immediately afterwards. Only include fields they actually mentioned.
    Amenities and keywords are added to any values already on the form.

    Route features carefully:
    - amenities: only known Airbnb amenity names from the amenities field description
    - keywords: any other desired feature (balcony, patio, sauna, ocean view, etc.)
    """
    updated = apply_filter_update(ctx.deps, filters)
    for field_name, value in updated.model_dump().items():
        setattr(ctx.deps, field_name, value)
    return ctx.deps


# ============================================================================
# MAIN TOOL
# ============================================================================


async def run_search(
    params: AirbnbFilters,
    progress: ProgressCallback | None = None,
    harvest_photos: bool | None = None,
) -> AirbnbSearchResponse:
    """Execute an Airbnb search from structured parameters.

    harvest_photos controls whether each listing's photo gallery is scraped for
    the full photo set. Defaults to True only when the photos will actually be
    used (vision reranking enabled or a reference image attached).
    """
    if progress:
        await progress("Performing filter search")
    location = params.location
    checkin = params.checkin
    nights = params.nights
    checkout = params.checkout
    keywords = params.keywords
    match_all_keywords = params.match_all_keywords
    amenities = params.amenities
    max_price = params.max_price
    min_price = params.min_price
    guests = params.guests
    room_type = params.room_type
    superhost = params.superhost
    instant_book = params.instant_book
    self_checkin = params.self_checkin
    min_bedrooms = params.min_bedrooms
    min_beds = params.min_beds
    min_bathrooms = params.min_bathrooms
    max_listings = params.max_listings
    max_pages = params.max_pages

    if not location:
        raise ValueError("location is required")
    if not checkin:
        raise ValueError("checkin is required (YYYY-MM-DD)")
    if not nights or nights < 1:
        raise ValueError("nights must be at least 1")

    try:
        checkin_dt = datetime.strptime(checkin, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"checkin must be YYYY-MM-DD, got '{checkin}'")

    if checkout is None:
        checkout = (checkin_dt + timedelta(days=nights)).strftime("%Y-%m-%d")

    amenity_ids = resolve_amenity_ids(amenities)

    search_url = build_search_url(
        location=location,
        checkin=checkin,
        checkout=checkout,
        guests=guests,
        min_price=min_price,
        max_price=max_price,
        amenities=amenity_ids,
        room_type=room_type,
        superhost=superhost,
        instant_book=instant_book,
        self_checkin=self_checkin,
        min_bedrooms=min_bedrooms,
        min_beds=min_beds,
        min_bathrooms=min_bathrooms,
    )

    if harvest_photos is None:
        harvest_photos = bool(params.use_vision or params._query_image)

    print(f"🔍 Searching: {search_url}")
    if keywords:
        print(f"📝 Custom Keywords: {keywords}")

    # Reuse one browser/context for discovery and detail scraping. Starting a
    # second browser is expensive and discards the warmed session.
    # The browser is still needed to walk search results (infinite scroll), but
    # listing detail pages go over plain HTTP, with browser pages as fallback.
    http_client = httpx.AsyncClient(
        headers={"User-Agent": _HTTP_UA, "Accept-Language": "en-US,en;q=0.9"},
    )
    try:
        async with async_playwright() as p:
            browser, context = await create_stealth_browser_async(p)
            page = await context.new_page()
            print("📄 Getting search results...")
            listing_urls = await get_listing_urls_async(page, search_url, max_listings, max_pages)
            await page.close()
            print(f"   Total: {len(listing_urls)} listings found")
            if listing_urls:
                print("🔍 Scraping listing details (concurrent)...")
                listings_data = await scrape_listings_concurrent(
                    context,
                    listing_urls,
                    max_price,
                    progress,
                    harvest_photos=harvest_photos,
                    http_client=http_client,
                )
            else:
                listings_data = []
            await browser.close()
    finally:
        await http_client.aclose()

    if not listing_urls:
        return AirbnbSearchResponse(
            location=location,
            checkin=checkin,
            checkout=checkout,
            nights=nights,
            total=0,
            listings=[],
        )

    # Step 3: filter by custom keywords
    if keywords:
        if progress:
            await progress("Filtering listings")
        print("🔎 Filtering by custom keywords...")
        listings_data = filter_by_keywords(listings_data, keywords, match_all_keywords)
        print(f"✅ Found {len(listings_data)} matching listings")
    else:
        print(f"✅ Found {len(listings_data)} listings")

    # Step 4: volume-based default filtering
    if len(listings_data) > LISTINGS_THRESHOLD:
        print(f"\n⚙️  APPLYING SMART DEFAULTS ({len(listings_data)} > {LISTINGS_THRESHOLD} threshold)")
        print(f"   ⭐ Requiring minimum rating > {DEFAULT_MIN_RATING}")
        filtered = []
        for listing in listings_data:
            rating = listing.get("rating")
            if rating and rating < DEFAULT_MIN_RATING:
                continue
            filtered.append(listing)
        listings_data = filtered
        print(f"   ✅ Reduced to {len(listings_data)} listings after applying defaults")

    listings = [
        AirbnbListing(
            title=listing.get("title", ""),
            url=listing.get("url", ""),
            city=params.location,
            price=listing.get("price"),
            rating=listing.get("rating"),
            amenities=listing.get("amenities", []),
            house_rules=listing.get("house_rules", []),
            description=listing.get("description", ""),
            image_url=listing.get("image_url", ""),
            image_urls=listing.get("image_urls", []),
            full_text=listing.get("full_text", ""),
            matched_keywords=listing.get("matched_keywords", []),
        )
        for listing in listings_data
    ]

    return AirbnbSearchResponse(
        location=location,
        checkin=checkin,
        checkout=checkout,
        nights=nights,
        total=len(listings),
        listings=listings,
    )


def format_listings_for_chat(
    response: AirbnbSearchResponse, top_k: int = DEFAULT_TOP_K
) -> str:
    """Format search results as markdown suitable for pasting into chat."""
    if not response.listings:
        return (
            f"No listings found in {response.location} for {response.checkin} "
            f"({response.nights} nights). Try different dates, a higher budget, "
            "or fewer amenity/keyword constraints."
        )

    shown = response.listings[: max(1, top_k)]
    lines = [
        f"Found **{response.total}** listings in {response.location} "
        f"({response.checkin} → {response.checkout}, {response.nights} nights). "
        f"Showing top {len(shown)}:",
        "",
    ]
    for i, listing in enumerate(shown, 1):
        title = listing.title or "Untitled listing"
        lines.append(f"### {i}. [{title}]({listing.url})")
        meta: list[str] = []
        if listing.city:
            meta.append(listing.city)
        if listing.price is not None:
            meta.append(f"${listing.price:,}/night")
        if listing.rating is not None:
            meta.append(f"★ {listing.rating}")
        if meta:
            lines.append(" · ".join(meta))
        if listing.matched_keywords:
            lines.append(f"Matched: {', '.join(listing.matched_keywords)}")
        if listing.description:
            desc = listing.description.strip()
            if len(desc) > 220:
                desc = desc[:217].rstrip() + "…"
            lines.append(desc)
        elif listing.amenities:
            lines.append("Amenities: " + ", ".join(listing.amenities[:8]))
        lines.append("")
    return "\n".join(lines).rstrip()


async def search_airbnb(
    ctx: RunContext[AirbnbFilters],
    keywords: Optional[list[str]] = None,
    match_all_keywords: Optional[bool] = None,
) -> str:
    """
    Search Airbnb and make structured listings available to the chat UI.

    Location, dates, budget and the standard Airbnb filters come from the search
    configuration passed with the run, so they are never parsed from conversation.
    This tool only accepts free-text keywords the user mentioned in chat.

    Args:
        keywords: Optional free-text keywords that must appear in the listing page
            text or amenities (e.g. ["sauna", "ping pong"]).
        match_all_keywords: When True, a listing must contain ALL keywords to match.
            When False (default), a listing matches if it contains ANY keyword.

    Returns:
        A short summary. Structured listing data is sent separately to the UI.
    """
    params = ctx.deps.model_copy(deep=True)
    if keywords:
        seen = set(params.keywords or [])
        params.keywords = list(seen) + [k for k in keywords if k not in seen]
    if match_all_keywords is not None:
        params.match_all_keywords = match_all_keywords

    if not params.has_required():
        missing = [n for n in ("location", "checkin", "nights") if getattr(params, n) is None]
        raise ModelRetry(
            "Cannot search yet — missing " + ", ".join(missing) + ". "
            "Ask the user to provide their destination, check-in date and number of "
            "nights (or fill them in the search form) before calling this tool again."
        )

    response = await run_search(params, progress=ctx.deps.report_progress)
    shown = response.listings[: max(1, params.top_k)]
    ctx.deps._listing_results = [
        {
            "title": listing.title or "Untitled listing",
            "url": listing.url,
            "city": listing.city,
            "price": listing.price,
            "rating": listing.rating,
            "description": listing.description,
            "image_url": listing.image_url,
            "image_urls": listing.image_urls,
            "amenities": listing.amenities,
            "house_rules": listing.house_rules,
            "matched_keywords": listing.matched_keywords,
        }
        for listing in shown
    ]
    if not shown:
        return (
            f"No listings found in {response.location} for {response.checkin} "
            f"({response.nights} nights). Suggest adjusting the search criteria."
        )
    return (
        f"Found {response.total} listings in {response.location}. "
        f"The best {len(shown)} listings are available in the interactive results viewer."
    )


def search_airbnb_sync(params: AirbnbFilters) -> AirbnbSearchResponse:
    """Synchronous wrapper around run_search for non-async callers."""
    return asyncio.run(run_search(params))


# Ready-to-register Pydantic AI tool (can also pass search_airbnb directly to tools=[])
filter_listings_tool = Tool(search_airbnb)
update_search_filters_tool = Tool(update_search_filters)


def save_results(results: list, filename: str = "results.json"):
    """Save results to JSON file."""
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"💾 Saved to {filename}")


# ============================================================================
# CLI
# ============================================================================


def build_parser():
    """Build the CLI argument parser for the Airbnb search tool."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Airbnb Scraper - Search listings and filter by custom keywords/amenities.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("location", type=str, help="Location to search (e.g., 'Lima, Peru')")

    # Custom keyword search (searches listing page text)
    parser.add_argument(
        "--keywords", "-k", nargs="*", default=None,
        help="Custom keywords to search in listing text (e.g., --keywords sauna 'ping pong')",
    )
    parser.add_argument(
        "--match-all", action="store_true",
        help="Listing must contain ALL keywords (default: match ANY)",
    )

    # Date & guest filters
    parser.add_argument("--checkin", type=str, required=True, help="Check-in date (YYYY-MM-DD)")
    parser.add_argument("--nights", type=int, required=True, help="Number of nights (computes check-out date)")
    parser.add_argument("--checkout", type=str, default=None, help="Check-out date (YYYY-MM-DD); overrides --nights")
    parser.add_argument("--guests", type=int, default=1, help="Number of guests")

    # Pagination
    parser.add_argument(
        "--max-listings",
        type=int,
        default=DEFAULT_MAX_LISTINGS,
        help="Max listings to scrape",
    )
    parser.add_argument("--max-pages", type=int, default=5, help="Max search result pages to scrape")

    # Price filters
    parser.add_argument("--min-price", type=int, default=None, help="Minimum price per night")
    parser.add_argument("--max-price", type=int, default=None, help="Maximum price per night")

    # Built-in Airbnb filters
    parser.add_argument(
        "--amenities", "-a", nargs="*", default=None,
        help="Amenity names (e.g., -a pool gym). See --list-amenities",
    )
    parser.add_argument(
        "--room-type", type=str, default="apartment",
        choices=["apartment", "entire_home", "private_room", "shared_room", "hotel_room"],
        help="Room type",
    )
    parser.add_argument("--superhost", action="store_true", help="Only superhosts")
    parser.add_argument("--instant-book", action="store_true", help="Only instant book listings")
    parser.add_argument("--self-checkin", action="store_true", help="Only self check-in listings")
    parser.add_argument("--min-bedrooms", type=int, default=None, help="Minimum bedrooms")
    parser.add_argument("--min-beds", type=int, default=None, help="Minimum beds")
    parser.add_argument("--min-bathrooms", type=int, default=None, help="Minimum bathrooms")

    # Output
    parser.add_argument("--output", "-o", type=str, default="airbnb_results.json", help="Output JSON file")
    parser.add_argument("--list-amenities", action="store_true", help="Print available amenity names/IDs and exit")

    return parser


def main():
    import sys

    if "--list-amenities" in sys.argv:
        print("AVAILABLE BUILT-IN AMENITIES:")
        for name, id in sorted(AMENITIES.items()):
            print(f"  AMENITIES['{name}'] = {id.value}")
        return

    parser = build_parser()
    args = parser.parse_args()

    params = AirbnbFilters(
        location=args.location,
        checkin=args.checkin,
        nights=args.nights,
        checkout=args.checkout,
        keywords=args.keywords,
        match_all_keywords=args.match_all,
        amenities=args.amenities,
        min_price=args.min_price,
        max_price=args.max_price,
        guests=args.guests,
        room_type=args.room_type,
        superhost=args.superhost,
        instant_book=args.instant_book,
        self_checkin=args.self_checkin,
        min_bedrooms=args.min_bedrooms,
        min_beds=args.min_beds,
        min_bathrooms=args.min_bathrooms,
        max_listings=args.max_listings,
        max_pages=args.max_pages,
    )

    result = asyncio.run(run_search(params))

    print("\n" + "=" * 60)
    print("MATCHING LISTINGS:")
    print("=" * 60)

    for r in result.listings:
        print(f"\n📍 {r.title}")
        print(f"   🔗 {r.url}")
        if r.price:
            print(f"   💰 ${r.price}/night")
        if r.rating:
            print(f"   ⭐ {r.rating}")
        if r.matched_keywords:
            print(f"   ✨ Matched: {r.matched_keywords}")

    print(f"\nTotal: {result.total} listings")
    save_results(result.model_dump()["listings"], args.output)


if __name__ == "__main__":
    main()

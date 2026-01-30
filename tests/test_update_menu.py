from datetime import datetime

from scripts.update_menu import extract_menu_meta_from_images, validate_menu_map


def test_extract_menu_meta_from_images_uses_date_in_url():
    now = datetime(2026, 1, 15)
    image_urls = [
        "https://files.ecatholic.com/pictures/2021/7/combo_logo.png",
        "https://files.ecatholic.com/pictures/2026/1/menu.jpg",
    ]

    meta = extract_menu_meta_from_images(image_urls, now)

    assert meta["year"] == 2026
    assert meta["month_num"] == 1
    assert meta["month_name"] == "January"
    assert meta["image_url"].endswith("/2026/1/menu.jpg")


def test_extract_menu_meta_from_images_falls_back_to_current_month():
    now = datetime(2026, 5, 10)
    image_urls = [
        "https://files.ecatholic.com/pictures/misc/menu.jpg",
        "https://files.ecatholic.com/pictures/2021/7/logo.jpg",
    ]

    meta = extract_menu_meta_from_images(image_urls, now)

    assert meta["year"] == 2026
    assert meta["month_num"] == 5
    assert meta["month_name"] == "May"


def test_validate_menu_map_filters_invalid_entries():
    menu_map = {
        "2026-01-12": "Pizza",
        "2026-02-01": "Wrong month",
        "2026-01-XX": "Bad date",
    }

    validated = validate_menu_map(menu_map, "2026-01")

    assert validated == {"2026-01-12": "Pizza"}

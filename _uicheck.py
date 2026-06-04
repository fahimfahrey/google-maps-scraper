import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"], executable_path="/usr/bin/chromium-browser")
    pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto("http://localhost:8767/", wait_until="networkidle"); time.sleep(4)
    body = pg.inner_text("body")
    print("Apply btn:", "Apply" in body)
    print("Delete btn:", "Delete" in body)
    print("edit hint:", "Edit cells inline" in body)
    print("data_editor present:", pg.query_selector("[data-testid='stDataFrameResizable'], [data-testid='stDataEditor']") is not None)
    print("exception:", "Traceback" in body)
    # open delete popover, check options
    try:
        pg.get_by_text("Delete", exact=False).first.click(); time.sleep(1)
        b2 = pg.inner_text("body")
        print("danger zone:", "Danger zone" in b2, "| clear all:", "Clear ALL" in b2)
    except Exception as e:
        print("popover click err:", e)
    pg.screenshot(path="_ui2.png", full_page=True)
    b.close()

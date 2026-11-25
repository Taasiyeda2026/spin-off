"""Integration tests against a fresh local Supabase CLI stack with synthetic users.

Apply poster-supabase-fixture.sql and the feature migration first. Run only
against loopback. The helper creates fake users via the actual Auth admin API.
"""
import base64
import json
import os
import re
import subprocess
from tempfile import TemporaryDirectory
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

api = os.environ.get("POSTER_SUPABASE_URL", "http://127.0.0.1:54321")
site = os.environ.get("POSTER_TEST_URL", "http://127.0.0.1:8123/poster.html")
public_key = os.environ["POSTER_SUPABASE_PUBLIC_KEY"]
service_key = os.environ["POSTER_SUPABASE_SERVICE_KEY"]
assert all(urlsplit(url).hostname == "127.0.0.1" for url in (api, site)), "Local fixture only"
password = "Synthetic-Local-Only-4k7Q"
artifact_directory = os.environ.get("POSTER_TEST_ARTIFACTS")


def capture(page, name):
    if artifact_directory:
        output = Path(artifact_directory)
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=output / (name + ".png"), full_page=True)

png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFtUAAAAASUVORK5CYII=")


def request(path, data, key=public_key, token=None, prefer=None):
    headers = {"apikey": key, "Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if prefer:
        headers["Prefer"] = prefer
    req = Request(api + path, data=json.dumps(data).encode(), headers=headers)
    try:
        with urlopen(req, timeout=25) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except HTTPError as error:
        raise AssertionError(f"{path} returned HTTP {error.code}") from error


def seed():
    users = []
    for role, name, emp_id in (
        ("instructor", "teacher-a", 101), ("instructor", "teacher-b", 102),
        ("activities_manager", "manager-a", None), ("activities_manager", "manager-b", None),
        ("admin", "admin", None),
    ):
        email = name + "@poster-fixture.example"
        user = request("/auth/v1/admin/users", {"email": email, "password": password, "email_confirm": True},
                       service_key, service_key)
        users.append(dict(user_id=name, auth_user_id=user["id"], emp_id=emp_id,
                          role=role, username=name, full_name=name, auth_email=email))
    for table, rows in (
        ("users", users),
        ("activities", [dict(row_id="space-" + letter, emp_id=employee, school="School " + letter.upper(),
                             grade="4", class_group="4" + letter.upper(), gefen_number="57651",
                             activity_manager="manager-" + letter)
                        for letter, employee in (("a", 101), ("b", 102))]),
        ("contacts_instructors", [dict(emp_id=101, direct_manager="manager-a", active="yes"),
                                  dict(emp_id=102, direct_manager="manager-b", active="yes")]),
    ):
        request("/rest/v1/" + table, rows, service_key, service_key, "return=minimal")


def page_for(browser):
    context = browser.new_context()
    context.add_init_script("window.posterCloudConfig = " + json.dumps({"url": api, "publishableKey": public_key}))
    context.route("**/*", lambda route: route.continue_()
                  if urlsplit(route.request.url).hostname == "127.0.0.1" or route.request.url.startswith("data:")
                  else route.abort())
    page = context.new_page()
    page.goto(site)
    return page


def click(page, label):
    page.get_by_role("button", name=label, exact=True).click()


def staff(browser, name):
    page = page_for(browser)
    click(page, "כניסת מדריכים")
    page.get_by_label("שם משתמש").fill(name)
    page.get_by_label("סיסמה").fill(password)
    click(page, "כניסה")
    expect(page.get_by_role("heading", name="ניהול הפוסטרים שלי")).to_be_visible()
    return page


def create(browser, teacher_code, label):
    page = page_for(browser)
    click(page, "יצירת פוסטר חדש")
    page.get_by_label("קוד מדריך").fill(teacher_code)
    click(page, "המשך")
    page.get_by_label("שמות חברי הקבוצה, מופרדים בפסיקים").fill("Synthetic A, Synthetic B")
    click(page, "יצירת פוסטר")
    group_code = page.get_by_text(re.compile(r"קוד הפוסטר: [1-9][0-9]{5}")).inner_text().split()[-1]
    page.locator("#poster-project").fill(label)
    expect(page.get_by_text("נשמר", exact=True)).to_be_visible()
    return page, group_code


def resume(browser, code):
    page = page_for(browser)
    click(page, "המשך עבודה על פוסטר")
    page.get_by_label("קוד הפוסטר").fill(code)
    click(page, "המשך")
    expect(page.locator("#poster-project")).to_be_visible()
    return page


def search(page, title):
    page.get_by_role("searchbox").fill(title)


if os.environ.get("POSTER_SUPABASE_USE_EXISTING_FIXTURE") != "1":
    seed()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"))
    teacher_a = staff(browser, "teacher-a")
    teacher_code_a = teacher_a.get_by_text(re.compile(r"קוד מדריך: [0-9]{4}")).inner_text().split()[-1]
    teacher_b = staff(browser, "teacher-b")
    teacher_code_b = teacher_b.get_by_text(re.compile(r"קוד מדריך: [0-9]{4}")).inner_text().split()[-1]
    assert teacher_code_a != teacher_code_b
    first, code_a = create(browser, teacher_code_a, "Synthetic project A")
    _, code_b = create(browser, teacher_code_b, "Synthetic project B")
    assert code_a != code_b

    with first.expect_response(
        lambda response: response.url.endswith("/rpc/spacetech_poster")
        and response.request.post_data_json.get("p_action") == "save"
    ) as saved_photo:
        first.locator("#img-main-file").set_input_files({"name": "fixture.png", "mimeType": "image/png", "buffer": png})
    assert "revision" in saved_photo.value.json()
    expect(first.get_by_text("נשמר", exact=True)).to_be_visible(timeout=25000)
    fresh = resume(browser, code_a)
    expect(fresh.locator("#poster-project")).to_have_value("Synthetic project A")
    expect(fresh.locator("#img-main")).to_be_visible()
    capture(fresh, "student")
    with TemporaryDirectory() as output:
        pdf = output + "/poster.pdf"
        fresh.pdf(path=pdf, prefer_css_page_size=True)
        assert re.search(r"^Pages:\s+1$", subprocess.check_output(["pdfinfo", pdf], text=True), re.MULTILINE)

    fresh.context.set_offline(True)
    fresh.locator("#problem").fill("Synthetic offline answer")
    expect(fresh.get_by_role("button", name="ניסיון שמירה מחדש")).to_be_visible()
    fresh.context.set_offline(False)
    expect(fresh.get_by_text("נשמר", exact=True)).to_be_visible()
    expect(resume(browser, code_a).locator("#problem")).to_have_value("Synthetic offline answer")

    for name, allowed, denied in (("teacher-a", "A", "B"), ("teacher-b", "B", "A"),
                                  ("manager-a", "A", "B"), ("manager-b", "B", "A")):
        page = staff(browser, name)
        search(page, "Synthetic project " + denied)
        expect(page.get_by_role("heading", name="Synthetic project " + denied)).to_have_count(0)
        search(page, "Synthetic project " + allowed)
        expect(page.get_by_role("heading", name="Synthetic project " + allowed)).to_be_visible()
        if name in ("teacher-a", "manager-a"):
            capture(page, name)
    admin = staff(browser, "admin")
    search(admin, "Synthetic project")
    for letter in "AB":
        expect(admin.get_by_role("heading", name="Synthetic project " + letter)).to_be_visible()

    capture(admin, "admin")
    manager = staff(browser, "manager-a")
    search(manager, "Synthetic project A")
    click(manager, "עריכה")
    manager.locator("#poster-project").fill("Manager edit")
    expect(manager.get_by_text("נשמר", exact=True)).to_be_visible()
    fresh.locator("#poster-project").fill("Stale edit")
    expect(fresh.get_by_role("button", name="פתיחת גרסת הענן")).to_be_visible()
    expect(resume(browser, code_a).locator("#poster-project")).to_have_value("Manager edit")

    first_session = uuid4().hex + uuid4().hex
    lookup = lambda code, session: request("/rest/v1/rpc/spacetech_poster", {
        "p_action": "resume", "p": {"code": code, "session": session}})
    lookup(code_a, first_session)
    other = lookup(code_b, uuid4().hex + uuid4().hex)
    forbidden = request("/rest/v1/rpc/spacetech_poster", {
        "p_action": "load", "p": {"id": other["id"], "session": first_session}})
    assert forbidden == {"error": "denied"}

    def concurrent_lookup(index):
        return request("/rest/v1/rpc/spacetech_poster", {"p_action": "activities", "p": {
            "code": (teacher_code_a, teacher_code_b)[index % 2], "ticket": uuid4().hex + uuid4().hex,
        }})

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert all("activities" in result for result in pool.map(concurrent_lookup, range(90)))

    ticket = uuid4().hex + uuid4().hex
    request("/rest/v1/rpc/spacetech_poster", {"p_action": "activities", "p": {
        "code": teacher_code_a, "ticket": ticket,
    }})
    params = {"activityId": "space-a", "participants": ["Synthetic retry"], "ticket": ticket,
              "requestId": str(uuid4()), "session": uuid4().hex + uuid4().hex}
    with ThreadPoolExecutor(max_workers=2) as pool:
        duplicates = list(pool.map(lambda _: request("/rest/v1/rpc/spacetech_poster", {
            "p_action": "create", "p": params,
        }), range(2)))
    assert duplicates[0]["id"] == duplicates[1]["id"]
    print("PASS: real Supabase Auth, PostgREST, Storage and Edge; roles, isolation, two browsers, conflicts and 90 lookups")

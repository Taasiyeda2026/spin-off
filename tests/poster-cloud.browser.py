"""Browser acceptance against a synthetic HTTP fixture. No real Supabase calls."""
import base64
import json
import hashlib
from pathlib import Path
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

url = os.environ.get("POSTER_TEST_URL", "http://127.0.0.1:8000/poster.html")
origin = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
poster_id = "230a7470-7352-467a-94e9-57f1ef0cec50"
activity = {"id": "activity-a", "school": "Fixture School", "grade": "4", "classGroup": "4A"}
poster = {
    "id": poster_id, "activityId": activity["id"], "code": "222222",
    "updatedAt": "2026-11-25T00:00:00Z", "revision": 0,
    "state": {"values": {"poster-school": "Fixture School", "poster-class": "4A",
                        "poster-students": ""},
              "participants": []},
}
png = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFtUAAAAASUVORK5CYII="
)
images = {}
errors = []
fail_save = False
conflict = False


def handle(route):
    global conflict
    request = route.request
    path = urlsplit(request.url).path
    if not request.url.startswith(origin + "/"):
        route.abort()
    elif path == "/auth/v1/user":
        if request.headers.get("authorization") == "Bearer invalid-token":
            route.fulfill(status=401, json={})
        else:
            route.fulfill(json={"id":"fixture"})
    elif path == "/rest/v1/rpc/get_current_app_user":
        role = "activities_manager" if request.headers.get("authorization") == "Bearer manager-token" else "instructor"
        route.fulfill(json=[{"auth_user_id":"fixture","is_active":True,"role":role}])
    elif path == "/rest/v1/rpc/spacetech_school_logo":
        route.fulfill(json={"schools":[]})
    elif path == "/functions/v1/poster-media":
        image_key = urlsplit(request.url).query
        if request.method == "PUT":
            images[image_key] = request.post_data_buffer
            route.fulfill(status=204)
        else:
            route.fulfill(body=images[image_key], content_type="image/png")
    elif path == "/rest/v1/rpc/spacetech_poster":
        call = request.post_data_json
        action, params = call["p_action"], call["p"]
        if action == "activities":
            assert params["code"] == "1234"
            result = {"activities": [activity]}
        elif action == "create":
            assert params["activityId"] == activity["id"] and len(params["session"]) == 64
            assert params["participants"] == []
            result = poster
        elif action in ("resume", "load"):
            if action == "resume":
                assert params["code"] == poster["code"] and len(params["session"]) == 64
            result = poster
        elif action == "save":
            if fail_save:
                route.fulfill(status=503)
                return
            if conflict:
                poster["revision"] += 1
                poster["state"]["values"]["poster-project"] = "Remote update"
                conflict = False
                route.fulfill(json={"error": "conflict"})
                return
            assert "data:image/" not in json.dumps(params["state"])
            assert params["revision"] == poster["revision"]
            poster["revision"] += 1
            poster["state"] = params["state"]
            result = poster
        elif action == "manage":
            bearer = request.headers["authorization"]
            assert bearer in ("Bearer fixture-token", "Bearer manager-token")
            manager = bearer == "Bearer manager-token"
            result = {"name": "Fixture Manager" if manager else "Fixture Instructor",
                      "code": None if manager else "1234", "activities": [
                {**activity, "posters": [{**poster, "title": poster["state"]["values"]["poster-project"],
                                        "participants": "Student A, Student B"}]}
            ]}
        else:
            raise AssertionError(action)
        route.fulfill(json=result)
    else:
        route.continue_()


def dashboard_sso(page, token):
    # Simulate only the trusted popup handoff; no real credentials or network login.
    page.evaluate("""token => {
      window.open = (url) => {
        const popup = {closed:false, close(){this.closed=true;}};
        const state = new URL(url).searchParams.get('state');
        setTimeout(() => {
          const event = new Event('message');
          Object.defineProperties(event, {origin:{value:'https://taasiyeda2026.github.io'},source:{value:popup},data:{value:{type:'spin-off:session',state,access_token:token}}});
          window.dispatchEvent(event);
        }, 10);
        return popup;
      };
    }""", token)
    page.get_by_role('button',name='התחברות דרך הדשבורד',exact=True).click()

def new_context(browser):
    context = browser.new_context()
    context.add_init_script(f"window.posterCloudConfig = {{ url: {json.dumps(origin)}, publishableKey: 'fixture-public' }};")
    context.route("**/*", handle)
    return context


def open_page(context):
    page = context.new_page()
    page.on("pageerror", lambda error: (errors.append(str(error)),print("PAGE ERROR:",str(error),flush=True)))
    page.on("console", lambda message: print("Browser error:", message.text, flush=True) if message.type == "error" else None)
    page.goto(url)
    return page


def click(page, name):
    page.get_by_role("button", name=name, exact=True).click()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"))
    student = open_page(new_context(browser))
    click(student, "יצירת פוסטר חדש")
    student.get_by_label("קוד מדריך").fill("1234")
    click(student, "המשך")
    expect(student.get_by_label("בית הספר והכיתה")).to_have_value(activity["id"])
    expect(student.get_by_label("שמות חברי הקבוצה, מופרדים בפסיקים")).to_have_count(0)
    click(student, "יצירת פוסטר")
    expect(student.get_by_text("קוד הפוסטר: 222222")).to_be_visible()
    expect(student.locator("#poster-school")).to_have_value("Fixture School")
    expect(student.locator("#poster-school")).to_have_js_property("readOnly", False)
    expect(student.locator("#tab-students")).to_be_visible()
    expect(student.locator("#poster-students")).to_have_value("")
    student.locator("#pc-cnt").select_option("2")
    student.locator("#pcf input").nth(0).fill("Student A")
    student.locator("#pcf input").nth(1).fill("Student B")
    expect(student.locator("#poster-students")).to_have_value("Student A, Student B")
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()
    assert poster["state"]["participants"] == ["Student A", "Student B"]
    student.locator('[data-tab="design"]').click()
    text_colors={'project-color':'#112233','description-color':'#223344','q-color':'#334455','t-color':'#445566'}
    for id,color in text_colors.items(): student.locator('#'+id+'-hex').fill(color)
    student.locator('[data-tab="content"]').click()
    student.locator("#panel-poster-project").fill("Language switch fixture")
    student.evaluate("window.__editorLanguageMarker = true")
    student.locator("#poster-editor-language").click()
    expect(student.locator("#tab-content .edit-card").first.locator("label")).to_have_text("1. اسم حلّنا؟")
    expect(student.locator("#panel-poster-project")).to_have_value("Language switch fixture")
    expect(student.locator("#poster-project")).to_have_value("Language switch fixture")
    expect(student.locator("#poster-students")).to_have_value("Student A, Student B")
    assert student.evaluate("window.__editorLanguageMarker === true")
    assert student.locator("#fill-list .edit-card > input, #fill-list .edit-card > textarea").evaluate_all(
        "(fields) => Math.max(...fields.map(f=>f.offsetWidth))-Math.min(...fields.map(f=>f.offsetWidth)) <= 1 && fields.every(f=>getComputedStyle(f).textAlign==='right')")
    student.locator("#poster-editor-language").click()
    expect(student.locator("#tab-content .edit-card").first.locator("label")).to_have_text("1. שם הפתרון שלנו?")
    student.locator("#panel-poster-project").fill("")
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()
    student.locator('[data-tab="design"]').click()

    assert student.locator("#bg-up").count() == 0
    # A previous saved status may remain visible during the debounce interval.
    # Wait for the response for this background before inspecting saved state.
    with student.expect_response(lambda response:
            urlsplit(response.url).path == "/rest/v1/rpc/spacetech_poster"
            and response.request.post_data_json.get("p_action") == "save"
            and response.request.post_data_json["p"]["state"].get("design", {}).get("bgId") == "bg3"):
        student.locator('[data-background-id="bg3"]').click()
    expect(student.locator('[data-background-id="bg3"]')).to_have_attribute("aria-pressed", "true")
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()
    assert poster["state"]["design"]["bgId"] == "bg3"
    assert "background" not in poster["state"]["media"]
    assert "bgImage" not in poster["state"]["design"]

    student.locator('[data-tab="content"]').click()
    student.locator("#panel-problem").fill("Full problem text")
    student.locator("#panel-requirements1").fill("Requirement one")
    student.locator("#panel-solution-type").select_option("smart")
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()
    assert poster["state"]["values"]["problem"] == "Full problem text"
    fail_save = True
    student.locator("#poster-project").fill("Fixture Project")
    expect(student.get_by_role("button", name="ניסיון שמירה מחדש")).to_be_visible()
    assert student.evaluate(f"async () => (await posterDrafts.read({json.dumps(poster_id)})).pending")
    fail_save = False
    click(student, "ניסיון שמירה מחדש")
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()

    student.locator("#img-main-file").set_input_files({"name": "fixture.png", "mimeType": "image/png", "buffer": png})
    expect(student.get_by_text("נשמר", exact=True)).to_be_visible()
    expect(student.locator("#img-main")).to_be_visible()
    for attempt in range(30):
        if poster["state"].get("media", {}).get("main"):
            break
        student.wait_for_timeout(100)
    else:
        raise AssertionError("Cloud state did not include the image")

    second = open_page(new_context(browser))
    click(second, "המשך עבודה על פוסטר")
    second.get_by_label("קוד הפוסטר").fill("222222")
    click(second, "המשך")
    expect(second.locator("#poster-project")).to_have_value("Fixture Project")
    expect(second.locator("#poster-students")).to_have_value("Student A, Student B")
    expect(second.locator("#img-main")).to_be_visible()
    expect(second.locator("#approved-bg-image")).to_have_attribute("src", "poster-backgrounds/versions/" + hashlib.sha256(Path("poster-backgrounds/webp/bg3.webp").read_bytes()).hexdigest() + ".webp")
    assert second.evaluate("async () => await backgroundReady")

    for id,color in text_colors.items(): expect(second.locator('#'+id)).to_have_value(color)
    assert poster['state']['design']['projectColor']=='#112233'
    assert poster['state']['design']['descriptionColor']=='#223344'
    assert poster['state']['design']['qColor']=='#334455'
    assert poster['state']['design']['tColor']=='#445566'

    conflict = True
    second.locator("#poster-project").fill("Local update")
    expect(second.get_by_role("button", name="פתיחת גרסת הענן")).to_be_visible()
    dialogs = []
    def accept_conflict_dialog(dialog):
        dialogs.append(dialog.message)
        dialog.accept()
    second.on("dialog", accept_conflict_dialog)
    with second.expect_response(lambda response: urlsplit(response.url).path == "/rest/v1/rpc/spacetech_poster" and response.request.post_data_json.get("p_action") == "load") as cloud_response:
        click(second, "פתיחת גרסת הענן")
    second.remove_listener("dialog", accept_conflict_dialog)
    assert any("לפתוח את גרסת הענן" in message for message in dialogs), dialogs
    assert cloud_response.value.json()["state"]["values"]["poster-project"] == "Remote update"
    print("Cloud response verified; editor status:", second.locator(".poster-cloud-toolbar").inner_text(), flush=True)
    expect(second.locator("#poster-project")).to_have_value("Remote update")
    click(second, "צפייה בטיוטה המקומית")
    expect(second.locator("#poster-project")).to_have_value("Local update")

    staff = open_page(new_context(browser))
    click(staff, "כניסת מדריכים")
    dashboard_sso(staff, "invalid-token")
    expect(staff.get_by_role("status")).to_contain_text("ההתחברות לא הושלמה")
    dashboard_sso(staff, "fixture-token")
    expect(staff.get_by_role("heading", name="ניהול הפוסטרים שלי")).to_be_visible()
    staff.get_by_role("searchbox").fill("Remote update")
    staff.evaluate("window.__languageSessionMarker = true")
    staff.locator("#poster-editor-language").click()
    expect(staff.get_by_role("heading", name="إدارة ملصقاتي")).to_be_visible()
    expect(staff.get_by_role("searchbox")).to_have_value("Remote update")
    expect(staff.locator("details[open]")).to_have_count(1)
    expect(staff.get_by_role("button", name="عرض", exact=True)).to_be_visible()
    assert staff.evaluate("window.__languageSessionMarker === true")
    staff.locator("#poster-editor-language").click()
    expect(staff.get_by_role("heading", name="ניהול הפוסטרים שלי")).to_be_visible()
    expect(staff.get_by_role("searchbox")).to_have_value("Remote update")
    expect(staff.locator("details[open]")).to_have_count(1)
    assert staff.evaluate("window.__languageSessionMarker === true")
    staff.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    click(staff, "העתקת מזהה פעילות")
    assert staff.evaluate("navigator.clipboard.readText()") == activity["id"]
    expect(staff.locator(".poster-activity-id button")).to_have_text("הועתק")
    click(staff, "צפייה")
    expect(staff.locator("#poster-project")).to_have_value("Remote update")
    expect(staff.locator("#poster")).to_have_js_property("inert", True)
    click(staff, "חזרה")
    staff.get_by_role("searchbox").fill("Remote update")
    click(staff, "עריכה")
    # Editing opens asynchronously after the prior read-only view; wait until it is interactive.
    expect(staff.locator("#poster")).to_have_js_property("inert", False)
    staff.locator("#poster-project").fill("Instructor update")
    expect(staff.get_by_text("נשמר", exact=True)).to_be_visible()
    third = open_page(new_context(browser))
    click(third, "המשך עבודה על פוסטר")
    third.get_by_label("קוד הפוסטר").fill("222222")
    click(third, "המשך")
    expect(third.locator("#poster-project")).to_have_value("Instructor update")
    manager = open_page(new_context(browser))
    click(manager, "כניסת מדריכים")
    dashboard_sso(manager, "manager-token")
    expect(manager.get_by_role("heading", name="ניהול הפוסטרים שלי")).to_be_visible()
    expect(manager.get_by_text("Fixture Manager", exact=True)).to_be_visible()
    expect(manager.get_by_role("button", name="העתקת קוד מדריך")).to_have_count(0)
    manager.get_by_role("searchbox").fill("Instructor update")
    click(manager, "צפייה")
    expect(manager.locator("#poster-project")).to_have_value("Instructor update")
    for viewer in (manager,):
        expect(viewer.locator("#problem")).to_have_value("Full problem text")
        expect(viewer.locator("#requirements1-out")).to_have_text("Requirement one")
        expect(viewer.locator("#solution-type")).to_have_value("smart")
        expect(viewer.locator("#poster-students")).to_have_value("Student A, Student B")
        expect(viewer.locator("#img-main")).to_be_visible()
        expect(viewer.locator("#approved-bg-image")).to_have_attribute("src", "poster-backgrounds/versions/" + hashlib.sha256(Path("poster-backgrounds/webp/bg3.webp").read_bytes()).hexdigest() + ".webp")
    arabic = open_page(new_context(browser))
    arabic.locator("#poster-editor-language").click()
    expect(arabic.locator("#poster-access")).to_have_attribute("lang", "ar")
    expect(arabic.get_by_role("button", name="إنشاء ملصق جديد")).to_be_visible()
    assert arabic.locator("#poster-access").evaluate("(node) => getComputedStyle(node).direction") == "rtl"
    assert not errors, errors
    print("PASS: create, scoped draft, failed save and retry, image, new browser, conflict recovery and instructor view")

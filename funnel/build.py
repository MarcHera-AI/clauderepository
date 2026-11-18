#!/usr/bin/env python3
"""Render the per-client funnel pages.

funnel/template.html is the single source of truth for how the funnel
works. clients/<slug>.json holds only what differs per client. This
script combines them into dist/<slug>/index.html:

    python3 funnel/build.py                 # every client in clients/
    python3 funnel/build.py homecareaide    # just one
    python3 funnel/build.py --draft ...     # render TODO values anyway

Cloudflare Pages runs the first form. Each client has its own Pages
project with the same build command and output directory dist/<slug>.

A client whose JSON still contains a "TODO" value is skipped, not built,
so its dist/<slug> never exists and its Pages build fails loudly instead
of deploying a half-filled page. The other clients still build. A config
that is malformed (wrong types, a question routing to a disqualify screen
that doesn't exist) stops the whole build: that is a bug, not a gap.

No third-party packages: the Pages build image only promises python3.
"""
import copy
import datetime
import html
import json
import pathlib
import re
import shutil
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "funnel" / "template.html"
CLIENTS = ROOT / "clients"
DIST = ROOT / "dist"

# Values a client may leave out. Everything else must be in its JSON.
# The theme defaults are the Cozly palette.
DEFAULTS = {
    "brand": {"logoUrl": "", "logoHeight": None, "wordmarkSub": "", "faviconLetter": ""},
    "theme": {
        "bg": "#fdfbf7",
        "accent": "#f5b800",
        "accentDark": "#e0a800",
        "accentInk": "#1a1500",
        "accentTint": "#fdf6e2",
        "thankYouTitle": "#e02020",
    },
    "phone": None,
    "media": {"vsl": "", "thankYou": ""},
    "form": {"extraField": None, "consent": None},
    "serviceArea": None,
    # Blank copy lines are left off the page rather than shown empty.
    "copy": {
        "callPrompt": "Prefer to talk? Call",
        "disclaimer": "",
        "form": {"subhead": ""},
        "thankYou": {"subhead": "", "stepsHead": ""},
    },
    "calendar": {
        "mode": "rules",
        "url": "",
        "utcOffsetHours": None,
        "zoneAbbr": "",
        "blockedDates": [],
        "slotIntervalMin": 0,
        "leadTimeMin": 0,
    },
    "slotsApi": "",
    "pixelId": "",
}

# Keys the webhook payload already uses; an extra form field can't take one.
PAYLOAD_KEYS = {
    "event", "source", "funnel", "funnel_slug", "lead_id", "name", "first_name",
    "last_name", "email", "phone", "booked", "answers", "answers_text", "page_url",
    "submitted_at", "booking_time", "booking_time_local", "booking_time_visitor",
    "booking_time_ghl", "booking_duration_min", "calendar_id", "timezone_visitor",
    "consent", "consent_text", "in_service_area",
}

# Copy may say {agency} or {phone}; the build writes in the config value,
# so a spelling or number change is one edit, not a hunt through copy.
TOKENS = ("agency", "phone")
TOKEN_SCOPES = ("copy", "questions", "disqualify", "form")


class ConfigError(Exception):
    pass


def merge(base, over):
    """Deep-merge `over` onto a copy of `base`. Lists and scalars replace."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out


def get(cfg, path):
    node = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def find_todos(node, path=""):
    """Every string value still holding a TODO marker, by path."""
    if isinstance(node, str):
        return [path] if "TODO" in node else []
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in find_todos(v, f"{path}.{k}" if path else k)]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in find_todos(v, f"{path}[{i}]")]
    return []


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
REQUIRED_TEXT = [
    "slug", "agency", "domain",
    "meta.title", "meta.description",
    "brand.wordmark",
    "copy.vsl.eyebrow", "copy.vsl.headline", "copy.vsl.subhead", "copy.vsl.cta",
    "copy.form.title", "copy.form.submit", "copy.form.namePlaceholder",
    "copy.thankYou.title",
    "copy.callPrompt",
    "funnelMeta.source", "funnelMeta.funnel", "funnelMeta.funnel_slug",
    "webhookUrl",
]

# Only when the client has a calendar (calendar is not null).
CALENDAR_TEXT = [
    "copy.calendar.title", "copy.calendar.subhead", "copy.calendar.confirm",
    "copy.calendar.busy", "copy.calendar.none", "copy.calendar.bookedLabel",
    "calendar.id", "calendar.timezone",
]
CALENDAR_COPY_KEYS = ["title", "subhead", "confirm", "busy", "none", "bookedLabel"]

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(cfg, slug):
    errors, warnings = [], []
    err = errors.append

    cal = cfg.get("calendar")
    if cal is not None and not isinstance(cal, dict):
        err("calendar must be an object, or null for no calendar step")
        cal = None
    for path in REQUIRED_TEXT + (CALENDAR_TEXT if cal is not None else []):
        try:
            v = get(cfg, path)
        except KeyError:
            err(f"{path} is missing")
            continue
        if not isinstance(v, str) or not v.strip():
            err(f"{path} must be a non-empty string")

    if cfg.get("slug") != slug:
        err(f"slug is {cfg.get('slug')!r} but the file is clients/{slug}.json")
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        err("the slug may only use a-z, 0-9 and '-' (it becomes a folder and a storage key)")

    lh = get_safe(cfg, "brand.logoHeight")
    if lh is not None and not (is_int(lh) and 16 <= lh <= 240):
        err("brand.logoHeight must be null or a whole number of pixels, 16-240")

    for k, v in cfg.get("theme", {}).items():
        if not (isinstance(v, str) and HEX_RE.match(v)):
            err(f"theme.{k} must be a #rrggbb colour, got {v!r}")

    # ---- questions and the disqualify screens they route to ----
    qs = cfg.get("questions")
    dqs = cfg.get("disqualify")
    if not isinstance(dqs, dict):
        err("disqualify must be an object of {key: {title, body: [...]}}")
        dqs = {}
    for key, dq in dqs.items():
        if not KEY_RE.match(key):
            err(f"disqualify key {key!r} must be lower_snake_case")
        if not (isinstance(dq, dict) and isinstance(dq.get("title"), str) and dq["title"].strip()):
            err(f"disqualify.{key}.title is required")
        body = dq.get("body") if isinstance(dq, dict) else None
        if not (isinstance(body, list) and body and all(isinstance(p, str) and p.strip() for p in body)):
            err(f"disqualify.{key}.body must be a non-empty list of paragraphs")

    used_dq = set()
    if not (isinstance(qs, list) and qs):
        err("questions must be a non-empty list")
        qs = []
    seen = set()
    for i, q in enumerate(qs):
        where = f"questions[{i}]"
        if not isinstance(q, dict):
            err(f"{where} must be an object")
            continue
        key = q.get("key")
        if not (isinstance(key, str) and KEY_RE.match(key)):
            err(f"{where}.key must be lower_snake_case")
        elif key in seen:
            err(f"{where}.key {key!r} is used twice")
        seen.add(key)
        if not (isinstance(q.get("title"), str) and q["title"].strip()):
            err(f"{where}.title is required")
        opts = q.get("options")
        if not (isinstance(opts, list) and len(opts) >= 2):
            err(f"{where}.options needs at least two options")
            continue
        for j, o in enumerate(opts):
            if not (isinstance(o, dict) and isinstance(o.get("label"), str) and o["label"].strip()):
                err(f"{where}.options[{j}].label is required")
                continue
            if "dq" in o:
                if o["dq"] not in dqs:
                    err(f"{where}.options[{j}] routes to disqualify.{o['dq']}, which doesn't exist")
                used_dq.add(o["dq"])
        if all(isinstance(o, dict) and "dq" in o for o in opts):
            err(f"{where}: every option disqualifies, so nobody can get past it")
    area = cfg.get("serviceArea")
    if isinstance(area, dict) and isinstance(area.get("dq"), str):
        used_dq.add(area["dq"])
    for key in set(dqs) - used_dq:
        warnings.append(f"disqualify.{key} is never routed to")

    steps = get_safe(cfg, "copy.thankYou.steps")
    if not (isinstance(steps, list) and steps and all(isinstance(s, str) and s.strip() for s in steps)):
        err("copy.thankYou.steps must be a non-empty list of strings")

    # ---- form ----
    extra = get_safe(cfg, "form.extraField")
    if extra is not None:
        if not isinstance(extra, dict):
            err("form.extraField must be null or {key, placeholder, error}")
        else:
            for k in ("key", "placeholder", "error"):
                if not (isinstance(extra.get(k), str) and extra[k].strip()):
                    err(f"form.extraField.{k} is required")
            k = extra.get("key", "")
            if isinstance(k, str) and not KEY_RE.match(k):
                err("form.extraField.key must be lower_snake_case")
            if k in PAYLOAD_KEYS or k in seen:
                err(f"form.extraField.key {k!r} collides with a payload field or question key")
            pat = extra.get("pattern")
            if pat is not None:
                try:
                    re.compile(pat)
                except (re.error, TypeError):
                    err("form.extraField.pattern is not a valid regular expression")
            if "maxlength" in extra and not (is_int(extra["maxlength"]) and extra["maxlength"] > 0):
                err("form.extraField.maxlength must be a whole number")

    consent = get_safe(cfg, "form.consent")
    if consent is not None:
        if not (isinstance(consent, dict) and all(
                isinstance(consent.get(k), str) and consent[k].strip() for k in ("label", "error"))):
            err("form.consent must be null or {label, error}")

    # ---- service area: the extra field checked against a ZIP list ----
    if area is not None:
        if not isinstance(area, dict):
            err("serviceArea must be null or {field, zips, dq}")
        else:
            if not (isinstance(extra, dict) and area.get("field") == extra.get("key")):
                err("serviceArea.field must be the form.extraField key (the ZIP the visitor types)")
            zips = area.get("zips")
            if not (isinstance(zips, list) and zips and all(isinstance(z, str) and re.fullmatch(r"\d{5}", z) for z in zips)):
                err("serviceArea.zips must be a non-empty list of 5-digit strings")
            elif len(set(zips)) != len(zips):
                err("serviceArea.zips lists a ZIP twice")
            if area.get("dq") not in dqs:
                err(f"serviceArea.dq routes to disqualify.{area.get('dq')}, which doesn't exist")

    # ---- endpoints ----
    def https(path, allow_empty):
        v = get_safe(cfg, path)
        if allow_empty and v == "":
            return
        if not (isinstance(v, str) and v.startswith("https://") and urllib.parse.urlparse(v).netloc):
            err(f"{path} must be an https:// URL" + (' or ""' if allow_empty else ""))

    https("webhookUrl", False)
    https("slotsApi", True)
    if not re.fullmatch(r"\d*", str(cfg.get("pixelId", ""))):
        err("pixelId must be digits only, or empty for no pixel")

    phone = cfg.get("phone")
    if phone is not None:
        digits = re.sub(r"\D", "", str(phone.get("display", "")) if isinstance(phone, dict) else "")
        if not (isinstance(phone, dict) and len(digits) >= 10):
            err('phone must be null or {"display": "(707) 555-0100"}')

    # ---- tokens ----
    if cfg.get("phone") is None:
        for path in find_token(cfg, "{phone}"):
            err(f"{path} says {{phone}} but phone is null")

    # ---- calendar ----
    if cal is None:
        return errors, warnings
    if cal.get("mode") not in ("rules", "embed"):
        err('calendar.mode must be "rules" or "embed"')
    days = cal.get("days")
    if not (isinstance(days, list) and days and all(is_int(d) and 0 <= d <= 6 for d in days)):
        err("calendar.days must list weekdays as 0 (Sun) to 6 (Sat)")
    for k, lo, hi in (("startHour", 0, 23), ("endHour", 1, 24)):
        if not (is_int(cal.get(k)) and lo <= cal[k] <= hi):
            err(f"calendar.{k} must be a whole hour {lo}-{hi}")
    if is_int(cal.get("startHour")) and is_int(cal.get("endHour")) and cal["startHour"] >= cal["endHour"]:
        err("calendar.startHour must be before calendar.endHour")
    for k, lo in (("durationMin", 1), ("slotIntervalMin", 0), ("bookUpTo", 1), ("leadTimeMin", 0)):
        if not (is_int(cal.get(k)) and cal[k] >= lo):
            err(f"calendar.{k} must be a whole number >= {lo}")
    for d in cal.get("blockedDates", []):
        try:
            datetime.date.fromisoformat(d)
        except (TypeError, ValueError):
            err(f"calendar.blockedDates: {d!r} is not YYYY-MM-DD")
    off = cal.get("utcOffsetHours")
    if off is not None:
        if not isinstance(off, (int, float)) or isinstance(off, bool):
            err("calendar.utcOffsetHours must be a number or null")
        elif not cal.get("zoneAbbr"):
            err("calendar.zoneAbbr is required when utcOffsetHours pins the offset")
    check_zone(cal.get("timezone"), off, errors, warnings)

    return errors, warnings


def get_safe(cfg, path):
    try:
        return get(cfg, path)
    except KeyError:
        return None


def find_token(cfg, token):
    out = []
    def walk(node, path):
        if isinstance(node, str):
            if token in node:
                out.append(path)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    for scope in TOKEN_SCOPES:
        walk(cfg.get(scope), scope)
    return out


def fill_tokens(cfg):
    """Write {agency} and {phone} into the copy. Copy is HTML, so the
    values are escaped on the way in."""
    values = {
        "agency": html.escape(cfg["agency"]),
        "phone": html.escape(cfg["phone"]["display"]) if cfg.get("phone") else None,
    }
    def walk(node):
        if isinstance(node, str):
            for name in TOKENS:
                if values[name] is not None:
                    node = node.replace("{" + name + "}", values[name])
            return node
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node
    for scope in TOKEN_SCOPES:
        if scope in cfg:
            cfg[scope] = walk(cfg[scope])


def check_zone(tz, pinned, errors, warnings):
    """The zone must exist. A pinned offset in a zone that changes its
    clocks is almost always a mistake: the slots would be an hour off for
    half the year. That is a warning rather than an error because pinning
    exists for the opposite case -- a zone that STOPPED changing before the
    tz database caught up -- and this machine's tz data can lag too."""
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        warnings.append("zoneinfo unavailable; calendar.timezone not checked")
        return
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        # Windows has no system tz database without the tzdata package.
        # Linux (Cloudflare's build image) does, so a real typo is still
        # caught where it matters.
        if sys.platform.startswith("win"):
            warnings.append(f"no tz database here; calendar.timezone {tz!r} not checked")
        else:
            errors.append(f"calendar.timezone {tz!r} is not a known IANA zone")
        return
    except (TypeError, ValueError):
        errors.append(f"calendar.timezone {tz!r} is not a known IANA zone")
        return
    if pinned is None:
        return
    year = datetime.date.today().year
    offsets = {
        datetime.datetime(year, m, 15, 12, tzinfo=zone).utcoffset().total_seconds() / 3600
        for m in (1, 7)
    }
    if len(offsets) > 1:
        warnings.append(
            f"calendar.utcOffsetHours pins {pinned} but the tz database says {tz} changes "
            f"its clocks ({sorted(offsets)}). Use null unless the zone really stopped."
        )
    elif pinned not in offsets:
        warnings.append(f"calendar.utcOffsetHours {pinned} disagrees with {tz} ({offsets.pop()})")


# --------------------------------------------------------------------------
# Derived values
# --------------------------------------------------------------------------
def favicon(cfg):
    letter = (cfg["brand"].get("faviconLetter") or cfg["agency"][:1]).strip()[:1] or "?"
    t = cfg["theme"]
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
        f"<rect width='100' height='100' rx='22' fill='{t['accent']}'/>"
        "<text x='50' y='71' font-size='66' font-family='Helvetica,Arial,sans-serif' "
        f"font-weight='700' text-anchor='middle' fill='{t['accentInk']}'>{html.escape(letter)}</text>"
        "</svg>"
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe=" '=/:,")


def tel(display):
    digits = re.sub(r"\D", "", display)
    # Ten digits is a North American number written without the country code.
    return "+1" + digits if len(digits) == 10 else "+" + digits


def page_config(cfg):
    """The CONFIG object the page runs on: the client's JSON with the
    derived values filled in. Safe to drop into a <script> block."""
    run = copy.deepcopy(cfg)
    if run.get("phone"):
        run["phone"]["tel"] = tel(run["phone"]["display"])
    if run["calendar"] is not None and not run["calendar"].get("url"):
        run["calendar"]["url"] = (
            "https://api.leadconnectorhq.com/widget/booking/" + run["calendar"]["id"]
        )
    text = json.dumps(run, indent=2, ensure_ascii=False)
    # "</script>" inside a string would end the block early.
    return text.replace("</", "<\\/")


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)(?:\|([a-z]+))?\s*\}\}")


def render(template, cfg):
    """{{ path }} is HTML-escaped. {{ path|html }} is copy that may carry
    markup (it comes from our own JSON, so it is trusted). {{ path|raw }}
    is for computed values that are already safe in place."""
    scope = dict(cfg)
    scope["computed"] = {"favicon": favicon(cfg), "configJson": page_config(cfg)}

    def sub(m):
        path, flt = m.group(1), m.group(2) or "text"
        try:
            v = get(scope, path)
        except KeyError:
            raise ConfigError(f"template asks for {path}, which the config doesn't have")
        if not isinstance(v, str):
            raise ConfigError(f"template wants {path} as text, got {type(v).__name__}")
        if flt == "text":
            return html.escape(v, quote=True)
        if flt in ("html", "raw"):
            return v
        raise ConfigError(f"unknown filter |{flt} on {path}")

    out = PLACEHOLDER.sub(sub, template)
    left = re.search(r"\{\{|\}\}", out.replace(scope["computed"]["configJson"], ""))
    if left:
        raise ConfigError(f"unrendered template tag near: {out[left.start():left.start() + 40]!r}")
    return out


def copy_logo(cfg, out_dir):
    """A logo can be an https URL, or a file under clients/ that ships
    with the page (copied next to index.html)."""
    url = cfg["brand"].get("logoUrl", "")
    if not url or url.startswith("https://"):
        return
    src = (CLIENTS / url).resolve()
    if CLIENTS.resolve() not in src.parents or not src.is_file():
        raise ConfigError(f"brand.logoUrl {url!r} is neither https:// nor a file under clients/")
    shutil.copy2(src, out_dir / src.name)
    cfg["brand"]["logoUrl"] = src.name


# A draft is only for looking at locally. Text TODOs stay visible on the
# page; these ones would break it instead, so they get inert stand-ins.
DRAFT_STAND_INS = {
    "brand.logoUrl": "",
    "media.vsl": "",
    "media.thankYou": "",
    "webhookUrl": "",
    "slotsApi": "",
    "pixelId": "",
    "calendar.timezone": "America/Los_Angeles",
}


def draft_stand_ins(cfg, todos):
    for path in todos:
        if path in DRAFT_STAND_INS:
            *parents, leaf = path.split(".")
            node = cfg
            for part in parents:
                node = node[part]
            node[leaf] = DRAFT_STAND_INS[path]
            print(f"  draft {path} -> {DRAFT_STAND_INS[path]!r}")


def build(slug, template, draft):
    raw = json.loads((CLIENTS / f"{slug}.json").read_text(encoding="utf-8"))
    raw.pop("_notes", None)          # free-text notes for humans, never shipped
    cfg = merge(DEFAULTS, raw)

    todos = find_todos(cfg)
    errors, warnings = validate(cfg, slug)
    # A TODO is a known gap, reported below; it isn't also a type error.
    def about_todo(msg):
        head = msg.split(" ", 1)[0]
        return any(t == head or t.startswith((head + ".", head + "[")) for t in todos)
    errors = [e for e in errors if not about_todo(e)]
    warnings = [w for w in warnings if not any(t in w for t in ("'TODO", '"TODO'))]
    for w in warnings:
        print(f"  warn  {slug}: {w}")
    if errors:
        raise ConfigError("\n".join(f"  error {slug}: {e}" for e in errors))
    if todos and not draft:
        print(f"  SKIP  {slug}: still has TODO values, not built:")
        for p in todos:
            print(f"          - {p}")
        return False

    if todos:
        draft_stand_ins(cfg, todos)
    fill_tokens(cfg)
    if cfg["calendar"] is None:
        # The calendar step's markup is still in the template (the page
        # drops it at boot), so its tags need something to render.
        cfg["copy"]["calendar"] = {k: "" for k in CALENDAR_COPY_KEYS}

    out_dir = DIST / slug
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    copy_logo(cfg, out_dir)
    (out_dir / "index.html").write_text(render(template, cfg), encoding="utf-8", newline="\n")
    note = f" (DRAFT: {len(todos)} TODO values rendered as-is)" if todos else ""
    print(f"  built dist/{slug}/index.html{note}")
    return True


def main(argv):
    draft = "--draft" in argv
    slugs = [a for a in argv if not a.startswith("--")]
    if not slugs:
        slugs = sorted(p.stem for p in CLIENTS.glob("*.json"))
    if not slugs:
        print("no clients/*.json found")
        return 1

    template = TEMPLATE.read_text(encoding="utf-8")
    failed = False
    for slug in slugs:
        if not (CLIENTS / f"{slug}.json").is_file():
            print(f"  error {slug}: clients/{slug}.json not found")
            failed = True
            continue
        try:
            build(slug, template, draft)
        except (ConfigError, json.JSONDecodeError) as e:
            print(e if isinstance(e, ConfigError) else f"  error {slug}: bad JSON: {e}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

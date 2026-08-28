#!/usr/bin/env python3
"""Derive the GoHighLevel paste blocks from the standalone site.

The standalone files in the repo root are the single source of truth.
Run this after editing them so the embed versions never drift:

    python3 webbuilder/build.py
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "webbuilder"
WRAP = "#hera-site"

# The site's own background, reused for the GHL page-level override.
PAGE_BG = "#08090b"


# --------------------------------------------------------------------------
# CSS: scope every selector to the wrapper so it cannot leak into the builder
# --------------------------------------------------------------------------
def scope_selector(sel: str) -> str:
    sel = sel.strip()
    if not sel:
        return sel
    # scroll-behavior only works on the root element, so leave html alone
    if sel == "html":
        return sel
    if sel in (":root", "body"):
        return WRAP
    if sel == "*":
        return f"{WRAP} *"
    if sel.startswith(WRAP):
        return sel
    # ".js .reveal" -> the js class lands on the wrapper itself
    if sel.startswith(".js "):
        return f"{WRAP}.js {sel[4:].strip()}"
    return f"{WRAP} {sel}"


def scope_selector_list(sel_list: str) -> str:
    parts = []
    for sel in sel_list.split(","):
        sel = sel.strip()
        if sel.startswith(".js "):
            parts.append(f"{WRAP}.js {sel[4:].strip()}")
        else:
            parts.append(scope_selector(sel))
    return ",\n".join(parts)


def split_rules(css: str):
    """Yield (prelude, body, is_at_rule) for each top-level block."""
    out, depth, buf = [], 0, ""
    for ch in css:
        buf += ch
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(buf)
                buf = ""
    if buf.strip():
        out.append(buf)
    return out


def scope_css(css: str) -> str:
    # Pull comments out of harm's way by leaving them attached to blocks.
    imports = re.findall(r"@import[^;]+;", css)
    css = re.sub(r"@import[^;]+;", "", css)

    result = []
    for block in split_rules(css):
        if "{" not in block:
            result.append(block)
            continue
        prelude, rest = block.split("{", 1)
        inner = rest.rsplit("}", 1)[0]

        # Peel off any comments sitting in front of the selector first, so a
        # commented @media block is still recognised as an at-rule.
        comment = ""
        while True:
            m = re.match(r"\s*(/\*.*?\*/)\s*", prelude, re.S)
            if not m:
                break
            comment += m.group(1) + "\n"
            prelude = prelude[m.end():]
        head = prelude.strip()

        if head.startswith("@keyframes"):
            result.append(f"{comment}{head} {{{inner}}}\n")   # keyframes need no scoping
        elif head.startswith("@media") or head.startswith("@supports"):
            result.append(f"{comment}{head} {{\n{scope_css(inner)}\n}}\n")
        else:
            result.append(f"{comment}{scope_selector_list(head)} {{{inner}}}\n")

    return "".join(imports) + "\n" + "".join(result)


GHL_CLEANUP = f"""

/* ===== GoHighLevel page cleanup =====
   Removes the builder's own white spacing above and below the embed.
   If you later add other sections to this page that need their own
   padding, delete this block and set THIS section's padding to 0 in
   the builder settings instead. */
body {{
  margin: 0 !important;
  padding: 0 !important;
  background: {PAGE_BG} !important;
}}

.c-section, .c-row, .c-column, .c-wrapper,
.hl_page-creator--section, .hl_page-creator--row, .hl_page-creator--col,
.fullSection, .noBorder {{
  padding: 0 !important;
}}
"""

BREAKOUT = f"""
/* Break out of the builder's boxed column so the site spans the full
   viewport width no matter how narrow the parent section is.

   min-height fills the screen when the content is shorter than the
   viewport -- a short survey slide would otherwise end mid-screen and
   let the builder's white page background show underneath. The column
   layout pushes the footer to the bottom in that case instead of
   leaving it stranded in the middle. */
html {{ background: {PAGE_BG}; }}

{WRAP} {{
  width: auto;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}}

{WRAP} > main {{ flex: 1 0 auto; }}
{WRAP} > footer {{ flex-shrink: 0; }}
"""


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
EMBED_JS = """
<script>
(function () {
  var site = document.getElementById('hera-site');
  if (!site) return;
  site.classList.add('js');

  // ---- Mobile navigation ----
  var navToggle = document.getElementById('heraNavToggle');
  var navLinks = document.getElementById('heraNavLinks');

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      var open = navLinks.classList.toggle('is-open');
      navToggle.classList.toggle('is-open', open);
      navToggle.setAttribute('aria-expanded', String(open));
    });
    navLinks.addEventListener('click', function (e) {
      if (e.target.closest('a')) {
        navLinks.classList.remove('is-open');
        navToggle.classList.remove('is-open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ---- Scroll reveal ----
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var revealEls = site.querySelectorAll('.reveal');

  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { observer.observe(el); });
  }

  // ---- Lightbox for testimonial screenshots ----
  var lightbox = document.getElementById('heraLightbox');
  var lightboxImg = document.getElementById('heraLightboxImg');

  if (lightbox && lightboxImg) {
    var closeLightbox = function () {
      lightbox.classList.remove('is-open');
      lightboxImg.src = '';
      document.body.style.overflow = '';
    };

    site.querySelectorAll('.wall__item').forEach(function (item) {
      item.addEventListener('click', function () {
        var img = item.querySelector('img');
        if (!img) return;
        lightboxImg.src = img.src;
        lightboxImg.alt = img.alt || '';
        lightbox.classList.add('is-open');
        document.body.style.overflow = 'hidden';
      });
    });

    lightbox.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && lightbox.classList.contains('is-open')) closeLightbox();
    });
  }

  // ---- Footer year ----
  var yearEl = document.getElementById('heraYear');
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
</script>

<!-- GoHighLevel widget auto-resize (booking calendar + forms) -->
<script src="https://link.msgsndr.com/js/form_embed.js" type="text/javascript"></script>
"""

HEADER = """<!-- ============================================================
     Hera Solutions {variant}
     Paste this whole file into ONE custom HTML / embed element.
     Pair it with hera-styles.css in the builder's Custom CSS area.

     Generated from index.html by webbuilder/build.py -- edit the
     source files in the repo root, then re-run the script.

     Quick edits:
     - Hero photo: set --hero-image at the top of the CSS
     - Screenshots: the .wall__item buttons (add or remove freely)
     - Booking calendar: the iframe src
     ============================================================ -->

"""


def build_html(variant_name: str, drop_nav: bool, source: str = "index.html") -> str:
    html = (ROOT / source).read_text()
    head = html.split("<head>", 1)[1].split("</head>", 1)[0]

    # Third-party player markup lives in <head> on the standalone page, but
    # has to travel inside the embed block in the builder.
    extras = re.findall(r'<script[^>]*fast\.wistia\.com[^>]*>\s*</script>', head)
    extras += [m for m in re.findall(r"<style>.*?</style>", head, re.S) if "wistia-player" in m]
    extras_html = ("\n".join(extras) + "\n\n") if extras else ""

    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    body = body.replace('<script src="js/main.js"></script>', "")
    body = body.replace(
        '<script src="https://link.msgsndr.com/js/form_embed.js" type="text/javascript"></script>', ""
    )
    # ids that could collide with the builder's own markup
    body = body.replace('id="navLinks"', 'id="heraNavLinks"')
    body = body.replace('id="navToggle"', 'id="heraNavToggle"')
    body = body.replace('id="year"', 'id="heraYear"')

    if drop_nav:
        body = re.sub(r"  <!-- ===== Navigation ===== -->.*?</header>\n", "", body, flags=re.S)
        body = body.replace('<section class="hero">', '<section class="hero" id="top">')

    fonts = ('<link href="https://fonts.googleapis.com/css2?'
             'family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap" '
             'rel="stylesheet" />\n\n')

    return (HEADER.format(variant=variant_name) + fonts + extras_html
            + '<div id="hera-site">\n' + body.rstrip() + '\n</div><!-- /#hera-site -->\n'
            + EMBED_JS)


def main():
    css = (ROOT / "css" / "style.css").read_text()
    scoped = scope_css(css) + BREAKOUT + GHL_CLEANUP
    banner = ("/* ============================================================\n"
              "   Hera Solutions - stylesheet for the GoHighLevel embed\n"
              "   Paste this whole file into the builder's Custom CSS area.\n\n"
              "   Generated from css/style.css by webbuilder/build.py -- edit\n"
              "   the source file in the repo, then re-run the script.\n"
              "   ============================================================ */\n\n"
              "/* Fonts. The HTML block links these too; this is a fallback for\n"
              "   builders that strip <link> tags out of custom HTML. */\n"
              "@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800"
              "&family=Inter:wght@400;500;600&display=swap');\n\n")
    (OUT / "hera-styles.css").write_text(banner + scoped)

    (OUT / "hera-page.html").write_text(build_html("web-builder block (with navigation)", False))
    (OUT / "hera-page-no-nav.html").write_text(build_html("web-builder block (no navigation)", True))

    # Single-paste build: CSS inlined in a <style> tag so there is only one
    # thing to paste and no separate Custom CSS field to fall out of sync.
    page = build_html("all-in-one block (styles included)", False).replace(
        "     Pair it with hera-styles.css in the builder's Custom CSS area.\n",
        "     Styles are included inline, so there is NOTHING to paste into\n"
        "     the Custom CSS area. Clear that field of any older stylesheet.\n",
    )
    marker = '<div id="hera-site">'
    combined = page.replace(
        marker,
        "<style>\n" + scoped + "\n</style>\n\n" + marker,
        1,
    )
    (OUT / "hera-all-in-one.html").write_text(combined)

    # ---- Thank-you / confirmation page ----
    ty = build_html("thank-you page (all-in-one, styles included)", False, "thankyou.html").replace(
        "     Pair it with hera-styles.css in the builder's Custom CSS area.\n",
        "     Styles are included inline, so there is NOTHING to paste into\n"
        "     the Custom CSS area. Clear that field of any older stylesheet.\n",
    )
    (OUT / "hera-thankyou.html").write_text(
        build_html("thank-you page (pairs with hera-styles.css)", False, "thankyou.html")
    )
    ty = ty.replace(marker, "<style>\n" + scoped + "\n</style>\n\n" + marker, 1)
    (OUT / "hera-thankyou-all-in-one.html").write_text(ty)

    # ---- Booking page ----
    (OUT / "hera-book.html").write_text(
        build_html("booking page (pairs with hera-styles.css)", False, "book.html")
    )
    bk = build_html("booking page (all-in-one, styles included)", False, "book.html").replace(
        "     Pair it with hera-styles.css in the builder's Custom CSS area.\n",
        "     Styles are included inline, so there is NOTHING to paste into\n"
        "     the Custom CSS area. Clear that field of any older stylesheet.\n",
    )
    bk = bk.replace(marker, "<style>\n" + scoped + "\n</style>\n\n" + marker, 1)
    (OUT / "hera-book-all-in-one.html").write_text(bk)

    # ---- Landing page (form instead of the calendar) ----
    (OUT / "hera-landing.html").write_text(
        build_html("landing page (pairs with hera-styles.css)", False, "landing.html")
    )
    ld = build_html("landing page (all-in-one, styles included)", False, "landing.html").replace(
        "     Pair it with hera-styles.css in the builder's Custom CSS area.\n",
        "     Styles are included inline, so there is NOTHING to paste into\n"
        "     the Custom CSS area. Clear that field of any older stylesheet.\n",
    )
    ld = ld.replace(marker, "<style>\n" + scoped + "\n</style>\n\n" + marker, 1)
    (OUT / "hera-landing-all-in-one.html").write_text(ld)

    # ---- "Not a fit" page (survey disqualify redirect) ----
    (OUT / "hera-notfit.html").write_text(
        build_html("not-a-fit page (pairs with hera-styles.css)", False, "not-a-fit.html")
    )
    nf = build_html("not-a-fit page (all-in-one, styles included)", False, "not-a-fit.html").replace(
        "     Pair it with hera-styles.css in the builder's Custom CSS area.\n",
        "     Styles are included inline, so there is NOTHING to paste into\n"
        "     the Custom CSS area. Clear that field of any older stylesheet.\n",
    )
    nf = nf.replace(marker, "<style>\n" + scoped + "\n</style>\n\n" + marker, 1)
    (OUT / "hera-notfit-all-in-one.html").write_text(nf)

    print("wrote hera-styles.css, hera-page.html, hera-page-no-nav.html,")
    print("      hera-all-in-one.html, hera-thankyou.html,")
    print("      hera-thankyou-all-in-one.html, hera-book.html,")
    print("      hera-book-all-in-one.html, hera-landing.html,")
    print("      hera-landing-all-in-one.html, hera-notfit.html,")
    print("      hera-notfit-all-in-one.html")


if __name__ == "__main__":
    main()

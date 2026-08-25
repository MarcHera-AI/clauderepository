# Hera Solutions — Website

Dark-theme site for **Hera Solutions**, a contractor marketing agency that runs
Meta ads for deck builders and books qualified homeowner estimates.

## Stack

Static HTML + CSS + vanilla JavaScript. No build step and no dependencies, so it
deploys as-is to GitHub Pages, Netlify or Vercel, and the same content also
generates paste-in blocks for GoHighLevel.

## Structure

```
index.html            # the site (source of truth)
css/style.css         # design system + layout (CSS variables at the top)
js/main.js            # mobile nav, scroll reveal, click-to-load video, year
images/               # logo PNGs (kept for reference; the site loads the
                      #   originals from the GHL media CDN)
webbuilder/
  build.py            # generates the GHL blocks from the files above
  hera-styles.css     # GENERATED - paste into GHL Custom CSS
  hera-page.html      # GENERATED - paste into one custom HTML element
  hera-page-no-nav.html  # GENERATED - same, minus the top nav
```

**The files in `webbuilder/` are generated.** Edit `index.html`, `css/style.css`
and `js/main.js`, then run:

```
python3 webbuilder/build.py
```

That scopes every CSS rule to the `#hera-site` wrapper, inlines the JavaScript,
adds the full-width breakout, and appends the GoHighLevel page-padding reset.

## Brand

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#08090b` | Page background |
| `--bg-2` | `#0d0f12` | Alternating sections |
| `--card` | `#121419` | Cards |
| `--accent` | `#f8b117` | Buttons, highlights, accents |
| `--ink` | `#ffffff` | Headings and primary text |

Buttons use dark text on orange, which clears WCAG AA comfortably. White text on
this orange would not, so keep the dark text if you restyle them.

## Things to fill in

- **Hero photo** — set `--hero-image` at the top of the CSS to a real photo URL.
  Until then the hero falls back to a gradient, which looks deliberate but flat.
- **Client logos** — the `.marquee__item` slots say "Your Client Logo". Swap each
  for `<img src="..." alt="..." />` and edit **both** marquee tracks so the loop
  stays seamless.
- **Testimonials** — the `.tcard` blocks in the Results section. Photo cards take
  an `<img>`; video cards take a YouTube id in `data-video` plus a thumbnail.
- **Trust line** — the hero says "Trusted by contractors across the US and
  Canada". Add a real client count when you have one to stand behind.

## Local preview

```
python3 -m http.server 8000
# open http://localhost:8000
```

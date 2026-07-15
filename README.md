# Hera Solutions — Website

Clean, single-page website for **Hera Solutions**, a contractor-marketing agency that runs Meta Ads and books qualified homeowner leads.

## Stack

Static HTML + CSS + vanilla JavaScript. No build step, no dependencies — deployable as-is to GitHub Pages, Netlify, Vercel, or any static host.

## Structure

```
index.html       # the page (nav, hero, services, results, about, process, booking, FAQ, contact, footer)
css/style.css    # design system + layout (CSS custom properties at the top)
js/main.js       # mobile nav, scroll reveal, stat count-up, footer year
fonts/           # self-hosted variable fonts (Baloo 2 + Inter, latin subsets)
images/          # logo PNGs (dark variant for light backgrounds, light for dark)
webbuilder/      # copy-paste versions for external page builders (GoHighLevel etc.)
```

## Brand

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#faf7f2` | Primary surface (warm dirty white) |
| `--ink` | `#1f1f1f` | Text + dark sections |
| `--accent` | `#f8b117` | Buttons, highlights, "solutions." |

The logo lives in `images/` as transparent PNGs recreated with the Fredoka typeface: `hera-logo-dark.png` for light backgrounds (nav) and `hera-logo-light.png` for dark backgrounds (about panel, footer). To swap in the original logo file, replace those PNGs and keep the filenames.

## Editing content

- **Contact email**: `heraecomm@gmail.com` in `index.html` (mailto link and form action).
- **Stats**: hero numbers live in `data-count` attributes on the `.stat__num` elements.
- **Copy**: all text is plain HTML in `index.html`.

## Local preview

```
python3 -m http.server 8000
# open http://localhost:8000
```

# Hera Solutions — Website

Clean, single-page marketing agency website for **Hera Solutions**.

## Stack

Static HTML + CSS + vanilla JavaScript. No build step, no dependencies — deployable as-is to GitHub Pages, Netlify, Vercel, or any static host.

## Structure

```
index.html       # the page (nav, hero, services, work, about, process, contact, footer)
css/style.css    # design system + layout (CSS custom properties at the top)
js/main.js       # mobile nav, scroll reveal, stat count-up, footer year
fonts/           # self-hosted variable fonts (Baloo 2 + Inter, latin subsets)
```

## Brand

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#faf7f2` | Primary surface (warm dirty white) |
| `--ink` | `#1f1f1f` | Text + dark sections |
| `--accent` | `#f8b117` | Buttons, highlights, "solutions." |

The logo is recreated as a text wordmark (`.logo` in `index.html`) using Baloo 2 so it adapts to light and dark sections. To use the real logo file instead, replace the contents of the `.logo` element with an `<img>`.

## Editing content

- **Contact email**: search for `hello@herasolutions.agency` in `index.html` and replace with your address.
- **Stats**: hero numbers live in `data-count` attributes on the `.stat__num` elements.
- **Copy**: all text is plain HTML in `index.html`.

## Local preview

```
python3 -m http.server 8000
# open http://localhost:8000
```

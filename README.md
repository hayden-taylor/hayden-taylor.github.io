# Design for Emerging and Nanoscale Manufacturing: Jekyll site

This folder is a Jekyll version of the PHP site in the parent `online` folder, ready for GitHub Pages. The PHP site is untouched and can stay live on OCF until you switch over.

## What changed from the PHP site

- Every page is plain HTML with a short YAML "front matter" header (title, description, panel title, banner images). The shared header, menu and footer are in `_layouts/default.html` and `_includes/nav.html`, so the menu is edited in one place.
- The research tiles and the Previous/Next project links are generated from `_data/projects.csv` (same columns as `research/projects.csv`; set `Include?` to 1 to show a project). The order of rows sets the order of tiles.
- The OCF logo has been removed from the homepage.
- Accessibility (WCAG 2.1 AA): page language set; skip-to-content link; one `h1` per page with `h2` section headings; alt text on every image (figure images take the first sentence of their caption; decorative banners have empty alt); visible gold focus ring; body text and link colors at 4.5:1 contrast or better (the old grey menu links and 11–13 px text were below that); underlined links; `aria-current` on the active menu item; videos have controls and pause automatically if the visitor has "reduce motion" set; Previous/Next links are no longer fixed over the text; layout reflows to a single column on phones with no sideways scrolling at 320 px.

## One-time setup

1. **Copy the media files.** Double-click `copy-assets.bat`. It copies `images`, `pdf`, `ppt` and `videos` from the parent folder into this one. (They are online-only in OneDrive at the moment, so they couldn't be copied automatically.)
2. **Create a GitHub repository** (e.g. `hkt-website`), and push the contents of this folder to it (GitHub Desktop is the easiest way: File > Add local repository > this folder > Publish).
3. **Turn on Pages:** repository Settings > Pages > Source: "Deploy from a branch", branch `main`, folder `/ (root)`. The site appears at `https://<username>.github.io/<repo>/` within a minute or two.
   - If you view it at that address *before* adding a custom domain, set `baseurl: "/<repo>"` in `_config.yml`; set it back to `""` once the custom domain is live.
4. **Custom domain:** register the domain (a `.com` or `.org` is safer than `.io`). In Settings > Pages > Custom domain, enter e.g. `www.haydentaylor.org`; GitHub will add a `CNAME` file. At your registrar add:
   - `CNAME` record: `www` → `<username>.github.io`
   - `A` records for the bare domain: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   Then tick "Enforce HTTPS". Optionally, put a redirect from the old OCF address to the new one in the PHP `index.php`.

## Research page and banners

- **Themes** (headings, intro sentence and three square images on the Research page) are in `_data/themes.yml`.
- **Topics** are rows of `_data/projects.csv`: a row appears under the theme named in its `Theme` column when `Include?` is 1, in row order. The Previous/Next links on topic pages follow the same order.
- **Banner and order editor:** double-click `tools/banner_editor.bat` (or run `python tools/banner_editor.py` from this folder). It opens a page in your browser where you can choose a page, move images from `images/` into or out of its banner, reorder them and save, and, on the second tab, reorder topics, change their theme and show or hide them. Banner images are 240, 480 or 720 pixels wide and should add up to 720. Commit and push the changed files afterwards as usual.
- People and Publications use folding sections (`<details class="fold">`); add `open` to a section to have it start unfolded.

## Editing

- **Text on a page:** edit the corresponding `.html` file below the front matter.
- **Add a research project:** copy an existing project page (e.g. `OTEC.html`), change its front matter and text, add a 240 × 240 px thumbnail to `images/`, and add a row to `_data/projects.csv`.
- **Menu:** `_includes/nav.html`. **Styles:** `assets/css/site.css`.

## Previewing locally (optional)

Install Ruby (rubyinstaller.org, with DevKit), then in this folder run `bundle install` once and `bundle exec jekyll serve`, and open http://localhost:4000.

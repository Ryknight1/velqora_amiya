# VelQora frontend

Plain HTML + CSS + vanilla JavaScript (no framework, no build step).

* `pages/index.html` – the original landing page; the input card now submits real research.
* `pages/briefing.html` – full one-page briefing (all 10 sections, printable).
* `pages/signin.html` – optional sign in / create account.
* `assets/css/` – the original stylesheet split into `variables / global / animations / components / responsive`
  (same rules, same cascade order). New rules at the end of `components.css` only style new elements/states.
* `assets/js/api.js` – the single API client. `auth.js` session + nav link. `research.js` form → polling → render.
  `briefing.js` card + full-page rendering (everything escaped). `app.js` helpers + the original parallax/scroll code.

Serve it with FastAPI (recommended, see the root README) or any static server, e.g.
`python -m http.server 5500` from this folder, then open `/pages/index.html`.

What changed in `index.html` versus the original: the `<style>`/`<script>` blocks became files; the Sign In link points
to `signin.html`; each input gained a transparent real `<input>` laid over the original text span (the demo typing
still plays on load but never starts research); one hidden line for error messages was added.

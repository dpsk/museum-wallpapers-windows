# Privacy policy — Museum Wallpapers

Museum Wallpapers does not collect, store or send any personal information.
There are no accounts, no analytics, no advertising and no telemetry.

To find and show paintings, the app connects only to Wikimedia services:
`commons.wikimedia.org`, `upload.wikimedia.org`, `www.wikidata.org`,
`query.wikidata.org` and `*.wikipedia.org`. These requests carry a
User-Agent naming the app and nothing about you. Wikimedia's own privacy
policy applies to them: https://foundation.wikimedia.org/wiki/Policy:Privacy_policy

If Windows is set to find a proxy automatically or to use a setup script,
the app asks Windows which proxy to use (Windows may look it up on your
network) and sends its Wikimedia requests through that proxy, as a browser
would.

The app checks Wikimedia's certificates with Windows' own verifier, so
Windows may itself download a missing root or intermediate certificate (from
Windows Update or the certificate authority), as it does for any browser.

Everything the app keeps stays on your computer: its settings, the
downloaded paintings and a log file in the app's folder, and the paintings you
save in `Pictures\Museum Wallpapers`. Uninstalling the app removes all of it
except your saved paintings.

Questions: https://github.com/dpsk/museum-wallpapers-windows/issues

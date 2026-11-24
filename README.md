# Antik TV for Kodi

A Kodi add-on for Antik TV in Slovakia and the Czech Republic. This fork is
based on [waladir/plugin.video.antik](https://github.com/waladir/plugin.video.antik).
The original community support thread is on
[XBMC-Kodi.cz](https://www.xbmc-kodi.cz/prispevek-antik-tv--13396).

## Features

- Search the archive by programme title. Search covers visible channels and
  their configured archive retention, or 14 days when retention is unknown.
- Show available programme artwork from Antik in live TV, archive listings and
  XMLTV. Artwork URLs are cached for 20 days; the first lookup or EPG generation
  can take longer.
- Show station logos in channel lists and use them in generated M3U and XMLTV.
  A configured Picons server takes precedence.
- Add archive programmes to the optional Stream Saver add-on through their
  context menu.
- Estimate the archive start position from stream duration minus the EPG
  programme duration. This is only an estimate: it may leave advertisements or
  skip content. It applies to short programmes too, does not remove ad breaks
  and does not affect downloads. The option can be disabled in add-on settings.
  Kodi's resume request takes precedence over the estimated start.

## Installation

Install the add-on in Kodi's add-ons directory as `plugin.video.antik`, enable
it in Kodi and configure your Antik credentials in the add-on settings.
Do not share your Kodi profile or `userdata/addon_data/plugin.video.antik`:
they may contain credentials, session tokens and other private data.

Station logos are not included. To obtain them, use **Settings → Update station
logos** in the add-on. The updater downloads SVGs from Antik and converts them
to PNG using ImageMagick (`magick` in `PATH`, or
`C:\Program Files\ImageMagick\magick.exe`). The current updater is intended for
Windows. When a local logo is missing, channel lists use the default image;
IPTV exports fall back to Antik's logo URL when available.

Regenerate the playlist and XMLTV after updating logos. Local logo paths refer
to the device where they were generated; use a Picons server when the files
need to be shared with another device.

## Remote archive search

The add-on uses Kodi's existing JSON-RPC interface; it does not run a separate
web server. Enable Kodi's HTTP remote control and use a `Files.GetDirectory`
request with a URL-encoded query:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "Files.GetDirectory",
  "params": {
    "directory": "plugin://plugin.video.antik/?action=search_archive&query=Example",
    "media": "video",
    "properties": ["title", "plot", "genre", "file"]
  }
}
```

Use the `file` from a result with `Player.Open` to start it in Kodi. Available
programme metadata is passed to the player. Configure authentication for Kodi's
HTTP interface and avoid exposing it directly to the internet.

## Tests

The tests use Python's standard `unittest` runner and mock Kodi APIs:

```text
python -m unittest discover -s tests -p "test_*.py"
```

The add-on depends on the Kodi add-ons listed in `addon.xml`.

## License

GPL-3.0; see [LICENSE.txt](LICENSE.txt).

# LLSS Protocol — Minimal Additive Extension

Backward-compatible additions to the existing poll-based protocol. Nothing
existing changes shape; every new field is optional. The canonical contract is
`llss_openapi.yaml`; this note summarizes the additions and the reasoning.

## Why no "partial frames" on the wire

Partial *transport* (sending only changed regions over HTTP) was considered and
rejected. Over good WiFi the cost is dominated by request round-trips to the
cloud server, not by bytes: a mono 800×480 frame is a few KB as PNG (48KB raw
worst case), so one full fetch is ~1 RTT, while splitting into N region fetches
is ~N RTTs — usually *slower*. And all of this network time (tens of ms) is
dwarfed by the panel refresh waveform (~600ms partial, ~2s full).

The only "partial" that saves real time is the **panel partial-refresh
waveform**, which is a device-local decision (the SSD1677 diffs internally
against its stored frame). It needs no region data on the wire. So: **the server
always sends one whole image.**

## Feature 1: Button-label strips baked into the frame

The display reserves a fixed-height strip at the top and/or bottom for button
labels. The server renders those strips **into the full frame image**; the device
just blits the whole image. The strip heights are part of the device contract.

- `DisplayCapabilities.top_strip_height` (optional, added in extension): pixels
  reserved at the top for the label strip. 0 / absent = none.
- `DisplayCapabilities.bottom_strip_height` (optional, added in extension): pixels
  reserved at the bottom. 0 / absent = none.
- Usable content height = `height - top_strip_height - bottom_strip_height`.

Both strips carry user-facing buttons (the bottom strip's 8 app buttons; the top
strip's user buttons — it also hosts device-local buttons the server does not
label). No button labels travel as JSON; they are pixels in the rendered frame.

## Feature 2: Optional pressed-state strip fetch (press feedback)

For instant feedback when a button is pressed, the device MAY fetch a strip
rendered with its buttons in the *pressed* visual state, then blit the pressed
slice locally without waiting for the next server frame.

- `GET /devices/{id}/frames/{frame_id}?strip=top_pressed` → top strip, pressed.
- `GET /devices/{id}/frames/{frame_id}?strip=bottom_pressed` → bottom strip, pressed.

Returns an image of height = the corresponding strip height. Tied to `frame_id`
so the labels match the current frame; the device re-fetches when the frame
changes if it wants fresh pressed art.

This is entirely optional and device-driven. If the device doesn't fetch it, or
the user presses before it is cached, the device can improvise locally (e.g.
invert the pressed button) — that fallback is **not part of this protocol**.
Users rarely click fast enough for it to matter.

## HLSS → LLSS: HLSS renders everything

HLSS owns all rendering. On each frame it uploads to LLSS
(`POST /instances/{id}/frames`, `multipart/form-data`):

- `file` (required): the **whole** display image — content plus both button
  strips already drawn in.
- `top_pressed` / `bottom_pressed` (optional): the strips rendered with their
  buttons in the pressed state, for device press-feedback.

LLSS stores these and serves them unchanged: the whole image on the normal frame
fetch, the pressed strips on `?strip=top_pressed|bottom_pressed`. **LLSS may diff
successive frames internally** (to skip an identical frame, or pick a refresh
hint) but never splits the image on the wire — the device always gets a whole
image.

## Button grid (fixed contract)

- **Bottom strip:** 8 slots, `BTN_1..BTN_8`, left → right.
- **Top strip:** 8 slots, but only the **outer two on each side are usable**
  (slots 1–2 and 7–8) = the 4 user buttons `ENTER`, `ESC`, `HL_LEFT`, `HL_RIGHT`.
  The middle 4 top slots are not usable and are left blank.
- 12 usable buttons total, matching the device's physical layout. All forward to
  LLSS as `InputEvent`s (`HL_LEFT`/`HL_RIGHT` are consumed by LLSS for instance
  cycling). The device-local UI (menu/clock) is reached via long-press, not via
  separate buttons.

## Mapping decisions

1. **No partial transport, no `regions`, no `?region=N`.** One whole-image fetch.
   See "Why no partial frames" above. The panel waveform is the real cost and is
   device-local.
2. **Button labels are rendered into the image, not sent as JSON.** Keeps the
   device dumb (no label rendering needed on-device) and keeps the wire to images.
3. **Pressed strips are a separate optional GET**, not pushed and not split per
   button — one strip image per fetch, cached and sliced by the device.

## Compatibility notes

- **v1 device → extended LLSS:** device omits `top_strip_height`/`bottom_strip_height`
  (default 0), so LLSS reserves no strips and renders content full-height, exactly
  as before. Device never calls `?strip=` and just fetches whole frames.
- **Extended device → v1 LLSS:** a v1 LLSS ignores unknown registration fields and
  doesn't implement `?strip=`; the device still gets whole frames and falls back to
  local press feedback. Degrades gracefully.
- **`?strip=` on a frame with no such strip** (height 0): server returns 404 /
  empty; device simply doesn't use pressed-strip feedback for that strip.
- Strip heights are advisory layout contract: if a device reports heights the
  server doesn't honor, the worst case is cosmetic (mismatched strip area), never
  a protocol break.

# Quetzal design system

The visual language for Quetzal — the mascot, palette, type, and UI tokens. It governs the local
management console (`quetzal ui`) and any Quetzal-branded surface. All tokens live as CSS custom
properties in [`quetzal/ui/static/styles.css`](../quetzal/ui/static/styles.css) `:root`; change the
theme there and the whole console follows.

## Brand

Quetzal is the feathered serpent — *asks · judges · reports*. The mark is a single continuous line
forming the serpent's body as an infinity/`S` loop, feathered crest above, rendered in an ink-navy →
green gradient. It reads as "one continuous loop": run → score → report.

- **Mark:** the serpent glyph alone. Used as the app/tab icon and the console topbar
  ([`quetzal/ui/static/quetzal-mark.png`](../quetzal/ui/static/quetzal-mark.png), transparent PNG).
- **Logo:** mark + `quetzal` wordmark (lowercase, geometric sans). Used on the repo README
  ([`assets/quetzal-logo.png`](../assets/quetzal-logo.png)).
- **Wordmark:** always lowercase `quetzal`, in ink navy.
- **Clearspace:** keep padding ≥ the height of the mark's eye around the logo. Don't recolor,
  stretch, add effects, or place the gradient mark on a busy background.

## Color

Sampled from the mascot. Navy is the ink; the teal→green gradient is the one accent.

### Brand
| Token | Hex | Use |
|-------|-----|-----|
| `--navy` | `#183054` | ink: wordmark, headings, active tab, primary dark surfaces |
| `--navy-deep` | `#0f2340` | deeper navy for hovers/emphasis |
| `--teal` | `#1c8a7c` | gradient start; `--info` |
| `--green` | `#12a06e` | primary accent; selection borders; charts; `--success` |
| `--green-bright` | `#17c07d` | gradient end; accent hover |
| `--green-tint` | `#e4f5ee` | selected-row / active background |
| `--green-glow` | `rgba(18,160,110,.18)` | primary-button shadow |
| `--brand-gradient` | `135deg, teal → green-bright` | primary buttons, the reviewed toggle |

**The accent is the gradient, not a flat color.** Primary actions carry `--brand-gradient`; navy
carries structure (bars, active nav). Use green sparingly for state (selected, success, the trend
line) so it stays meaningful.

### Neutral (cool slate)
`--gray-50 #f4f6f8` · `100 #e9edf1` · `200 #dce2e9` · `300 #c7d0da` · `400 #9aabb9` ·
`500 #68798a` · `600 #3f4f5e` · `700 #2b3947` · `800 #1c2733` · `900 #121b25`.

Semantic roles: `--bg #f4f6f8`, `--surface #ffffff`, `--text #16293f`, `--text-muted #68798a`,
`--border #dce2e9`.

### Status
`--success #12a06e` · `--error #c0392b` · `--warning #c77d0a` · `--info #1c8a7c`.
Difficulty chips: easy = green, medium = amber, hard = red (tinted background + darker text).

## Typography

- **UI font:** **Manrope** (400/500/600/700/800), loaded from Google Fonts. Geometric,
  slightly rounded — echoes the wordmark while staying legible at body sizes.
- **Mono:** `source-code-pro`, Menlo, Consolas — for ids, code roots, and case ids.
- **Scale (console):** page title 20px/800, panel headings 15–16px/800, body 14px, labels &
  chips 11–12px uppercase 0.04–0.05em tracking, muted meta 12–13px. Headings use `-0.02em`
  letter-spacing.

## Tokens: radius, shadow, spacing

- **Radius:** `--radius-sm 6px` (controls, chips), `--radius 8px`, `--radius-lg 12px` (panels,
  modals, cards).
- **Shadow:** `--shadow-sm` (panels/resting), `--shadow-md` (raised), `--shadow-pop` (modals,
  toast) — all tinted navy `rgba(16,41,63,·)`, never neutral black.
- **Spacing:** 4px base; common steps 6/8/10/12/16/20/24. Panel padding 18px; page gutters 24px.

## Components

- **Topbar / brand:** white surface, 1px bottom border, sticky. Brand = mark (26px) + `quetzal`
  (navy, 800) + a divider and muted sub-label.
- **Tabs:** ghost by default (muted); **active = navy fill, white text**.
- **Buttons:** `.btn` neutral outline on surface; **`.btn-primary` = `--brand-gradient`, white,
  green glow**; `.btn-ghost` borderless muted; `.btn-danger` reveals error red on hover. Primary
  lifts 1px on hover.
- **Sidebar suites:** selectable rows; **active = `--green-tint` bg + `--green` border**; count in
  muted mono-ish meta.
- **Table:** uppercase muted headers, 1px `--gray-100` row separators, `--gray-50` row hover.
- **Chips:** difficulty (easy/medium/hard tints above); `.chip.tag` = navy fill, white.
- **Reviewed toggle:** off = `--gray-300` track; **on = `--brand-gradient`**.
- **Modal:** `--surface`, `--radius-lg`, `--shadow-pop`, navy-tinted scrim; inputs use
  `--gray-300` borders, focus to `--gray-500`.
- **Score cards:** panels; big 28px/800 number; hover border → `--green`.
- **Trend chart:** grid `--gray-100`, axis text `--gray-500`, line + points + area gradient in
  `--green (#12a06e)`.
- **Toast:** `--gray-900` fill, white, `--shadow-pop`, bottom-center.

## Changing the theme

Everything routes through `:root` in `styles.css`. To restyle, edit those tokens (not the
component rules). The two chart colors mirrored in `quetzal/ui/static/app.js` (`#12a06e` line/points,
`#e9edf1`/`#68798a` grid/axis) are the only hardcoded values — keep them in sync with the tokens.

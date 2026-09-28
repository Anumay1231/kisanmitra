# KisanMitra design system

The web UI follows these tokens. Colours live as CSS variables in `frontend/src/index.css`.
The style is a friendly fintech look: sage canvas, white cards, one lime accent, heavy display type.

## Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| canvas | `#e8ebe6` | `#0e0f0c` | Page background |
| card | `#ffffff` | `#1c1f1a` | Cards. The contrast with the canvas is the elevation (no shadows) |
| card-2 | `#f3f5f1` | `#151713` | Inset areas inside cards (tool trace, figures, lists) |
| ink | `#0e0f0c` | `#e8ebe6` | Headings and main text |
| body | `#454745` | `#c3c8bf` | Paragraphs |
| mute | `#5d605b` | `#a3a8a0` | Captions (passes WCAG AA on canvas and card) |
| lime | `#9fe870` | `#9fe870` | The only accent: primary actions (send, work out EMI), logo mark |
| pos / pos-bg | `#054d28` / `#e2f6d5` | `#8fdc9f` / `#16261a` | Success, "Ready", high confidence, headline figure |
| warn / warn-bg | `#4a3b1c` / `#fff3c4` | `#ffd978` / `#2a2412` | Demo mode, failed tools, data gaps |
| neg / neg-bg | `#a72027` / `#fde8e8` | `#ff9a94` / `#2e1414` | Errors, low confidence |

Rules: lime is never used as a success colour and never sits on a green background. One accent only.

## Type

- Display: Manrope 800 (headlines, card titles, key figures). Tight tracking.
- Body: Inter 400/600. Numbers use tabular figures.
- Hero headline 48 to 60 px, card titles 18 to 20 px, body 16 px, captions 12 to 14 px.

## Shape and spacing

- Cards and primary buttons: 24 px radius. Pills and icon buttons: full radius. Inputs: 12 px.
- 4 px base grid. Card padding 20 to 24 px.

## Motion

Only fades and small slides on new messages and the tool trace. Everything respects `prefers-reduced-motion`.

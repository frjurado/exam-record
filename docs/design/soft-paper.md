# Soft Paper — WikiAnálisis design system

Palette: **Sage on Cream**. Applies to every page (`base.html`, `index.html`, `discipline.html`, `event.html`, `wizard.html`, partials).

Stylesheet: `app/static/css/wikianalisis.css`. It replaces the Tailwind 2 CDN link. All classes are prefixed `wa-`.

Reference markup: `docs/design/reference/*.html`. These are static pages that use the same stylesheet. Each Jinja template should produce the same markup.

---

## 1. Principles

- Warm paper background, white cards, one accent colour (sage). Nothing else is coloured unless it shows state.
- The serif (Fraunces) is for names: titles, years, work titles, nicknames. The sans (Inter) is for everything else.
- Italic serif marks the "human" part of a title: *Análisis*, *vivo*, nicknames such as *«Patética»*.
- Consensus state comes from a coloured dot plus text. Never colour alone.
- Avoid drop shadows on content. Hairline rules (`--wa-rule`) and 1px borders do the separating.

## 2. Tokens

### Colour

| Token | Value | Use |
|---|---|---|
| `--wa-bg` | `#F3EEE3` | Page background |
| `--wa-bg-soft` | `#ECE6D8` | Breadcrumb bar, stats strip, toggle track, disabled |
| `--wa-card` | `#FFFFFF` | Cards, rows, inputs |
| `--wa-card-verified` | `#FCFAF2` | Verified work card |
| `--wa-ink` | `#2A2722` | Primary text |
| `--wa-ink-soft` | `#4A463E` | Lede, secondary body |
| `--wa-muted` | `#6F685A` | Meta text, labels (4.9:1 on bg) |
| `--wa-faint` | `#8A8373` | Arrows, separators, placeholders only. Not for text that must be read |
| `--wa-rule` | `#DCD4C2` | Borders, dividers |
| `--wa-accent` | `#4A6A4E` | Links, primary buttons, verified state |
| `--wa-accent-hover` | `#3E5A42` | Primary button hover |
| `--wa-accent-soft` | `#DCE3D4` | Pills, chips, resolved banner, hover fill |
| `--wa-warn` / `--wa-warn-soft` | `#9A5A3A` / `#F1E1D6` | Disputed state |
| `--wa-danger` | `#9A3A2E` | Flagged-for-review, form errors, flag hover |

Note: `--wa-muted` is a little darker than the prototype (`#8A8373` → `#6F685A`) so small meta text passes WCAG AA. The old value is kept as `--wa-faint` for non-text decoration.

### Type

| Role | Family | Mobile | Desktop (≥720px) |
|---|---|---|---|
| Hero title | Fraunces 500, lh 1.05, −0.025em | 46px | 84px |
| Page title (discipline) | Fraunces 500 | 32px | 44px |
| Page title (event) | Fraunces 500 | 32px | 56px |
| Region title | Fraunces 500 | 26px | 36px |
| Verified work title | Fraunces 500 | 22px | 28px |
| Work title | Fraunces 500 | 17px | 20px |
| Year number | Fraunces 500 | 22px | 28px |
| Lede | Inter 400, lh 1.55 | 15px | 19px |
| Body | Inter 400 | 15px | 15px |
| Meta / composer | Inter 400 | 12–13px | 13–14px |
| Group label | Inter 500, uppercase, +0.04em | 11px | 12px |
| Badge | Inter 600, uppercase, +0.08em | 11px | 11px |

Inputs use 16px on mobile so iOS doesn't zoom on focus.

### Spacing, radius, layout

- Spacing scale: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 (`--wa-s1`…`--wa-s9`).
- Radius: 3px for cards and buttons, 6px for banners and modals, pill for chips and toggles. Nothing is rounder than that.
- Content column: 900px max. Gutter 20px on mobile, 24px on desktop.
- Single breakpoint: **720px**. The CSS is mobile-first, so styles outside a media query are the mobile ones.
- Minimum tap target: 44px (`--wa-tap`). Desktop buttons are 40px.

## 3. Components

| Component | Classes | Replaces |
|---|---|---|
| Header | `wa-header`, `wa-logo`, `wa-logo__dot`, `wa-meta`, `wa-meta__email` | top bar in `base.html` |
| Breadcrumbs | `wa-crumbs`, `wa-crumbs__sep`, `[aria-current]` on the last item | `{% block breadcrumbs %}` nav |
| Hero | `wa-hero`, `wa-hero__title`, `wa-hero__lede`, `wa-stats` | index intro |
| Region | `wa-region`, `wa-region__head`, `wa-region__title`, `wa-pill` | blue region card |
| Discipline grid | `wa-group`, `wa-group__label`, `wa-disc-grid`, `wa-disc`, `wa-disc__hint`, `wa-disc__arrow`, `wa-disc--disabled` | blue buttons, "Próximamente" |
| Features | `wa-features`, `wa-feature`, `wa-feature__icon`, `wa-feature__title`, `wa-feature__text` | three icon cards |
| Footer | `wa-footer` | about section |
| Page head | `wa-pagehead`, `wa-pagehead--event`, `wa-pagehead__title`, `wa-pagehead__sub` | h1 blocks |
| Toggle | `wa-toggle`, children with `aria-current="true"` | sparse-mode switch |
| Year row | `wa-years`, `wa-year`, `wa-year--empty`, `__num`, `__work`, `__composer`, `__status`, `__imslp`, `__arrow` | `partials/year_list.html` |
| Status | `wa-status`, `--verified`, `--disputed`, `--neutral` | coloured badges |
| Banner | `wa-banner`, `--resolved`, `--disputed`, `__icon`, `__title`, `__text` | `partials/event_status_banner.html` |
| Work card | `wa-works`, `wa-work`, `--verified`, `--disputed`, `__badge`, `__title`, `__nick`, `__composer`, `__meta`, `__flagged`, `__actions` | `partials/work_card.html` |
| Buttons | `wa-btn` + `--primary`, `--ghost`, `--quiet`, `--chosen`, `--sm`; `:disabled` | all buttons |
| IMSLP chip | `wa-chip` | IMSLP links |
| Disclosure | `wa-disclosure`, `__toggle` (`aria-expanded`), `__caret`, `__body` | "Ver otras opciones" |
| CTA / note | `wa-cta`, `wa-cta__title`, `wa-note` | contribute block, "Ya has votado" |
| Empty state | `wa-empty`, `__title`, `__text` | "No hay datos todavía" |
| Load more | `wa-loadmore`, `wa-spinner` | load-more button and spinner |
| Toast | `wa-toast` | green success banner |
| Modal | `wa-modal`, `__backdrop`, `__panel`, `__title`, `__text`, `__actions` | both Alpine modals, auth modal |
| Form | `wa-field`, `wa-label`, `wa-hint`, `wa-input`, `wa-error` | wizard and auth inputs |

### Button mapping in `work_card.html`

- Not participated: `wa-btn wa-btn--primary` "¡Yo también!"
- Your choice: `wa-btn wa-btn--chosen` with `disabled`, "✓ Tu elección"
- Participated elsewhere: `wa-btn wa-btn--ghost` with `disabled`, "Participado"
- Flag: `wa-btn wa-btn--quiet` with text "Marcar incorrecto" (the custom SVG goes away), `hx-confirm` stays as it is

## 4. Desktop vs mobile

| Element | Mobile (<720px) | Desktop |
|---|---|---|
| Header | Logo + version + Salir. Email hidden | Email shown |
| Hero | Left-aligned. Stats stack vertically | Centred. Stats in one row |
| Discipline grid | 1 column, full-width 44px rows. "sin datos" hint inline after the name | 5 columns, equal-height boxes. Hint on its own line under the name |
| Features | Stacked | 3 columns |
| Page head | Title above toggle | Title and toggle on one row |
| Year row | `64px │ work + composer + status │ →`. Status sits under the composer. IMSLP chip wraps below | `100px │ work │ IMSLP │ status │ →` |
| Empty year | "Contribuir" button under the year | Button right-aligned |
| Work actions | Stacked full-width buttons | Inline |
| Modal | Bottom sheet, respects safe area | Centred dialog |
| Toast | Bottom, full width minus 16px | Bottom centre |

## 5. Behaviour that stays the same

All HTMX attributes (`hx-post`, `hx-target`, `hx-swap`, `hx-swap-oob`, `hx-confirm`), Alpine state (`x-data`, `x-show`, `@click`), element IDs (`report-{id}`, `year-{year}`, `consensus-banner`, `exam-history-list`, `load-more-container`, `loading-spinner`, `show-empty-toggle`) and the JS in `discipline.html` stay unchanged. Only classes and wrapper markup change.

The `year-{year}` ID must stay on the outermost element of each row, because `loadMoreYears()` reads it.

## 6. Migration checklist

1. Add `app/static/css/wikianalisis.css`.
2. In `base.html`, remove the Tailwind CDN `<link>` and add `<link rel="stylesheet" href="/static/css/wikianalisis.css">`. Keep Alpine and HTMX.
3. Add `<style>[x-cloak]{display:none}</style>` handling. The stylesheet already includes it, so use `x-cloak` instead of inline `style="display:none"`.
4. Rewrite each template to match its reference page in `docs/design/reference/`.
5. Remove all remaining Tailwind utility classes (`grep -rn 'class="[^"]*\b\(bg\|text\|px\|py\)-' app/templates`).
6. Check at 375px and 1280px: no horizontal scroll, every tap target at least 44px on mobile.

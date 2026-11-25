---
name: FitShot
description: A lookbook photo desk where every catalog photo carries its inspection.
colors:
  cobalt: "#2b35f5"
  cobalt-deep: "#1b23c4"
  accent: "#2b35f5"
  accent-dark: "#c8ff2e"
  volt: "#c8ff2e"
  volt-deep: "#b2ec0f"
  on-volt: "#0e0e10"
  on-cobalt: "#ffffff"
  card: "#ffffff"
  card-ink: "#0e0e10"
  card-soft: "#4d4d57"
  card-line: "#e2e2e6"
  stamp-pass: "#0f5438"
  stamp-fail: "#8f1d17"
  stamp-check: "#8a5600"
  card-error: "#fff5f4"
  field-line: "#8f8f99"
  field-line-dark: "#6b6b78"
  mat: "#e6e6e4"
  pass: "#176b49"
  check: "#8a5600"
  fail: "#b3261e"
  pass-dark: "#63cda2"
  check-dark: "#f0b860"
  fail-dark: "#ff9288"
  paper: "#ffffff"
  paper-2: "#f1f1ef"
  field: "#f7f7f5"
  line: "#e0e0e3"
  line-strong: "#b9b9c1"
  ink: "#0e0e10"
  muted: "#5c5c66"
  action: "#0e0e10"
  action-ink: "#ffffff"
  paper-dark: "#0d0d10"
  paper-2-dark: "#17171b"
  field-dark: "#121216"
  line-dark: "#2b2b32"
  line-strong-dark: "#4a4a55"
  ink-dark: "#f4f4f6"
  muted-dark: "#a3a3af"
  action-dark: "#f4f4f6"
  action-ink-dark: "#0e0e10"
typography:
  masthead:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "1.75rem"
    fontWeight: 900
    lineHeight: 0.9
    letterSpacing: "-0.03em"
    fontVariation: "'wdth' 150"
  card-masthead:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "1.625rem"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 150"
  display:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "clamp(2.25rem, 1.5rem + 2.2vw, 3.75rem)"
    fontWeight: 850
    lineHeight: 0.94
    letterSpacing: "-0.035em"
    fontVariation: "'wdth' 140"
  figure:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "2.25rem"
    fontWeight: 850
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: '"tnum"'
    fontVariation: "'wdth' 125"
  headline:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "1.875rem"
    fontWeight: 850
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontVariation: "'wdth' 130"
  title:
    fontFamily: '"Anybody Variable", "Arial Black", sans-serif'
    fontSize: "1.5rem"
    fontWeight: 820
    lineHeight: 1.45
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 125"
  lede:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.45
  summary:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "1.0625rem"
    fontWeight: 620
    lineHeight: 1.35
  body:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
  nav:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "1rem"
    fontWeight: 560
    lineHeight: 1.45
  control:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "0.9375rem"
    fontWeight: 650
    lineHeight: 1.45
  label:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "0.8125rem"
    fontWeight: 700
    lineHeight: 1.45
  status:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "0.78rem"
    fontWeight: 680
    lineHeight: 1.45
  burst:
    fontFamily: '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif'
    fontSize: "0.6875rem"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "0.04em"
rounded:
  sharp: "2px"
  square: "0px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "30px"
  gutter: "40px"
components:
  button-primary:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.sharp}"
    padding: "9px 18px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-cobalt}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.sharp}"
    padding: "9px 18px"
    height: "44px"
  button-outline-hover:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-ink}"
  button-small:
    rounded: "{rounded.sharp}"
    padding: "5px 12px"
    height: "36px"
  button-approve:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-cobalt}"
    typography: "{typography.control}"
    rounded: "{rounded.sharp}"
    padding: "9px 18px"
    height: "44px"
  button-approve-hover:
    backgroundColor: "{colors.cobalt-deep}"
    textColor: "{colors.on-cobalt}"
  button-try-on:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-cobalt}"
    rounded: "{rounded.sharp}"
    padding: "9px 18px"
    height: "52px"
    width: "100%"
  button-try-on-hover:
    backgroundColor: "{colors.cobalt-deep}"
    textColor: "{colors.on-cobalt}"
  button-card-outline:
    backgroundColor: "transparent"
    textColor: "{colors.card-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.sharp}"
    height: "44px"
  button-card-outline-hover:
    backgroundColor: "{colors.card-ink}"
    textColor: "{colors.card}"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.sharp}"
    padding: "6px 14px"
    height: "38px"
  chip-selected:
    backgroundColor: "{colors.action}"
    textColor: "{colors.action-ink}"
  chip-compact:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.sharp}"
    padding: "4px 12px"
    height: "34px"
  look-tag:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-soft}"
    rounded: "{rounded.sharp}"
    padding: "1px 7px"
  look-tag-pass:
    backgroundColor: "{colors.card}"
    textColor: "{colors.stamp-pass}"
  look-tag-fail:
    backgroundColor: "{colors.card}"
    textColor: "{colors.stamp-fail}"
  status-pass:
    textColor: "{colors.pass}"
    typography: "{typography.status}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  status-check:
    textColor: "{colors.check}"
    typography: "{typography.status}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  status-fail:
    textColor: "{colors.fail}"
    typography: "{typography.status}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  status-idle:
    textColor: "{colors.muted}"
    typography: "{typography.status}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sharp}"
    padding: "8px 12px"
    height: "44px"
  rail:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-cobalt}"
    padding: "26px 16px 18px"
    width: "240px"
  rail-link:
    typography: "{typography.nav}"
    rounded: "{rounded.sharp}"
    padding: "9px 12px"
    height: "44px"
  rail-link-active:
    backgroundColor: "{colors.on-cobalt}"
    textColor: "{colors.cobalt}"
  inspection-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-ink}"
    rounded: "{rounded.sharp}"
    padding: "0 22px 20px"
    width: "400px"
  inspection-masthead:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.on-cobalt}"
    typography: "{typography.card-masthead}"
    padding: "14px 14px 14px 22px"
  check-word-pass:
    textColor: "{colors.stamp-pass}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  check-word-check:
    backgroundColor: "{colors.card-ink}"
    textColor: "{colors.card}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  check-word-fail:
    backgroundColor: "{colors.stamp-fail}"
    textColor: "{colors.card}"
    rounded: "{rounded.sharp}"
    padding: "1px 8px 1px 6px"
  photo-tile:
    backgroundColor: "{colors.mat}"
    rounded: "{rounded.sharp}"
  evidence-panel:
    backgroundColor: "{colors.paper-2}"
    rounded: "{rounded.sharp}"
    padding: "18px"
  evidence-panel-in-card:
    backgroundColor: "{colors.mat}"
    rounded: "{rounded.sharp}"
    padding: "8px"
  empty-state:
    backgroundColor: "{colors.paper-2}"
    rounded: "{rounded.sharp}"
    padding: "30px 34px"
  form-panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "22px"
  studio-panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "18px"
  stage:
    backgroundColor: "{colors.mat}"
    rounded: "{rounded.sharp}"
  stage-flag:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-ink}"
    rounded: "{rounded.sharp}"
    padding: "8px 12px"
  table-head:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "12px 16px"
  cost-figure:
    textColor: "{colors.ink}"
    typography: "{typography.figure}"
  cost-figure-lead:
    textColor: "{colors.accent}"
    typography: "{typography.figure}"
---

# Design System: FitShot

## Overview

**Creative North Star: "The Lookbook Photo Desk"**

FitShot is a fashion lookbook's photo desk on a 60/30/10 color split: white paper and the neutral photo mat (60%), cobalt (30%) and volt lime (10%), with big photographs first. Pages open on a magazine cover line set in Anybody at extreme width, over a borderless grid of 3:4 photos laid on a neutral grey mat. Every photo carries its inspection, and opening one brings up a white Inspection card with a cobalt masthead and a cover-burst sticker that states the verdict in a word. The system refuses the grey SaaS dashboard where quality checks shrink into a badge; here the check is the second-largest object on the screen after the photo.

The home page is the Fitting room: a four-step flow (person, garment, AI model, review) under a step bar, ending in a result view that sets the before and after photos side by side beside the Inspection card. The rail leads with the three main sections (Fitting room, Models, Results), then the studio tools.

The density is editorial rather than tabular: generous 30px row gaps between photos, one cover line per page, hairline rules instead of boxes. Where the work is numeric (shoots list, costs, forms) the desk turns crisp: ruled tables and panels under a 3px ink top rule, tabular figures, square corners. The personality is premium but funky. The funk lives in four places only: the expanded display type, the starburst sticker, the cobalt, and the volt that marks what to press and where you are. Everything a person reads or operates is set calmly in Bricolage Grotesque.

Two themes share one desk. Light and dark flip only the paper, ink and lines. The cobalt rail, the white Inspection card, the photo mat and the burst tones are physical objects and stay identical in both, so a photo is judged against the same ground whatever the theme. Motion is small and print-like: a sticker slaps on with a spin, the card rises 10px, a photo leans in 3.5% on hover, and all of it collapses under reduced motion.

The direction contract named the card "The Edit"; the build titles it **Inspection**, and the build is the record.

**Key Characteristics:**
- A 60/30/10 split, re-pinned by the user on 2026-11-25: 60% white paper and the neutral mat, 30% cobalt (#2b35f5) on the rail, the Inspection masthead, selected chips and light-theme selection, 10% volt lime (#c8ff2e) on the two committing actions, the current page and the stickers.
- Volt is always a filled shape carrying ink. It is never text or a hairline on white, where it is unreadable.
- Anybody Variable at 125 to 150% width and weight 820 to 900 for covers; Bricolage Grotesque for the work.
- Photos sit only on the neutral mat, paper or paper-2, never tinted.
- Status is always a word with an icon; color only reinforces it.
- 2px corners on everything handled; square ruled containers under a 3px ink top rule.
- One lifted object: the Inspection card. Everything else is flat.

## Colors

A white-and-ink desk on a 60/30/10 split: white paper and the photo mat carry about 60% of every screen, cobalt about 30%, volt lime about 10%. A fixed white card set holds the inspection, and quiet status inks never travel without a word.

### Primary
- **Rail Cobalt** (#2b35f5), the 30%: the navigation rail (and the phone bottom bar), the Inspection card masthead, selected chips (scene, model, generators, filters), primary-button hover, the progress fill, the logo-marking box, and the stage and side-by-side "View large" hover. It is also the browser theme color.
- **Volt** (#c8ff2e), the 10%: the two committing actions (Try it on and Approve photo) as volt fills with ink type and an ink edge, the current page tab on the rail and phone bar, the review count, empty-state bursts, the photo-added check on the photo cards, the skip link, text selection, and the pale volt wash behind a "learned" note and a "Still needed" line (30% volt mixed into the ground). On the committing actions hover inverts to an ink fill with volt type.
- **Pressed Volt** (#b2ec0f): reserved for a pressed volt fill.
- **Focus Accent** (#2b35f5 light, #c8ff2e dark): focus outlines, the selected-photo outline (3px, 4px offset), selected look cards, looks-strip and queue thumbnails, picked garments, field and search focus borders, the row chevron on hover, the caret, and the lead figure on Costs. It turns volt in dark, where volt on ink paper reads at about 16:1. On the rail and inside the card, focus is drawn in white and cobalt respectively.
- **On Cobalt** (#ffffff): every text and icon on cobalt. **On Volt** (#0e0e10): every text and icon on volt.

### Secondary
The fixed card set. These never change with the theme because the Inspection card is a white object in both.
- **Card White** (#ffffff): the Inspection card ground, the idle burst fill, and the fixed white ground of look tags and the stage flag that sit on photos.
- **Card Ink** (#0e0e10): card text, outline buttons on the card, the "Check" result chip fill and the "needs your check" burst.
- **Card Soft** (#4d4d57): measured scores, "Not run" results and the card footnote.
- **Card Rule** (#e2e2e6): the card's border and the hairlines between check rows.
- **Stamp Green** (#0f5438): the Verified and Approved burst, "Pass" results on the card, and the Approved flag on model shots.
- **Stamp Red** (#8f1d17): the Rejected and Failed burst, the "Fail" result chip, card error notes and the Rejected flag on model shots.
- **Photo Mat** (#e6e6e4): the ground under every photo, the Fitting room stage, look cards, looks-strip and queue thumbnails, product images, picked garments and the evidence panel inside the card. Same in both themes.

### Tertiary
Status inks for words on paper. Each flips with the theme for contrast.
- **Pass Green** (#176b49, dark #63cda2): Verified and Approved pills, completed setup steps.
- **Check Amber** (#8a5600, dark #f0b860): "Needs your check" pills, the "N need you" table marker, and the setup-banner warning icon.
- **Fail Red** (#b3261e, dark #ff9288): Rejected and Failed pills, error notes on paper.

### Neutral
- **Paper** (#ffffff, dark #0d0d10): page ground and form panels.
- **Paper Two** (#f1f1ef, dark #17171b): empty states, the in-page evidence panel, the setup banner, table-row hover, skeletons.
- **Field** (#f7f7f5, dark #121216): inputs and selects, the logo preview placeholder.
- **Hairline** (#e0e0e3, dark #2b2b32): table rows, panel sides, chip and field borders, cost-line dividers, the progress track.
- **Strong Hairline** (#b9b9c1, dark #4a4a55): table header underline, quiet-button borders, setup-step rules, field hover, the scrollbar.
- **Ink** (#0e0e10, dark #f4f4f6): text, outline-button borders, the 3px top rule on tables, panels and the cost line.
- **Muted** (#5c5c66, dark #a3a3af): page ledes, table heads, field help, unselected chips, cost labels.
- **Action** (#0e0e10 on #ffffff text; dark #f4f4f6 on #0e0e10): primary buttons, selected chips and the outline-button hover fill. It inverts with the theme so the primary button is always the strongest neutral.

### Named Rules
**The 60/30/10 Rule.** Neutral paper and the photo mat carry about 60% of a screen, cobalt about 30% (structure: rail, masthead, selection), volt about 10% (what to press and where you are). No third brand hue is added. Neither hue marks status (Verified stays deep Stamp Green with its word, so volt never reads as "pass"), and neither fills a photo ground.

**The Volt Is A Fill Rule.** Volt appears only as a filled shape carrying ink, or on cobalt and ink grounds. It is never text, a hairline or an outline on white or the mat, where it falls to about 1.1:1.

**The Fixed Objects Rule.** The rail, the Inspection card, the photo mat and the burst tones are objects, not theme surfaces. Only paper, ink, lines and status inks flip between light and dark.

**The Neutral Mat Rule.** Photos sit only on the mat (#e6e6e4), paper or paper-2, never on cobalt or a status color, and are never tinted, filtered or overlaid. The single exception is a source shot standing in for a photo still being generated: it is ghosted (35% opacity, greyscale) and always carries an in-progress word (Queued, Checking, or the stage flag's "Dressing the model and checking the photo").

## Typography

**Display Font:** Anybody Variable (with Arial Black, sans-serif)
**Body Font:** Bricolage Grotesque Variable (with Segoe UI, system-ui, sans-serif)

**Character:** Anybody at expanded widths reads like a fashion-magazine cover line, wide, black and tightly tracked; Bricolage Grotesque is a warm, slightly quirky grotesque that keeps the working text human and plain. Both load from @fontsource-variable in the app entry; the build sets width with `font-stretch`, which maps to the `wdth` axis recorded in the tokens.

### Hierarchy
- **Masthead** (Anybody 900, 1.75rem, 150% width, line-height 0.9, -0.03em, uppercase): the FITSHOT wordmark on the rail (1.375rem on phones). Tracking opens to 0.01em on hover over 300ms.
- **Card Masthead** (Anybody 900, 1.625rem, 150% width, line-height 1, -0.02em, uppercase): INSPECTION on the card's cobalt head.
- **Display** (Anybody 850, clamp(2.25rem, 1.5rem + 2.2vw, 3.75rem), 140% width, line-height 0.94, -0.035em, balanced wrap): the page cover line, one per page, sentence case ("Studio photoshoot", "Costs").
- **Figure** (Anybody 850, 2.25rem, 125% width, line-height 1, -0.03em, tabular): the four cost-line numbers; 1.75rem on phones.
- **Headline** (Anybody 850, 1.875rem, 130% width, line-height 1, -0.03em): empty-state headlines. The model name on Brand models uses the same voice at 1.75rem.
- **Title** (Anybody 820, 1.5rem, 125% width, -0.02em): section titles such as "By garment". Compact empty states drop to 1.375rem; Fitting room column heads ("Your garments", "Shoot settings") are 1.3rem at 850, line-height 1.1.
- **Lede** (Bricolage 400, 1.0625rem, muted): the sentence under a page title; also the photo name on the card.
- **Summary** (Bricolage 620, 1.0625rem, line-height 1.35): the plain-language verdict sentence on the Inspection card.
- **Body** (Bricolage 400, 1rem, line-height 1.45): base text. Explanatory paragraphs hold to 52 to 72ch.
- **Nav** (Bricolage 560, 1rem; 720 when current): rail links. Phone bar labels drop to 0.6875rem 650 with short names.
- **Control** (Bricolage 650, 0.9375rem): buttons; chips are 0.875rem 650, small buttons 0.8125rem.
- **Label** (Bricolage 700, 0.8125rem): field labels and table headers, sentence case, no tracking.
- **Status** (Bricolage 680, 0.78rem): status pills; card result chips are 0.8125rem 720.
- **Burst** (Bricolage 800, 0.6875rem, +0.04em, uppercase, line-height 1.08): the word inside a starburst; 0.71rem on the card stamp, 0.875rem in full empty states.

### Named Rules
**The Two Voices Rule.** Anybody is reserved for covers: mastheads, page titles, section and panel heads, empty-state headlines, the model name and cost figures, always at 125 to 150% width and weight 820 to 900. Everything a person reads closely or operates is Bricolage Grotesque.

**The Uppercase Budget Rule.** Uppercase appears only in the FITSHOT masthead, the INSPECTION card masthead and burst words. Titles, labels, table heads and buttons are sentence case with no added tracking.

**The Tabular Money Rule.** Counts, money and scores use tabular numerals (cost figures, table numbers, chip counts, the review count, measured scores) so columns of figures align.

## Layout

The shell is a two-column grid: a 240px sticky cobalt rail at full viewport height, and the desk. Pages pad 36px top, 40px sides and 56px bottom; the page head aligns the cover line left and its one primary action right, bottom-aligned, with 30px below. Costs uses a narrow page capped at 1060px. A setup banner, when needed, sits above the page inset 40px.

The Fitting room (the home route, first in navigation) is one column: the page head, the step bar, and one step panel at a time (Paper ground, hairline sides, 3px ink top rule, 22px padding). Each panel ends in a step foot: Back at left, the reason a step is blocked and Continue at right. The review step is a two-column grid (the person and garment photos on the mat, then the summary and the model's settings). The result is a grid of the before and after photos (3:4 on the mat) with a 380px Inspection column, sticky 20px from the top. Results uses the discovery grid with a 400px detail column. Models lays out model panels in 360px-minimum columns.

Work pages that inspect photos become a workspace: the page plus a docked Inspection card in a 400px column, sticky at the top with its own scroll (36px top, 28px right padding). The discovery grid auto-fills 212px minimum columns with dense packing and 30px row by 20px column gaps; the photo dominates, the caption is one line beneath it. At 1280px and wider the first photo is featured, spanning two columns and two rows. Catalog garments use 250px columns, model shots 210px, the garment picker 134px with a 360px scroll cap.

Recurring spacing steps are 8, 12, 16, 20, 30 and 40px (see tokens); the build writes them as literal values rather than variables. Primary controls stand at 44px.

Responsive changes:
- **1360px and below:** Fitting room columns narrow to 232px catalog and 340px side, 22px gaps.
- **1180px and below:** rail narrows to 212px, page gutter to 30px, docked card to 376px. The Fitting room catalog becomes a full-width row above the stage and side column, its look cards a horizontal scroller of 128px columns.
- **1040px and below:** the Fitting room becomes a single column (stage, then catalog, then side), the side column stops being sticky, the card's actions are no longer sticky, and the stage is capped at 72% of the viewport height (680px). On workspace pages the dock disappears and the card opens as a modal dialog up to 470px wide over a 62% ink backdrop, from a tapped photo or, on Review, from an "Open inspection" primary button in the page head. The dialog always shows the evidence photos.
- **760px and below:** the shell stacks. The rail becomes a sticky cobalt top bar holding the masthead and an icon-only theme toggle; navigation moves to a fixed cobalt bottom bar of five equal 52px targets (Try on, Models, Results, Review, More), padded for the safe area; More opens a page listing the other studio tools. Pages pad 24px, 16px gutters, 32px bottom. Photo, shot, people and catalog grids become two columns with 22px by 12px gaps. The review grid, result and Results detail stack into one column. Tables hide secondary columns, the cost line becomes 2 by 2, form panels go single-column with full-width submit buttons, and empty states stack.

## Elevation & Depth

The desk is flat. Depth comes from ruled lines (a 3px ink top rule over hairlines), tonal steps between paper, paper-2 and the mat, and the fixed objects that keep their color across themes. Exactly one surface is lifted: the Inspection card, which rests on the desk like a print with a long, soft under-shadow. (The Fitting room's stage flag also carries a small shadow; that is recorded as drift below, not as vocabulary.)

### Shadow Vocabulary
- **Card rest** (`box-shadow: 0 30px 50px -34px rgb(14 14 16 / 0.45)`): the Inspection card only, docked or in the dialog.
- **Logo mark ring** (`box-shadow: 0 0 0 1.5px #fff, inset 0 0 0 1.5px #fff`): white halo around the 2px cobalt logo-marking box so it reads over any garment.
- **Picked ring** (`box-shadow: inset 0 0 0 1.5px var(--accent)`): doubles the accent border on a chosen garment in the picker.
- **Dialog backdrop** (`rgb(14 14 16 / 0.62)`): behind the Inspection dialog on narrow screens.

### Named Rules
**The One Lifted Card Rule.** Only the Inspection card casts a shadow. Panels, tiles, tables, chips and buttons are flat; hierarchy among them comes from rules, tone and type, never from elevation.

## Shapes

Corners are a crisp 2px on everything a person handles: buttons, chips, fields, status pills, photo tiles and their images, evidence panels, empty states, notes, the rail links and the Inspection card. Containers that hold rows of data are square and ruled: form panels, Fitting room studio panels, tables and the cost line carry a 3px ink top rule and 1px hairlines elsewhere, and the progress bar is a square 6px track. Control borders are 1.5px; dividers are 1px.

The one free shape is the cover burst: an 18-point starburst (outer radius 50, inner 42 on a 100-unit box), filled flat, rotated -8 degrees as the card stamp and -10 degrees in empty states. Photos are 3:4 portrait in grids, thumbnails and the featured tile; garment images are square and contained on the mat; evidence images are contained at their own ratio.

## Components

### Buttons
Square-shouldered and inky; the only color appears on hover or on Approve.
- **Shape:** 2px corners, 1.5px border, 44px tall, 9px by 18px padding, 8px icon gap, Control type.
- **Outline (default):** transparent with ink text and ink border. Hover fills with Action and inverts the text.
- **Primary:** Action fill with Action Ink text, one per page head or form foot. Hover turns cobalt with white text, the moment cobalt enters the page.
- **Press:** every button drops 1px on active over 120ms.
- **Try it on:** the Fitting room's committing action. Full width of the Shoot settings panel, 52px tall, 1rem 650, a volt fill with ink type, an ink edge and a Sparkles icon; hover inverts to an ink fill with volt type. When disabled it stays volt at 40% opacity, and the line beneath it says what is blocking it.
- **Small:** 36px, 5px by 12px, 0.8125rem, used on model-shot cards. **Quiet:** the outline button with a Strong Hairline border, for the secondary choice beside it.
- **Disabled:** 40% opacity, no hover change, not-allowed cursor, and a title explaining what unlocks it.
- **Icon button:** 40px square, transparent, paper-2 hover on paper and 15% white on cobalt.
- **Upload as button:** a label styled as the outline button wraps a visually hidden file input and shows the focus ring on focus-within.

### Chips
- **Style:** filter chips and segmented choices share one look: 38px, 6px by 14px, transparent with muted text and a 1.5px hairline border, 2px corners, an optional tabular count at 80% opacity.
- **State:** hover darkens text and border to ink. Pressed or current fills with cobalt and white text, part of the 30%. They are used for photo filters, scene tabs, the garment-source switch and the model switcher.
- **Compact:** 34px, 4px by 12px, 0.8125rem, 6px gaps and no bottom margin, for Fitting room category and scene chips. A disabled chip (a scene with no approved shot) drops to 40% opacity.

### Status Pills
- **Style:** a word with a 14px icon, Status type, 1.5px border in currentColor, 2px corners, transparent ground. Pass Green for Verified and Approved, Check Amber for Needs your check, Fail Red for Rejected and Failed, Muted for Queued and Checking (the Checking icon spins).
- **Related marks:** the "N need you" marker in tables is the same outlined form in Check Amber; model-shot flags (Approved, Rejected) are the same form on a white ground in the stamp inks, pinned 10px into the photo's corner. Look tags in the Fitting room catalog are the small version of that flag (0.6875rem 720, 1px by 7px, pinned 7px into the corner): a fixed white ground and currentColor border with a word ("Verified", "Approved", "Needs check", "Rejected", "Failed", "Trying on", "Not tried") in Stamp Green, amber, Stamp Red or Card Soft. Because the ground is fixed white, they use the fixed card inks rather than the theme-flipping status inks.

### Cards / Containers
- **Studio panel:** the Fitting room's version of the form panel: Paper ground, 1px hairline sides, 3px ink top rule, square corners, 18px padding, 14px gap, with a 1.3rem Anybody head. It holds Shoot settings (model select when there is more than one, compact scene chips, pose and generator selects two-up, the Try it on button and a help line) and, before a garment has been tried on, an "On the model" panel showing the garment on the mat beside its name.
- **Form panel:** Paper ground, 1px hairline sides, 3px ink top rule, square corners, 22px padding, 20px internal gap. The head pairs an Anybody title (1.5rem) with a 40px close icon; the foot right-aligns the primary button beside any error. A two-column variant places a 280px preview (the logo marker on the mat, or a dashed placeholder) beside the fields.
- **Empty state:** Paper Two ground, 2px corners, up to 700px wide, 30px by 34px padding, a volt burst with an ink word (112px, -10 degrees) with a one-word mark ("Start", "Go", "Clear", "Add", "Cast", "Shoot"), an Anybody headline, one muted sentence (52ch) and one next step. A compact level shrinks the burst to 88px. The first-run variant lists setup steps on Strong Hairline rules, finished steps struck through with a pass check.
- **Setup banner:** Paper Two with a hairline border, 2px corners, amber warning icon and one plain sentence.
- **Error note:** Fail Red text and 1.5px border with a warning icon on paper; inside the card it uses Stamp Red on a pale red ground.

### Inputs / Fields
- **Style:** Field ground, 1.5px hairline border, 2px corners, 44px tall, 8px by 12px padding. Selects drop the native arrow for a 14px grey chevron 13px from the right. File inputs carry an ink outline "choose" button. Checkboxes are 18px and take the cobalt accent color.
- **Label:** Label type above, 6px gap, optional 0.75rem muted help below.
- **Hover / Focus:** hover raises the border to Strong Hairline; focus turns it Focus Accent with a 2px accent outline at 2px offset.
- **Layout:** fields auto-fit in rows of 200px minimum (170px for four-up, 260px for two-up) with 16px gaps.
- **Search:** a 44px field-tone box with a 2px corner, a 16px muted search icon and a borderless input inside; the whole box takes the accent border and outline on focus-within.

### Navigation
- **Cobalt rail:** full-height cobalt column, 26px by 16px padding, 30px gaps: the FITSHOT masthead, the nav, a one-line rail note, and the theme toggle at the foot (outlined in 50% white, filled 12% white on hover).
- **Order:** the three main sections, Fitting room (Sparkles, short label "Try on", home), Models (Cpu) and Results (Images); then, under a hairline rule, the studio tools as slightly shorter 38px links: People, Garments, Photoshoots, Review, Costs. The masthead links to the Fitting room.
- **Links:** 44px rows with a 19px icon, 80% white text, 2px corners. Hover lifts to full white on a 12% white wash. The current page becomes a volt tab with ink text at weight 720.
- **Review count:** a volt 24px badge with ink tabular figures that inverts to volt figures on an ink badge when its link is the current volt tab.
- **Phone bottom bar:** at 760px and below the links become a fixed cobalt bar of five equal 52px columns (Try on, Models, Results, Review, More) with icon over short label; the count rides the icon's top right.
- **Back link:** muted 0.9375rem with a left arrow above the page title, underlined on hover.

### Photo Tile and Discovery Grid
Borderless photos on the mat with a caption beneath: the SKU in bold, the pose, and the status pill at the right (stacked under the name on phones). The whole tile is one button. Hover leans the image in to 103.5% over 700ms on the expo-out curve; selection draws a 3px Focus Accent outline 4px off the photo. Loading tiles are Paper Two blocks that pulse at 1.4s. At 1280px and up the first tile spans 2 by 2 and its name steps up to 1.0625rem.

### Fitting Room: Step Bar, Panels and Result
- **Step bar:** four equal steps (Person, Garment, AI model, Review), each a button under a 3px top rule with a 26px numbered mark. Done steps take a cobalt rule and a cobalt mark with a check and can be clicked to go back; the current step takes an ink rule and a volt mark with ink figures; later steps are muted and disabled until the earlier ones are done.
- **Person tabs:** two large tabs, Live and Built-in models, an Anybody name over a one-line note; the selected tab carries a 3px cobalt underline.
- **Mode cards:** Full body and Half body as radio cards with a person icon (cropped for half body); the chosen card takes a cobalt border and inset ring. A Paper Two guide box below lists what the photo needs.
- **Upload box:** a dashed Strong Hairline box with a 3:4 preview on the mat, a title, help, and Choose a photo, Take a photo and Remove buttons; dragging over turns the border cobalt on a faint cobalt wash, and a filled box turns its border solid ink.
- **Person cards:** 3:4 photos on the mat with the name and a Full body or Half body tag; the chosen card takes a 3px Focus Accent outline and a volt check square in its corner.
- **Choice cards:** category, photo-type and AI-model choices share one radio-card look (Strong Hairline border, cobalt border and inset ring when chosen, 50% opacity and the reason in the note when incompatible).
- **Review:** the person and garment photos on the mat, then a ruled summary (3px ink top rule, a muted label column) and the chosen model's settings as range sliders with tabular values. Generate try-on is the volt committing action.
- **Result:** before and after 3:4 frames on the mat; while the look is being made the person photo stands in, ghosted under the Neutral Mat Rule, with the white stage flag naming the model and the elapsed seconds. Actions (View large, Download, Different settings, Another model, Another garment) sit below; the Inspection card sits at right without its evidence panel.

### Inspection Card (signature)
A white print laid beside the grid, identical in both themes.
- **Frame:** Card White, 1px Card Rule border, 2px corners, the card-rest shadow, 22px side padding. It rises 10px into place over 420ms when a photo is opened.
- **Masthead:** a full-bleed cobalt bar with INSPECTION in the card masthead type and a white close icon when it is a dialog.
- **Cover:** the photo's SKU and pose at left, the burst stamp at right: 104px, rotated -8 degrees, spinning in from -60 degrees at 55% scale over 520ms and re-stamping whenever the status changes. Burst tones: green (Verified, Approved), red (Rejected, Failed), ink (Needs your check), white with an ink outline (Queued, Checking). The burst word is the full status label.
- **Summary:** one plain sentence in Summary type naming the problem or the outcome.
- **Evidence:** "Real product" beside the generated photo on the mat (8px padding and gap), with a link to the full-size image.
- **Check rows:** eight ruled rows (Garment color, Pattern, Logo, Structure, Face, Skin tone, Body, Hands), 40px each, separated by Card Rule hairlines. Each shows a result chip: "Pass" in Stamp Green text, "Check" as Card Ink fill, "Fail" as Stamp Red fill, "Not run" in Card Soft, every one with its icon. A row expands with a turning chevron to the plain-language result, and the measured score sits one line below in Card Soft tabular figures.
- **Actions:** a sticky white footer (not sticky in the single-column Fitting room at 1040px and below), a 1.25 to 1 grid: volt **Approve photo** with ink type and an ink edge (hover inverts to ink with volt type) beside card-ink outline Reject and Retry, or Undo when a decision exists. On the card, focus outlines are cobalt.
- **Footnote:** attempts and spend, then the standing disclosure "Check limits are still being tuned, so use your own eye too." It is always present.

### Cover Burst
The 18-point starburst carries a word, never stands in for one. Tones: green, red, ink and white-outline on the card; volt in empty states. Fill is flat, the word is white (ink on the white and volt tones), uppercase Burst type, centered within 70% of the width.

### Evidence Panel and Queue Strip
On Review the evidence is a page-level panel: Paper Two, 18px padding, 20px gap, two figures with images contained and capped to the viewport height, bold 0.8125rem captions. Under it the queue strip scrolls horizontally: 120px 3:4 thumbnails on the mat with SKU and pose beneath, the current one outlined in Focus Accent.

### Tables
Square and ruled: a 3px ink top rule, a 1px hairline bottom, Label-type muted headers over a Strong Hairline, 15px by 16px cells divided by hairlines, Paper Two row hover. Numbers right-align in tabular figures. Whole rows link: the row is clickable, the focus ring is drawn on the row inset 2px, and the trailing chevron nudges 3px right and turns accent on hover. A "Spent" footnote under a hairline closes the job page.

### Cost Line
Four figures in a ruled strip: 3px ink top rule, hairline bottom and dividers, muted 0.8125rem labels over Figure-type numbers. The first figure, cost per accepted photo, is the only one in Focus Accent. On phones it becomes 2 by 2 at 1.75rem. The traditional-photoshoot comparison below it is always labeled as an estimate.

### Progress
A square 6px Hairline track with a cobalt fill that eases its width over 250ms while a shoot runs.

## Do's and Don'ts

### Do:
- **Do** keep the 60/30/10 split: neutral paper and mat for most of a screen, cobalt (#2b35f5) for the rail, the Inspection masthead, selected chips, primary hover, progress and light-theme selection, volt (#c8ff2e) for Try it on, Approve photo, the current page, the review count and empty-state bursts.
- **Do** lay every photo on the mat (#e6e6e4), paper or paper-2 at its true color, with 3:4 tiles in grids.
- **Do** pair every status with its word: pills, card result chips, burst stickers, shot flags, look tags, the stage flag and table markers all carry text, and pills and result chips add an icon.
- **Do** keep the provisional-limits disclosure on every Inspection card and on the brand-model face-match note, keep the "does not predict real size or fit" line under Try it on, and label the photoshoot comparison as an estimate.
- **Do** keep volt actions to the two that commit work, Try it on and Approve photo; every other action is ink.
- **Do** set covers in Anybody at 125 to 150% width and weight 820 to 900, and everything operational in Bricolage Grotesque.
- **Do** use 2px corners on handled things and square, 3px-ink-topped rules on tables, the cost line, form panels and studio panels.
- **Do** keep the rail, the Inspection card, the mat and the burst tones identical in light and dark.
- **Do** collapse every animation and transition to 1ms under prefers-reduced-motion.

### Don't:
- **Don't** introduce a third brand hue, use cobalt or volt to mean pass, fail or warning, or set volt as text, a hairline or an outline on white.
- **Don't** place a photo on cobalt or a status color, or tint, filter or overlay a generated photo; only an in-progress source shot may be ghosted.
- **Don't** signal a status by color alone, or let an unverified photo look verified.
- **Don't** set Anybody for body, labels or buttons, or uppercase anything beyond the two mastheads and burst words.
- **Don't** add shadows to anything but the Inspection card.
- **Don't** round corners past 2px or put the burst to work as decoration without a word in it.
- **Don't** make the cost figures or the Inspection card change color with the theme.

### Known drift (not canonized)
Recorded from the build and left unrepaired. None of these is a rule for new surfaces.
- The select chevron is an inline SVG stroked with a literal #8a8a95, because a data URI cannot read a token. It reaches about 3:1 on both field grounds.
- In the Fitting room side column the volt Try it on and the volt Approve photo can be on screen together when a look needs a check, so the one committing action is not singular there.
- Small buttons (36px) and compact chips (34px) stay below the 44px used by icon buttons, chips and fields.
- CSS class names still say "slip" (for example `.slip`, `.slip-dock`), a leftover from the retired world. The visible masthead and the accessible names say Inspection.

Repaired on 2026-11-24: untokened literals now use `card`, `card-soft`, `stamp-check` and `card-error`; the stage flag lost its shadow and gained a `card-line` border; the review count uses 2px corners; chip counts are at full strength; panel heads share one style (1.375rem, 850, 125% width); icon buttons are 44px and chips 40px; field and search borders use `field-line`, which reaches 3:1.

Re-pinned on 2026-11-25 by the user: the single-cobalt rule became a 60/30/10 split with volt lime (#c8ff2e) as the 10%. Cobalt kept the structure, volt took the committing actions, the current page and the stickers, and the two side-bordered notes (the learned note and the "Still needed" line) became volt washes.

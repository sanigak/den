# Responsive layout

Doc ID: `responsive_layout`

## Shared layout

The viewport follows the device width and leaves browser zoom enabled. Main
content uses Bootstrap's container breakpoints and matching 15px grid gutters,
with safe-area padding for screen cutouts. Long text wraps within cards and
flex children. Page-wide horizontal clipping must not conceal overflow defects.

Navigation is sticky and participates in document layout, including when its
mobile menu expands. Below 992px it can scroll within the viewport on short
landscape screens. The footer follows the content, with flex layout placing it
at the bottom of short pages; it never covers form actions. There is one main
landmark, supplied by the base template.

Fields have automatic height and a minimum height of 44px, allowing their text
and padding to fit. Touch and narrow-screen fields retain a 1rem font size.
Buttons, form actions, and modal footers wrap. Touch and narrow-screen buttons
have a minimum height of 44px. Modals scroll vertically and retain close, Escape,
focus trapping, restoration, and background inertness from `ui.js`. Selects use
a consistent CSS arrow and ellipsis so WebKit's native control cannot create
horizontal overflow from long option names; the native choice menu still works.

`DenModal.open(element, trigger = document.activeElement)` accepts the initiating
control explicitly. Click handlers provide it because some browsers do not focus
clicked buttons. Closing the modal restores focus to that control; automatic
open callers retain the existing default.

## Calendar

The month always has seven equal columns using `repeat(7, minmax(0, 1fr))`.
Cells and meal badges can shrink; long recipe names use ellipses within the cell.
Day numbers and weekday headings remain visible. Below 401px, the month heading
has its own navigation row. Top actions wrap when they cannot fit side by side.

Every populated date has a native `.day-open` button. Clicking, tapping, Enter,
or Space opens the existing meal modal with the full planned name, including
skip and empty-plan descriptions. Past dates display information only. Today
and future dates offer the recipe picker, Save, and a full-size Skip day button.
Desktop hover shortcuts remain available; below 992px or on touch/no-hover
devices those small shortcuts are hidden in favor of opening the full day.

`openSwapModal(cell, trigger)` reads the date, recipe ID, and editability from the selected
calendar cell. It resets the picker and all modal controls on each opening,
copies the meal name with `textContent`, and disables hidden write controls for
past dates. Selecting an unassigned/skip date resets the recipe picker to its
first option instead of carrying a previous day's selection forward.

The existing swap and skip POST endpoints, date bounds, CSRF tokens, skip
confirmation, and scheduling behavior are unchanged. The selected date goes
through the existing hidden date fields. The calendar script also accepts the
empty-recipe screen, where meal modals and date inputs are absent.

## Other screens

Home cards retain two columns on phones, with complete descriptions and wrapping
buttons. Mascot animation respects reduced-motion preferences. Shopping items
wrap long content while preserving the Remove button. Recipe forms wrap their
actions; recipe names and ingredients wrap even without spaces.

The projects summary retains its six-column table, with horizontal scrolling
inside its labeled, keyboard-focusable region. A narrow-screen hint makes that
scrolling discoverable. Descriptions, comments, and write controls remain on
the detail screen. See `schema/project_screens.csv` and
`schema/responsive_screens.csv` for the screen contracts.

## Verification procedure

Use a fresh isolated development database and synthetic records, including long
unbroken shopping items, recipe names, ingredients, project names, and comments.
Populate a month with generated, manual, skipped, past, and future days. Never
copy household data into the browser fixture. Keep screenshots and runtime
receipts in an ignored development directory.

Review the home, planner, shopping, recipes, recipe add/edit, project list/detail,
and informational pages at 320, 375, 390, 430, 667, 768, 820, 1024, 1280, and
1920 CSS pixels. Include short landscape height, touch emulation, and enlarged
text. Check Chromium, Firefox, and WebKit when available.

Verify all seven calendar headers share a row and fit the viewport; detect page
overflow and clipped form/action content. Open every modal and reach its footer
by scrolling. Read a full meal name, edit a future date, cancel/confirm a skip,
and inspect a past date. Check Enter/Space, Escape, restored focus, the expanded
mobile menu, and scrolling to the table's final column. Check the empty planner
for script errors. Restart the development server after template edits because
template caching remains enabled with DEBUG false.

Run the checks in `CONTRIBUTING.md`. Browser emulation verifies these layouts
and interactions; actual household-device and installed-service checks remain
separate, as described in `hardening-verification.md`.

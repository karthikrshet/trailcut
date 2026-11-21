---
name: ui-component
description: Use when building or changing a screen or component in apps/web. Blade components and tokens first, Lucide icons from react-icons/lu only, all 4 states (empty, loading, error, data), formatINR/formatDate, WCAG AA, 375px, reduced-motion variant and a Vitest test.
---

# UI component

## Rules
- **Blade first.** Use `@razorpay/blade` components (Box, Card, Heading, Text, Badge,
  Table, Drawer, Alert, Skeleton...). Style only through Blade props and tokens.
  No raw hex colours, px font sizes or magic spacing numbers.
- **Icons:** `react-icons/lu` only, for one stroke style. Decorative icons get
  `aria-hidden`; meaningful ones get a label.
- **4 states:** every data view renders **empty, loading (Skeleton), error (Alert with
  one clear next action) and data**. Write the copy in plain language.
- **Numbers:** money via `formatINR()` (full in tables, `compact` in cards), dates via
  `formatDate()`. Never format numbers inline. Never compute money in the UI. It comes
  from the API.
- **Status:** colour is never the only signal. A badge has a word and an icon
  (Switch now = positive, Wait = notice, Keep = neutral).
- **Accessibility:** WCAG AA contrast, keyboard reachable, visible focus, correct roles
  and labels; tables use proper headers.
- **Responsive:** single column under 768 px; must work at 375 px with no horizontal scroll.
- **Motion:** `motion/react`, transform/opacity only, under 1 s, nothing loops but
  skeletons/spinners. With `prefers-reduced-motion`, count-ups jump to the final
  value and staggers become a simple fade (use `useReducedMotion()`).

## Steps
1. Sketch props as a TypeScript type; data comes in already computed.
2. Build the component in `apps/web/src/components/<Name>/<Name>.tsx`.
3. Test in `<Name>.test.tsx` with Testing Library: one test per state, an accessible
   role/name query, INR formatting, and the reduced-motion branch.
4. `pnpm --filter web lint && pnpm --filter web typecheck && pnpm --filter web test`.
5. For new screens, extend the Playwright smoke at 375 px and desktop.
6. Commit `feat(web): ...` with a screenshot in the PR.

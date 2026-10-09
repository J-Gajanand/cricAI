# cricAI design system

## Direction

Premium cricket broadcast, paired with restrained analytical clarity. Original
cricket-stump/ascending-bar mark and cricAI wordmark; no official branding.
Home prioritizes an actual local auction, not marketing, fake stats or future
feature previews. Auction prioritizes player, bid, leader, timer and next action.

## Tokens

| Token | Value |
| --- | --- |
| Canvas / surface | #101214 / #1C2023 |
| Text / muted | #F4F6F7 / #AFB8BD |
| Action green | #45D483 with dark label |
| Intelligence cyan | #67CDE3 |
| Attention amber / error | #FFBE55 / #FF7272 |
| Spacing | 4, 8, 12, 16, 24, 32 logical pixels |
| Item radius / minimum touch | 8 / 48 logical pixels |
| Proposed fonts | Rajdhani display, Barlow body, licensed local assets |

Use tabular numerals for money and timers; stable button and counter dimensions.
No negative tracking, nested cards, giant dashboard headlines or decorative blur.
Use a coherent Material icon family with semantic labels and tooltips. Full-width
sections, thin dividers and deliberate empty space. Portrait absence has an
original intentional placeholder, not a fabricated photograph.

## Interactions

Fixed bid dock on normal phone layouts; reflow accessibly at larger text scale.
History and squad detail use bottom sheets. Actions reflect server state, not
animation completion. Brief price/leader changes respect reduced motion.
Pending bid is not a confirmed bid. Disconnection disables bidding and triggers
resnapshot; no offline queue. Color is never the only status indicator.

## QA gate

Review 360x640 and 412x915 logical pixels, text scales 1.0/1.3/2.0, long names and
money, insets, keyboard, scrolling and accessibility semantics. Verify actual
contrast. Capture home, active auction, sold, unsold, paused, empty/error,
disconnected and summary states from the implementation. Goldens supplement but
do not replace device/emulator screenshots. Record exact device/build/state.
Screenshots not captured must be labeled unverified. No generic placeholder
screen counts as completed UI. Figma sync requires an authorized target file;
no remote design file is created without explicit authorization.
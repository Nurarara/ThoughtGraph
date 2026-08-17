# ThoughtGraph observatory redesign — design QA

## Findings

- No actionable P0, P1, or P2 differences remain in the final comparison.
- [P3] The generated product target depicts a deliberately idealized multi-cluster graph, while the implementation renders the signed-in local user's canonical 25-node graph. The implementation preserves the target's observatory hierarchy, gravity fields, focused-node reticle, technical labels, and evidence panel without inventing relationships or replacing real data with mock content. No fix is recommended.
- [P3] The target's large graph bodies have more complex faceted shading than the interactive canvas nodes. The implementation uses crisp radial mass, rings, and real-time focus states so it stays responsive and truthful at arbitrary zoom. This is an acceptable runtime simplification.

## Comparison setup

- Source visual truth:
  - Landing: `frontend/artifacts/design/selected-landing.png`
  - Product: `frontend/artifacts/design/selected-product.png`
- Browser-rendered implementation:
  - Landing: `frontend/artifacts/design/implementation-landing.png`
  - Product, signed in with a real local graph and a node selected: `frontend/artifacts/design/implementation-product.png`
  - Mobile landing: `frontend/artifacts/design/implementation-landing-mobile.png`
  - Mobile sign-in: `frontend/artifacts/design/implementation-auth-mobile.png`
  - Mobile product: `frontend/artifacts/design/implementation-product-mobile.png`
- Full-view comparisons:
  - `frontend/artifacts/design/comparison-landing.png`
  - `frontend/artifacts/design/comparison-product.png`
- Focused comparisons:
  - `frontend/artifacts/design/comparison-landing-focus.png`
  - `frontend/artifacts/design/comparison-detail-focus.png`
  - `frontend/artifacts/design/comparison-graph-focus.png`
- Viewport and density:
  - Source images: 1487 × 1058 px.
  - Desktop implementation: 1440 × 1024 CSS px at device scale factor 1.
  - Sources were normalized to 1440 × 1024 with Lanczos resampling before side-by-side comparison.
  - Mobile implementation: 390 × 844 CSS px at device scale factor 1. The visual target did not prescribe a mobile frame, so mobile was evaluated as a responsive extension of the desktop system rather than as a pixel-match target.
- State:
  - Landing: signed out, dark observatory theme, idle orbit field.
  - Product: signed in as the local development user, canonical graph loaded, highest-connection node selected, detail panel open.
- Browser: installed Microsoft Edge, driven through the user-approved standalone Playwright check.

## Required fidelity surfaces

- Fonts and typography: IBM Plex Sans and IBM Plex Mono are self-hosted. The final desktop hero uses the target's two-line wrap, tight display tracking, restrained body width, and technical uppercase labels. Long live-data titles use deliberate truncation with the complete thought immediately below.
- Spacing and layout rhythm: the landing retains a strong left-to-right narrative and generous field depth. The product keeps the graph primary, uses one bounded detail rail, and moves secondary actions behind progressive disclosure. Square, low-radius instrument surfaces replace generic cards.
- Colors and visual tokens: near-black blue, cyan, and amber map consistently to environment, orientation, and focus. The target's foreground/background balance, subdued grid, glow restraint, and state contrast are preserved.
- Image and asset quality: the graph is a real interactive canvas, not a substituted screenshot. Phosphor supplies the interface icons, and the generated app icon is delivered as a sharp 512 px raster asset. No target illustration or non-standard icon was replaced with placeholder glyphs, handmade SVG, or decorative CSS blobs.
- Copy and content: the landing establishes curiosity, then explains capture, connection, and evidence before asking for sign-in. Product copy is real user data. Reflection language remains explicitly evidence-based and non-clinical.
- Responsiveness and accessibility: desktop and 390 px mobile captures show no control overlap. Mobile hides nonessential node annotations until interaction, provides 44–48 px targets, and keeps the auth dialog within the viewport. Buttons have semantic labels, fields have visible labels, Escape closes transient surfaces, focus states are visible, and motion respects `prefers-reduced-motion`.

## Comparison history

1. First comparison — blocked.
   - P1: dense graph labels collided around the focused cluster, obscuring the active node.
   - P2: the live detail title dominated the panel and reduced scanability.
   - Fixes: limited focused-neighbour annotation, introduced a technical `FOCUSED NODE` label, shortened the display heading while retaining full content below, and preserved the home viewport when selecting directly on the canvas.
   - Post-fix evidence: `comparison-product.png`, `comparison-detail-focus.png`, and `comparison-graph-focus.png`.
2. Second comparison — blocked.
   - P2: the landing headline wrapped to three lines instead of the target's two, materially changing the hero proportion.
   - P2: the first mobile dialog capture showed the entering transition and excessive panel height.
   - Fixes: made the desktop line break intentional, adjusted the optical scale and width, waited for the modal to settle, and tightened the mobile dialog/backdrop treatment.
   - Post-fix evidence: `comparison-landing.png`, `comparison-landing-focus.png`, and `implementation-auth-mobile.png`.
3. Third comparison — blocked.
   - P2: cluster labels sat inside dense gravity fields, and desktop-level node annotation remained too dense on mobile.
   - Fixes: placed cluster labels above their computed field radius and progressively disclosed mobile node labels only after interaction.
   - Post-fix evidence: `comparison-product.png` and `implementation-product-mobile.png`.
4. Final comparison — passed.
   - No actionable P0/P1/P2 findings remain. Residual differences are the expected consequence of rendering canonical live graph content instead of the target's fictional demonstration data.

## Interaction and runtime checks

- Opened and closed the landing explanation.
- Opened sign-in and entered an email value.
- Selected a real graph node and opened its detail panel.
- Opened Search, Explore, and Capture, then dismissed each.
- Opened the mobile navigation and Capture composer.
- Checked browser console, page errors, and HTTP responses during the scripted journey: zero errors recorded in `frontend/artifacts/design/browser-qa.json`.

## Open questions

- None blocking. A later data-layout project could distribute very large clusters more aggressively, but changing canonical graph geometry was intentionally kept outside this visual-system pass.

## Implementation checklist

- [x] One cohesive landing and product language.
- [x] Progressive sign-in and explanatory journey.
- [x] Spatial canvas motion with inertia, friction, focus, and reduced-motion support.
- [x] Desktop and mobile visual verification.
- [x] Core interactions and error console verification.
- [x] Side-by-side and focused comparison loop completed.

final result: passed

# UX Ideas: Separate Progress (Star Plot) vs Prediction (GPX Strategy)

## High-level take
Your separation makes sense: users have two distinct jobs that currently get mixed:
1) **“Where am I right now / am I improving?”** (Progress + motivation)  
2) **“What can I do on this route and how should I pace it?”** (Prediction + planning)

Treat “analysis” as *infrastructure* (mostly background) and surface only the outcomes users care about: **predicted time**, **confidence**, and **what changed since last time**.

---

## Proposed information architecture (3 surfaces)

### 1) Home = Progress (default landing)
Primary purpose: return value + habit formation.

**Above the fold**
- “Today” card: *current fitness snapshot* (e.g., “This week: improving uphill, stable flat”)
- “Readiness / status” chip: `Fresh` / `Normal` / `Fatigued` + a short “why” (e.g., “high load last 3 days”)
- “Prediction shortcut”: a single input to pick a GPX/route and immediately see a **time range** (not the full planning flow)

**Progress section (Star Plot = hero)**
- Star plot shows **current period vs previous period** overlay by default
- Each axis shows:
  - trend arrow + % change
  - confidence dot (solid = high, hollow = low)
- CTA: “See trends” (weekly timeline) + “Earn next badge” (optional, secondary)

**Feed / highlights**
- “New PR on climbs” / “Downhill improved 6%” / “Low downhill data — try a descent run to improve accuracy”

This makes the star plot a *destination* users want to revisit, not a required step to get predictions.

---

### 2) Predict = route-focused outcome (“What can I achieve here?”)
Primary purpose: plan an attempt on a known route.

**Step 1: Choose a route**
- Upload/select GPX or choose a saved route
- Optionally select a segment within it (start/end markers)

**Step 2: Show predicted outcomes immediately**
Before asking for strategy details, show:
- **Predicted time** (single best estimate)
- **Range** (p10–p90) to represent uncertainty
- **Confidence drivers** (e.g., “high confidence on flat; low on steep downhill due to few samples”)

**Step 3: Strategy builder**
Goal: turn prediction into action.
- Split route into meaningful chunks (automatic: climbs/descents/flats, or user-defined)
- For each chunk:
  - target pace (or speed)
  - expected effort (RPE/HR zone if available)
  - “time gained/lost vs even pace” explanation
- Global knobs:
  - “Conservative / Balanced / Aggressive” pacing preset
  - “Conditions” (heat/wind/trail) as optional modifiers (even if initially manual)

**Step 4: Export / execute**
- “Race plan” summary (splits + key warnings)
- Export as PDF/shareable or “send to watch” later (optional)

This keeps prediction as its own product feature, not a byproduct of calibration.

---

### 3) Analysis = behind-the-scenes + transparency (mostly asynchronous)
Primary purpose: trust + control, not daily usage.

This is where “analysis” lives, but it should be entered intentionally.

**What this screen answers**
- “What data are you using?” (activity coverage, sample counts by grade)
- “What changed my prediction recently?” (new activities → updated snapshot)
- “How accurate has it been?” (if you later log actual vs predicted)
- “Force refresh” controls and troubleshooting (Strava sync, caching)

Key point: users shouldn’t be forced through analysis to get value unless something is missing.

---

## Key UX principle: “Prediction first, calibration quietly”

### Avoid the current funnel
Current: `analysis -> predict time -> starplot -> prediction`

Suggested:
- **Returning user**: `Home (progress) -> Predict (route) -> optional Strategy`
- **First-time user**: `Connect -> minimal baseline -> Home`, with background history processing

Let “analysis” be a background task whose completion improves confidence and unlocks better planning.

---

## First-time user flow (important)
Your plan already mentions bootstrap. UX-wise, make it feel intentional:

1) After Strava connect: ask for **one representative activity** (quick baseline)
2) Immediately unlock:
   - basic star plot (low confidence badge)
   - basic route prediction (wide range)
3) Start background fetch:
   - Show a single progress bar: “Building your performance profile (2–3 min)”
   - Show what the user gets: “Narrower time range, better hill estimates, achievements”

When background completes:
- A “Profile ready” toast
- Star plot now has “confidence improved” indicator

---

## How the star plot becomes *useful* gamification (not decoration)

### Make it answer: “What should I train next to improve predictions and performance?”
For each grade category (uphill/flat/downhill), show two signals:
- **Performance trend** (improvement/decline)
- **Data confidence** (enough samples or not)

Then recommend one of:
- “Train this” (to improve performance)
- “Collect this” (to improve model confidence)

Example: “Downhill: low confidence (3 samples). Add 1 downhill run to tighten prediction range.”

This ties engagement directly to predictor quality without exposing model internals.

---

## Prediction UX details that improve trust

### Always show uncertainty and why
Users accept wrong predictions more when uncertainty is visible and reasoned.
- Time estimate + range
- Confidence explanation:
  - “Most of this route is +8% to +12% climbs; you have strong coverage there”
  - “Steep descents are low confidence; your history has few -15% to -25% samples”

### Surface “fitness vs readiness”
Even with a strong long-term model, daily readiness changes outcome.
Communicate it as:
- “Fitness prediction” (from snapshots)
- “Today adjustment” (from readiness)

Even if readiness is initially simple (recent load heuristic), UX-wise it’s valuable.

---

## Monetization (UX-integrated)

### Principle: “Progress is sticky, Predict is valuable”
- Use **Progress** (star plot + trends + achievements) to create a habit loop and demonstrate value.
- Monetize **Predict** (route planning depth) and **history/confidence tooling**, not basic access to personalization.
- Keep **Analysis/Profile** as a trust-builder that also explains what Pro improves (tighter ranges, better grade coverage).

### Suggested tiers (packaging)

**Free**
- Progress: current vs previous period star plot overlay, basic achievements, simple “improving/stable/declining” callouts
- Predict: predicted time for a chosen route/segment + **wide range**; limited saved routes; no pacing plan
- History depth: last ~4–6 weeks snapshots (or a small fixed number)

**Pro (subscription)**
- Predict: **strategy builder** (route chunking, target splits, conservative/balanced/aggressive presets), multi-scenario “what-if” knobs (readiness/conditions), route library, export/share
- Progress: long trends (3–12 months), goal tracking, advanced achievements
- Profile: grade coverage diagnostics, “what changed my prediction”, optional weekly digest

**Coach/Team (optional higher tier)**
- Multi-athlete dashboards, comparative trends, report exports

### Paywall placement (feels fair)
- Always show a **single best predicted time** for free.
- Gate: detailed pacing plan, exports, long history, multi-scenario comparisons, and deeper confidence diagnostics.
- Avoid hard-gating the star plot itself; instead, gate **depth** (history length, advanced breakdowns).

### High-intent upgrade triggers (where to prompt)
- After route prediction result: “Unlock pacing plan + splits for this route”
- When uncertainty is high: “Unlock history + grade coverage to tighten your time range”
- When saving multiple routes: “Route library is Pro”
- When a milestone/achievement unlocks: “Unlock 12-month trends + goal roadmap (Pro)”

### Monetizable “what-if” knobs (Predict)
These are intuitive and high value, even if initially manual:
- Conditions: heat, wind, trail vs road, altitude
- Readiness: fresh/normal/fatigued adjustment
- Effort target: conservative/balanced/aggressive presets

---

## Navigation suggestion (simple)
- Bottom tabs (or left nav):
  - **Progress** (default) — star plot + achievements + trends
  - **Predict** — routes, time, plan
  - **Profile** (or “Data”) — analysis, sync, confidence coverage

Avoid naming it “Calibration” once it’s ongoing; “Profile” or “Performance” is more intuitive.

---

## Minimal viable UX (MVP) vs next layers

### MVP
- Progress tab:
  - current vs previous star plot overlay
  - trend arrows + confidence dots
- Predict tab:
  - choose route/segment
  - predicted time + range + confidence explanation (text)
- Profile tab:
  - “last updated”, “data coverage by grade”, “refresh” button

### Next layers
- Strategy builder (chunk pacing)
- Achievements + nudges tied to coverage gaps
- Prediction accuracy tracking (actual vs predicted) + calibration quality score

---

## Concrete screens (wireframe-level outlines)

### Progress (Home)
- Header: “This week”
- Card: Predicted “fitness flat pace” + readiness chip
- Star plot: current vs last week + callouts on biggest deltas
- Row: “Uphill / Flat / Downhill” summary chips
- “Build confidence” nudge if needed (low coverage)

### Predict
- Route selector + segment picker
- Result card: time + range + confidence
- Route preview with colored grade sections (optional)
- CTA: “Build pacing plan”

### Profile (Analysis)
- Last snapshot date + next scheduled update
- Coverage histogram by grade
- List of recent activities used
- Buttons: “Refresh from Strava”, “Recompute last 4 weeks”

---

## Product question to decide early (affects UX)
Do you want the star plot to represent:
1) **Performance** (what the user can do), or
2) **Model parameters** (anchor ratios / curve shape)?

For UX, (1) is easier to understand. You can still compute via anchor ratios but label axes in user terms:
- “Steep Uphill”
- “Moderate Uphill”
- “Flat”
- “Moderate Downhill”
- “Steep Downhill”

Users care about “I’m better at climbs now”, not “my +20% anchor ratio changed”.

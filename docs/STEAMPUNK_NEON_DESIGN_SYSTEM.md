# SmartPickShop Steampunk Neon Design System

## Purpose

This document is the reusable visual foundation for the SmartPickShop Holdings portfolio. Cashh Radar is the first production implementation.

**Visual language:** Industrial Steampunk × Electric Neon × Futuristic Workshop  
**Portfolio line:** Ideas today. Empires tomorrow.

## Non-negotiable principles

1. **Function before decoration.** Navigation, information hierarchy, accessibility, responsiveness, and task completion come before ornament.
2. **Real cockpit, not wallpaper.** Product interfaces should feel instrumented: gauges, status signals, radar, evidence, controls, and clear feedback.
3. **Dark metal foundation.** Iron, coal, charcoal, and gunmetal form the base surfaces.
4. **Warm mechanical structure.** Brass and copper define rails, frames, borders, dividers, and industrial details.
5. **Electric information.** Cyan/teal signals active intelligence and verified data. Magenta is a selective energy/alert accent, not a flood fill.
6. **Shared family, distinct products.** Every project inherits the system but gets a project-specific mechanical metaphor.
7. **Proof-aware design.** States such as verified, source-confirmed, stale, blocked, illustrative, pending, and published must remain visually distinct.
8. **Accessible by default.** Maintain keyboard focus, readable contrast, responsive layouts, reduced-motion support, and semantic HTML.

## Core palette

| Role | Token | Value |
| --- | --- | --- |
| Iron background | `--sps-iron` | `#080B0F` |
| Coal surface | `--sps-coal` | `#10151B` |
| Gunmetal | `--sps-gunmetal` | `#202832` |
| Brass structure | `--sps-brass` | `#C58A32` |
| Copper detail | `--sps-copper` | `#B65F35` |
| Neon cyan | `--sps-neon-cyan` | `#39F6FF` |
| Neon magenta | `--sps-neon-magenta` | `#FF3FD1` |
| Ivory text | `--sps-ivory` | `#F4EAD7` |

## Component language

### Shells and panels
- layered dark-metal gradients
- thin brass/copper frame
- restrained inner rim
- occasional corner rivets
- blueprint/radar grid only where it improves context

### Controls
- primary action = warm brass face with bright edge
- active/verified signal = cyan
- warning = amber
- destructive/error = red
- special energy/accent = magenta

### Motion
- use slow radar/pulse motion for live state
- never animate large areas continuously
- honor `prefers-reduced-motion`

## Cashh Radar metaphor

Cashh Radar is a **signal-scanning machine**:
- radar sweep = discovery
- score gauge = ranking
- evidence lights = verification
- cockpit cards = opportunities
- brass rails = structure
- cyan instrumentation = trusted intelligence
- magenta spark = exceptional/high-attention state

## Portfolio mapping

| Project | Mechanical metaphor |
| --- | --- |
| Founder Dynasty OS | command/control room |
| Cashh Radar | radar and signal-scanning machine |
| Promotion Engine | broadcast/transmission engine |
| Trend Labs / Opportunity Lab | experimental research laboratory |
| Founder Console | central industrial control console |
| Same Beat | neon phonograph + synchronization machinery |
| DoubleTap Rewards | arcade reward machinery |
| Fish Shooter Arcade | mechanical underwater arcade world |
| EGM4000 | premium cyber-aquatic analysis console |
| Snarky How To | practical mechanical workshop |
| Blogger / content hub | neon foundry publishing workshop |

## Surface checklist

Every redesign pass should cover, when the project has that surface:

- product UI
- public website
- mobile/tablet layout
- PWA shell
- social profile and post templates
- README/repository presentation
- setup/workflow/QA/launch documentation
- screenshots, thumbnails, banners, OG image, app icons
- desktop and mobile proof

## Rollout rule

Do not mass-repaint every repository blindly. Ship one project at a time:

**Discover → Prioritize → Execute → Verify → Document → Launch → Monitor**

For each project, preserve existing working behavior, create reversible changes on a branch, verify before merging, and record evidence.

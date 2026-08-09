# Research and differentiation

Research date: 8 August 2026.

## Method

The selection process used four checks:

1. Inventory more than 100 existing projects in the local `D:\我的\GitHub` workspace and extract their README descriptions.
2. Search prior project memory for shipped or discussed tools, especially data scanners, maintenance-plan extractors, photo utilities, evidence receipts, and developer tooling.
3. Search GitHub repository names, descriptions, and indexed pages for rental inspection, security deposit evidence, move-in and move-out photo comparison, and condition-report tools.
4. Search public web and community discussions for repeated user pain and existing commercial supply.

The GitHub Search API reached its rate limit during the wider query set, so the conclusion does not rely on an empty result. The broad query returned a highest-ranked directly related repository at three stars: [RentRadar](https://github.com/Jerry2003826/unihack3-13). Indexed GitHub searches were then used as a separate fallback.

## Demand evidence

Official guidance supports the underlying workflow:

- [NSW Fair Trading](https://www.nsw.gov.au/housing-and-construction/rules/rental-property-condition-reports) says a detailed condition report with time-stamped photos reduces disputes and should be kept by both parties.
- [Consumer Affairs Victoria](https://www.consumer.vic.gov.au/housing/renting/rent-bond-bills-and-condition-reports/condition-reports) recommends dating, labeling, and attaching photos to the condition report.
- [UK government renting checklist](https://www.gov.uk/government/publications/how-to-rent/how-to-rent-the-checklist-for-renting-in-england) recommends an agreed inventory and photos at both move-in and move-out.
- A [public community request](https://www.reddit.com/r/SomebodyMakeThis/comments/1r59vfg/a_deadsimple_renters_digital_vault_app_for/) describes the exact pain of scattered photos, weak before-and-after organization, and no easy evidence package.

Commercial tools such as [MoveShield](https://moveshield.app/), [door.lease](https://door.lease/), and [Sealmark](https://getsealmark.com/) further confirm that people pay for structured capture and reports.

## Open-source gap

The closest indexed GitHub result, RentRadar, is a broad AI-assisted pre-lease inspection and decision platform that uses Gemini, Google Maps, Cohere, Qdrant, MiniMax, and hosted infrastructure. It is not a portable evidence verifier.

General photo managers and forensic tools exist, but they do not provide this full narrow chain:

```text
stable room view -> original-byte register -> move-in/out pair -> transparent pixel aid
-> case seal -> printable report -> deterministic bundle -> independent verifier
```

No absolute claim that nobody has ever written similar code is possible. The defensible claim is narrower: the documented search did not find a mature, prominent GitHub project with the same offline evidence-chain scope.

## Why it does not duplicate this workspace

- `data-xray-local` scans files for privacy and metadata risks. It does not organize rental condition evidence or pair visual states.
- `ManualCare` extracts maintenance plans from manuals. It does not process photos or evidence bundles.
- `ShipReceipt` creates software delivery receipts. It does not handle rental inspections or image comparison.
- `PixelPeel` creates UI screenshot diffs. It does not preserve evidence originals, condition slots, or case seals.
- `Camera Halo Fence` and `PromoSift` review media capture quality for other domains.

RoomReceipt introduces a new audience, workflow, data model, verification boundary, and output format.

## Star and visibility hypothesis

No project can guarantee stars. RoomReceipt has a credible discovery path because it combines:

- a broad renter pain point;
- privacy-first local processing;
- a live sample report;
- a one-command verifier;
- deterministic fixtures that contributors can trust;
- clear legal and technical limitations instead of AI damage claims;
- GitHub topics spanning rental, tenant, local-first, photo evidence, and reproducible builds.

The release should be evaluated by real usage, issue quality, repeat contributors, and verified downloads, not stars alone.

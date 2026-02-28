# GD&T Formatting Rules

## Standard: ASME Y14.5-2018 (exclusively — no ISO 1101 mixing)

## Feature Control Frame Notation

All feature control frames use this format:

```
|symbol| tolerance [modifier] | datum_A | datum_B | datum_C |
```

Examples:

- `|⊕| ∅0.25 Ⓜ | A | B | C |` — Position, diameter tolerance zone, MMC, three datums
- `|⊥| ∅0.05 | A |` — Perpendicularity, diameter zone, one datum
- `|▱| 0.1 |` — Flatness, linear zone, no datums (form control)
- `|⌓| 0.08 | A | B |` — Profile of a surface, two datums

## Unicode Symbols (Must Render Correctly)

| Symbol | Unicode | Name |
|--------|---------|------|
| ⊕ | U+2295 | Position |
| ⊥ | U+22A5 | Perpendicularity |
| ▱ | U+25B1 | Flatness |
| ○ | U+25CB | Circularity |
| ⌭ | U+232D | Cylindricity |
| ∠ | U+2220 | Angularity |
| // | -- | Parallelism (use two forward slashes) |
| ⌓ | U+2313 | Profile of a surface |
| ⌒ | U+2312 | Profile of a line |
| ↗ | U+2197 | Circular runout |
| ↗↗ | -- | Total runout (double arrow) |
| ◎ | U+25CE | Concentricity |
| ≡ | U+2261 | Symmetry |
| Ⓜ | U+24C2 | MMC modifier |
| Ⓛ | U+24C1 | LMC modifier |
| ∅ | U+2205 | Diameter symbol |

## Formatting Rules

1. Diameter symbol (∅) precedes tolerance value ONLY for cylindrical tolerance zones (holes, bosses, shafts). Linear features use raw number.
2. Modifier symbol follows tolerance value with no space: `∅0.25Ⓜ` or `∅0.25 Ⓜ` (both acceptable in output, but be consistent).
3. Datum references are single uppercase letters: A, B, C, etc.
4. Datum order matters: primary | secondary | tertiary (left to right).
5. Form controls (flatness, circularity, cylindricity, straightness) NEVER have datum references.
6. RFS (Regardless of Feature Size) is the default in Y14.5-2018 — no symbol needed.
7. Units: default to millimeters (mm). If inches, specify explicitly.
8. Tolerance values: use reasonable precision — typically 2-3 decimal places in mm, 3-4 in inches.

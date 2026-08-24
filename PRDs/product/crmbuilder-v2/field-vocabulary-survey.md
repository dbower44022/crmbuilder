# Field vocabulary survey — what three CRMs can say that the design cannot

Working paper for PI-414 (REQ-501…504, DEC-930). Read 2026-08-23.

The purpose is not to choose words. It is to establish, against real systems rather
than memory, the complete set of distinctions the design's field vocabulary has to be
able to carry. The words come next, one at a time, for approval.

## Sources

| System | Source | Read |
|---|---|---|
| EspoCRM | `application/Espo/Resources/metadata/fields/` in `espocrm/espocrm`, default branch — one file per field type | 2026-08-23 |
| HubSpot | Properties API guide, developers.hubspot.com — `type` and `fieldType` enumerations and their pairing table | 2026-08-23 |
| Salesforce | Metadata API `FieldType` enumeration, developer.salesforce.com | 2026-08-23 |

EspoCRM is the implemented engine. HubSpot is the second engine the design model already
names in its own code comments. Salesforce is included because it is the richest of the
three and therefore the hardest test of the vocabulary.

## What each system can say

**EspoCRM — 46 field types.**

`address`, `array`, `arrayInt`, `attachmentMultiple`, `autoincrement`, `barcode`, `base`,
`bool`, `checklist`, `colorpicker`, `currency`, `currencyConverted`, `date`, `datetime`,
`datetimeOptional`, `decimal`, `duration`, `email`, `enum`, `enumFloat`, `enumInt`, `file`,
`float`, `foreign`, `image`, `int`, `jsonArray`, `jsonObject`, `link`, `linkMultiple`,
`linkOne`, `linkParent`, `map`, `multiEnum`, `number`, `password`, `personName`, `phone`,
`rangeCurrency`, `rangeFloat`, `rangeInt`, `text`, `url`, `urlMultiple`, `varchar`,
`wysiwyg`.

CRMBuilder's own YAML schema supports 16 of these. The audit's translation table
recognises 19 and folds everything else into plain text.

**HubSpot — 8 storage types × 12 presentations.**

Storage (`type`): `string`, `number`, `bool`, `date`, `datetime`, `enumeration`,
`object_coordinates`, `json`.

Presentation (`fieldType`): `text`, `textarea`, `html`, `phonenumber`, `file`, `number`,
`date`, `select`, `radio`, `checkbox`, `booleancheckbox`, `calculation_equation`.

HubSpot's own documentation states the split plainly: type "determines the type of the
property, i.e. a string or a number", while fieldType "determines how the property will
appear". **A second CRM, designed independently, arrived at exactly the base-type plus
qualifier structure this planning item proposes.** That is the strongest external support
available for the shape, and it was not assumed — it was read.

**Salesforce — 31 field types.**

`Text`, `TextArea`, `LongTextArea`, `Html`, `EncryptedText`, `Email`, `Phone`, `Url`,
`Number`, `Integer`, `Long`, `Currency`, `Percent`, `Checkbox`, `Picklist`,
`MultiselectPicklist`, `Date`, `DateTime`, `Time`, `AutoNumber`, `Summary`, `Lookup`,
`MasterDetail`, `Hierarchy`, `MetadataRelationship`, `ExternalLookup`, `IndirectLookup`,
`File`, `Location`, `Address`, `Array`.

## What the design can say today

Twelve words: `text`, `long_text`, `enum`, `multi_enum`, `date`, `datetime`, `money`,
`boolean`, `number`, `reference`, `derived`, `foreign`.

Plus three qualifying properties already stored on the design record but, in two cases,
never read back from an instance: a format (`email`, `phone`, `url`, `percent`, `currency`,
`date`, `datetime`, `time`, `multiline`), a numeric scale, and a maximum length.

## The distinctions, and whether the design can carry them

✓ carried today · ~ carried by a qualifier that exists but is not read from instances ·
✗ cannot be expressed · ✓ DEC-NNN closed by a ruling made since the survey was written ·
→ moved out of the field vocabulary by a ruling, and carried elsewhere

**Correction, 2026-08-23.** The two qualifiers marked ~ are stored on the design record but
are **empty on all 254 CBM design fields** — neither has ever been populated, because the
reader never fills them in. The mechanism exists; the data does not. Those distinctions
close by teaching the reader to read them, not by using what is already held.

### Text

| Distinction | Where it appears | Design |
|---|---|---|
| Single-line text | all three | ✓ |
| Multi-line plain text | all three | ✓ |
| Rich or HTML text | Espo `wysiwyg`, HubSpot `html`, SF `Html` | ✓ DEC-933 |
| Email address | all three | ~ |
| Telephone number | all three | ~ |
| Web address | all three | ~ |
| Several web addresses in one field | Espo `urlMultiple` | ✓ DEC-937 |
| Secret or encrypted text | Espo `password`, SF `EncryptedText` | ✓ DEC-939 |
| Barcode | Espo `barcode` | ✓ DEC-939 |
| Colour | Espo `colorpicker` | ✓ DEC-939 |
| System-generated running number | Espo `autoincrement`, SF `AutoNumber` | ✓ DEC-939 |

### Numbers

| Distinction | Where it appears | Design |
|---|---|---|
| Whole number | all three | ~ |
| Decimal number | all three | ~ |
| Money | Espo `currency`, SF `Currency` | ✓ |
| Money converted to another currency | Espo `currencyConverted` | ✓ DEC-939 |
| Percentage | SF `Percent`; EspoCRM has none at all | ✓ DEC-941 |
| Length of time | Espo `duration` | ✓ DEC-936 |
| A range, low to high | Espo `rangeInt`, `rangeFloat`, `rangeCurrency` | ✓ DEC-934 |

### Dates and times

| Distinction | Where it appears | Design |
|---|---|---|
| Date | all three | ✓ |
| Date and time | all three | ✓ |
| Date where the time is optional | Espo `datetimeOptional` | ✓ DEC-939 |
| Time of day alone | SF `Time` | ✓ DEC-936 |

### Choices

| Distinction | Where it appears | Design |
|---|---|---|
| One choice from a fixed list | all three | ✓ |
| Several choices from a fixed list | all three | ✓ |
| Shown as a tick-list rather than a dropdown | Espo `checklist`, HubSpot `checkbox` | ✓ DEC-933 |
| Shown as radio buttons rather than a dropdown | HubSpot `radio` | ✓ DEC-933 |
| An open list of values with no fixed option set | Espo `array`, SF `Array` | ✓ DEC-935 |
| A choice whose stored value is a number | Espo `enumInt`, `enumFloat`, `arrayInt` | ✓ DEC-935 |
| Choose from a list or type your own | SF `combobox` | ✓ DEC-935 |

### Yes / no

| Distinction | Where it appears | Design |
|---|---|---|
| Yes / no | all three | ✓ |

### Links to other records

| Distinction | Where it appears | Design |
|---|---|---|
| Points at one record | Espo `link`/`linkOne`, SF `Lookup` | → relationship, DEC-932 |
| Points at many records | Espo `linkMultiple` | → relationship, DEC-932 |
| Points at a record of any of several kinds | Espo `linkParent` | → relationship, DEC-932 |
| Owning link — deleting the parent deletes the child | SF `MasterDetail` | → relationship, DEC-932 |
| Points at itself, forming a hierarchy | SF `Hierarchy` | → relationship, DEC-932 |
| Points at a record in another system | SF `ExternalLookup`, `IndirectLookup` | → relationship, DEC-932 |

### Computed values

| Distinction | Where it appears | Design |
|---|---|---|
| Calculated from this record | all three | ✓ |
| Summed or counted across related records | SF `Summary`, Espo via formula | ✓ |
| Copied from a linked record | Espo `foreign` | ✓ |

### Files and structures

| Distinction | Where it appears | Design |
|---|---|---|
| One attached file | Espo `file`, HubSpot `file`, SF `File` | ✓ DEC-936 |
| An image | Espo `image` | ✓ DEC-936 |
| Several attachments | Espo `attachmentMultiple` | ✓ DEC-937 |
| A place on a map | Espo `map`, HubSpot `object_coordinates`, SF `Location` | ✓ DEC-934 |
| A postal address as one unit | Espo `address`, SF `Address` | ✓ DEC-934 |
| A person's name as one unit | Espo `personName` | ✓ DEC-934 |
| Arbitrary structured data | Espo `jsonObject`/`jsonArray`, HubSpot `json` | ✓ DEC-936 |

## What the survey found

**The gap is much wider than the six collapses already known.** Those six were only the
places where EspoCRM's existing translation table folds two types into one. Measured
against everything the three systems can actually express, the design carries about
fourteen distinctions cleanly and four more through qualifiers it stores but does not read
back. Roughly thirty distinctions have no representation at all.

**Most of the missing ones are not new kinds of field.** They are the same handful of
questions asked over and over: how many values, how it is shown, whether the values are
constrained, whether it is one thing or several things bundled, whether it is stored or
computed, and whether it is sensitive. That is what makes a qualifier-based vocabulary the
right answer rather than a longer list of words — the axes recur, the words do not.

**Eight axes account for nearly every missing distinction:**

1. How many values the field holds — one, or several.
2. How it is presented — plain, rich, dropdown, radio, tick-list.
3. Whether values are constrained to a declared list, or open.
4. What kind of thing the value is — a scalar, or several parts bundled as one (an
   address, a name, a place, a range).
5. Whether it is stored or computed, and if computed, from this record, from related
   records, or copied from a linked one.
6. What character a link has — one target or many, one kind of target or several, owning
   or not, inside the system or outside it.
7. Whether the value is sensitive.
8. Whether the system generates the value rather than a person.

**Two distinctions are already recoverable at no vocabulary cost.** Email, telephone and
web address are separated by a format the design record already stores; whole and decimal
numbers are separated by a numeric scale it already stores. Neither is read back from an
instance today. Fixing the reading alone closes two of the six known collapses without
inventing a single word.

**Not everything here belongs in the field vocabulary.** Link character (axis 6) describes
a relationship, and the design already models relationships as their own construct.

**Settled 2026-08-23 by DEC-932 (REQ-505 to REQ-507).** A link between records is described
once, as a relationship, and never as a field. The reference field type is retired and its
19 records fold into relationship records; relationships gain targets that may be any of
several kinds of record, and the per-side display properties the field side was carrying.
Every axis-6 row above therefore leaves the field vocabulary. The row reading *"points at
many records — ✗"* closes by construction: link-typed fields stop being read as fields at
all, so the catch-all that recorded them as plain text is never reached.

The duplication that prompted the ruling was found in live data — the same link recorded as
field `linkedContact` and as relationship `cLinkedContact`, under two names, with nothing
keeping them in step.

## Not covered

- Whether each distinction is worth carrying. The survey establishes what exists, not what
  matters. Several — barcode, colour, converted currency — may be recorded as deliberately
  outside the vocabulary. That is a decision each.
- Entity, layout, role, team and filtered-tab vocabularies. Fields only.
- Any word choices. Those come next, individually, for approval.

## Rulings made since

| Ruling | What it settled | Rows closed |
|---|---|---|
| DEC-932 | A link between records is described once, as a relationship, never as a field | all of *Links to other records*, plus *points at many records* by construction |
| DEC-933 | A field says separately what its value is and how it is displayed; the second property is called **display** | rich text, tick-list, radio buttons |
| DEC-934 | A value made of several fixed parts is one field whose kind names the bundle — **postal address**, **person name**, **place**; a low-to-high range is an existing kind shown as a range | postal address, person name, place on a map, low-to-high range |
| DEC-935 | A field states how constrained its permitted values are, in a property called **values** — fixed, open or suggested; a numeric choice is the number kind with values fixed | open list, choose-or-type, numeric-valued choice |
| DEC-936 | Three kinds added — **file**, **time**, **structured data**; **image** and **duration** become format values | one file, an image, time of day, length of time, structured data (several attachments pending) |
| DEC-937 | A field states whether it **holds** one value or several; the separate multi-choice kind is removed | several attachments, several web addresses |
| DEC-938 | An attribute the design does not declare is **unknown**, with the reason naming the design rather than the instance | (correctness, not coverage — no survey row) |
| DEC-941 | **Percent** stays in the format list (DEC-933's six dropped becomes five), and publishing declares any property the target CRM cannot carry | percentage |
| DEC-939 | All six remaining distinctions carried; **supplied by** records who provides a value, replacing the unused externally-populated flag; **secret**, **colour**, **time optional** join format and **barcode** joins display | secret text, barcode, colour, system-generated number, converted money, optional-time date |

## Survey complete

Every distinction the three surveyed CRMs make is now carried by the design's field
vocabulary, or has been moved to the relationship construct. Eight rulings on coverage
(DEC-932 to DEC-937, DEC-939) plus one on correctness (DEC-938).

**Added:** four properties — `display`, `values`, `holds`, `supplied by` — and six kinds —
postal address, person name, place, file, time, structured data. Plus new settings on
existing properties: `image`, `duration`, `secret`, `colour`, `time optional` on format,
and `barcode`, `range` on display.

**Removed:** the separate multi-choice kind (DEC-937) and the externally-populated flag
(DEC-939).

What remains below is not coverage but correctness.

## Open points

None. The last one — whether an enum with no options should be reported as a fault on the
instance rather than only as a gap in the design — was settled 2026-08-23 by DEC-940: it is
**drift**, even when the instance also carries no options, because the field is unusable on
either side. That amends DEC-938 for this case; DEC-938's general rule that a genuinely
undeclared attribute is unknown stands.

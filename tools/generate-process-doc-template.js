// ═══════════════════════════════════════════════════════════════════════
// CRM Builder — Process Document Generator Template
// ═══════════════════════════════════════════════════════════════════════
//
// Reference implementation for generating Phase 2 process documents
// as Word (.docx) files. This template defines the standard formatting,
// table layouts, and document structure used across all CRM Builder
// implementations.
//
// Usage:
//   Copy this file per process, replace the DOCUMENT CONTENT section
//   with the process-specific content, then run with Node.js:
//     node generate-{PROCESS-CODE}.js
//
// Reference document: MN-INTAKE.docx (Cleveland Business Mentors)
//
// Formatting standards (also stored in Claude memory):
//   - Font: Arial throughout
//   - Colors: Header bg #1F3864, header text white, title/heading #1F3864,
//     alt row shading #F2F7FB, borders #AAAAAA, gray text #888888
//   - Field tables: Two rows per field
//     Row 1: Field Name (bold) | Type | Required (Yes/No) | Values | Default | ID (small gray)
//     Row 2: Description (full-width span, gray font)
//     Alternating shading per field pair
//   - Column widths (DXA): 2200 + 1100 + 800 + 2400 + 1000 + 1860 = 9360
//   - Required column: strictly Yes/No — nuance goes in description
//   - Requirement tables: Two columns (ID bold + Requirement), same header style
//   - Page: US Letter, 1" margins
//   - Header: org name left, process name right
//   - Footer: "Process Document — [Domain] Domain"
//   - Human-readable-first identifiers: "Client Intake (MN-INTAKE)" not
//     "MN-INTAKE — Client Intake"
//
// Dependencies:
//   npm install -g docx
//
// ═══════════════════════════════════════════════════════════════════════

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageBreak, PositionalTab, PositionalTabAlignment,
  PositionalTabRelativeTo, PositionalTabLeader
} = require("docx");

// ── Shared styles ──────────────────────────────────────────────────
const FONT = "Arial";
const SZ = { body: 22, small: 20, xs: 16, h1: 32, h2: 28, h3: 24, meta: 20 };
const COLORS = {
  headerBg: "1F3864",
  headerText: "FFFFFF",
  altRowBg: "F2F7FB",
  borderColor: "AAAAAA",
  titleColor: "1F3864",
  idColor: "888888",
};

const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.borderColor };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };
const descMargins = { top: 40, bottom: 80, left: 100, right: 100 };

// ── Primitive helpers ──────────────────────────────────────────────

function r(text, opts = {}) {
  return new TextRun({
    text,
    font: FONT,
    size: opts.size || SZ.body,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color,
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120 },
    alignment: opts.align,
    children: Array.isArray(text) ? text : [r(text, opts)],
  });
}

function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    children: [r(text, { bold: true, size: level === HeadingLevel.HEADING_1 ? SZ.h1 : level === HeadingLevel.HEADING_2 ? SZ.h2 : SZ.h3 })],
  });
}

// ── Table helpers ──────────────────────────────────────────────────
const TABLE_WIDTH = 9360; // US Letter with 1" margins

function hdrCell(text, width) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: COLORS.headerBg, type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({ children: [r(text, { bold: true, size: SZ.small, color: COLORS.headerText })] })],
  });
}

function dataCell(text, width, opts = {}) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.shaded ? { fill: COLORS.altRowBg, type: ShadingType.CLEAR } : undefined,
    margins: cellMargins,
    columnSpan: opts.columnSpan,
    children: [new Paragraph({
      children: [r(text, {
        size: opts.size || SZ.small,
        bold: opts.bold,
        color: opts.color,
        italics: opts.italics,
      })],
    })],
  });
}

// ── Field table (two-row format) ───────────────────────────────────
// Row 1: Field Name | Type | Required | Values | Default | ID
// Row 2: Description (spans all columns, gray font)
const FC = [2200, 1100, 800, 2400, 1000, 1860];

function fieldTableHeader() {
  return new TableRow({
    children: [
      hdrCell("Field Name", FC[0]),
      hdrCell("Type", FC[1]),
      hdrCell("Required", FC[2]),
      hdrCell("Values", FC[3]),
      hdrCell("Default", FC[4]),
      hdrCell("ID", FC[5]),
    ],
  });
}

function fieldRows(name, type, required, values, defaultVal, id, desc, shaded) {
  const bg = shaded;
  const row1 = new TableRow({
    children: [
      dataCell(name, FC[0], { shaded: bg, bold: true }),
      dataCell(type, FC[1], { shaded: bg }),
      dataCell(required, FC[2], { shaded: bg }),
      dataCell(values, FC[3], { shaded: bg }),
      dataCell(defaultVal, FC[4], { shaded: bg }),
      dataCell(id, FC[5], { shaded: bg, size: SZ.xs, color: COLORS.idColor }),
    ],
  });
  const row2 = new TableRow({
    children: [
      new TableCell({
        borders,
        width: { size: TABLE_WIDTH, type: WidthType.DXA },
        columnSpan: 6,
        shading: bg ? { fill: COLORS.altRowBg, type: ShadingType.CLEAR } : undefined,
        margins: descMargins,
        children: [new Paragraph({
          children: [r(desc, { size: SZ.small, color: COLORS.idColor })],
        })],
      }),
    ],
  });
  return [row1, row2];
}

// fields: array of [name, type, required, values, default, id, description]
function fieldTable(fields) {
  const rows = [fieldTableHeader()];
  fields.forEach((f, i) => {
    const [name, type, required, values, defaultVal, id, desc] = f;
    rows.push(...fieldRows(name, type, required, values, defaultVal, id, desc, i % 2 === 1));
  });
  return new Table({
    width: { size: TABLE_WIDTH, type: WidthType.DXA },
    columnWidths: FC,
    rows,
  });
}

// ── Bullet & numbered list helpers ─────────────────────────────────

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [r(text)],
  });
}

function numberedItem(text) {
  return new Paragraph({
    numbering: { reference: "workflow", level: 0 },
    spacing: { after: 80 },
    children: [r(text)],
  });
}

// ── Metadata table (title page) ────────────────────────────────────

function metaTable(pairs) {
  const KW = 2400;
  const VW = TABLE_WIDTH - KW;
  return new Table({
    width: { size: TABLE_WIDTH, type: WidthType.DXA },
    columnWidths: [KW, VW],
    rows: pairs.map(([key, val]) =>
      new TableRow({
        children: [
          new TableCell({
            borders,
            width: { size: KW, type: WidthType.DXA },
            shading: { fill: "E8E8E8", type: ShadingType.CLEAR },
            margins: cellMargins,
            children: [new Paragraph({ children: [r(key, { bold: true, size: SZ.meta })] })],
          }),
          new TableCell({
            borders,
            width: { size: VW, type: WidthType.DXA },
            margins: cellMargins,
            children: [new Paragraph({ children: [r(val, { size: SZ.meta })] })],
          }),
        ],
      })
    ),
  });
}

// ── Requirement table ──────────────────────────────────────────────
const RC = [2000, 7360];

function reqTable(reqs) {
  const rows = [
    new TableRow({
      children: [
        hdrCell("ID", RC[0]),
        hdrCell("Requirement", RC[1]),
      ],
    }),
  ];
  reqs.forEach(([id, text], i) => {
    rows.push(
      new TableRow({
        children: [
          dataCell(id, RC[0], { bold: true, shaded: i % 2 === 1 }),
          dataCell(text, RC[1], { shaded: i % 2 === 1 }),
        ],
      })
    );
  });
  return new Table({
    width: { size: TABLE_WIDTH, type: WidthType.DXA },
    columnWidths: RC,
    rows,
  });
}

// ── Document style definitions ─────────────────────────────────────

function docStyles() {
  return {
    default: { document: { run: { font: FONT, size: SZ.body } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: SZ.h1, bold: true, font: FONT, color: COLORS.titleColor },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: SZ.h2, bold: true, font: FONT, color: COLORS.titleColor },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: SZ.h3, bold: true, font: FONT },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 },
      },
    ],
  };
}

function docNumbering() {
  return {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "workflow",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  };
}

function pageProps() {
  return {
    page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
    },
  };
}

function docHeader(orgName, processLabel) {
  return new Header({
    children: [
      new Paragraph({
        spacing: { after: 0 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.titleColor, space: 1 } },
        children: [
          r(orgName, { size: 18, color: "666666" }),
          new TextRun({
            children: [
              new PositionalTab({
                alignment: PositionalTabAlignment.RIGHT,
                relativeTo: PositionalTabRelativeTo.MARGIN,
                leader: PositionalTabLeader.NONE,
              }),
            ],
          }),
          r(processLabel, { size: 18, color: "666666" }),
        ],
      }),
    ],
  });
}

function docFooter(domainName) {
  return new Footer({
    children: [
      new Paragraph({
        spacing: { after: 0 },
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: COLORS.titleColor, space: 1 } },
        children: [
          r(`Process Document \u2014 ${domainName} Domain`, { size: 16, color: "999999" }),
        ],
      }),
    ],
  });
}


// ═══════════════════════════════════════════════════════════════════════
// DOCUMENT CONTENT — Replace everything below for each process
// ═══════════════════════════════════════════════════════════════════════

// ── Configuration ──────────────────────────────────────────────────
const ORG_NAME = "Cleveland Business Mentors";
const PROCESS_LABEL = "Client Intake (MN-INTAKE)";  // human-readable first
const DOMAIN_NAME = "Mentoring";
const OUTPUT_FILE = "/home/claude/MN-INTAKE.docx";

const doc = new Document({
  styles: docStyles(),
  numbering: docNumbering(),
  sections: [
    {
      properties: pageProps(),
      headers: { default: docHeader(ORG_NAME, PROCESS_LABEL) },
      footers: { default: docFooter(DOMAIN_NAME) },
      children: [
        // ── Title block ──
        p(ORG_NAME, { size: 36, bold: true, color: COLORS.titleColor, after: 60, align: AlignmentType.CENTER }),
        p(PROCESS_LABEL, { size: 28, bold: true, color: COLORS.titleColor, after: 200, align: AlignmentType.CENTER }),
        p("Process Document", { size: SZ.body, after: 400, align: AlignmentType.CENTER }),

        metaTable([
          ["Domain", "Mentoring (MN)"],
          ["Process Code", "MN-INTAKE"],
          ["Version", "1.0"],
          ["Status", "Draft"],
          ["Last Updated", "03-30-26 22:00"],
          ["Source", "Extracted from CBM-Domain-PRD-Mentoring.md v1.0"],
        ]),

        new Paragraph({ children: [new PageBreak()] }),

        // ══════════════════════════════════════════════════════════════
        // Section 1: Process Purpose and Trigger
        // ══════════════════════════════════════════════════════════════
        heading("1. Process Purpose and Trigger", HeadingLevel.HEADING_1),

        p("The Client Intake process begins when a prospective client submits a mentoring request through the CBM public website. Its purpose is to capture the information needed to assess eligibility and identify an appropriate mentor, and to route the application to the Client Administrator for review."),

        p("The process is complete when the Client Administrator has either approved the application (advancing it to the Mentor Matching process) or declined it with a recorded reason. All records created during intake are retained permanently regardless of outcome."),

        // ══════════════════════════════════════════════════════════════
        // Section 2: Personas Involved
        // ══════════════════════════════════════════════════════════════
        heading("2. Personas Involved", HeadingLevel.HEADING_1),

        p("Client (MST-PER-013)", { bold: true, after: 40 }),
        p("Submits the mentoring request through the public website. Provides business information, contact details, and a description of mentoring needs."),

        p("Client Administrator (MST-PER-003)", { bold: true, after: 40 }),
        p("Reviews submitted applications for completeness and basic eligibility. Approves or declines applications and communicates decisions to applicants directly."),

        // ══════════════════════════════════════════════════════════════
        // Section 3: Process Workflow
        // ══════════════════════════════════════════════════════════════
        heading("3. Process Workflow", HeadingLevel.HEADING_1),

        numberedItem("The prospective client completes and submits the Phase 1 Mentoring Request form on the CBM public website."),
        numberedItem("The system automatically creates three linked records: a Client Organization record (the business), a Client Contact record (the submitting individual, flagged as Primary Contact), and an Engagement record with status Submitted."),
        numberedItem("The Client Administrator receives an automatic notification of the new submission."),
        numberedItem("The Client Administrator reviews the submission for completeness and basic eligibility against CBM\u2019s program criteria."),
        numberedItem("If eligible, the application proceeds to the Mentor Matching process (MN-MATCH)."),
        numberedItem("If not eligible, the Client Administrator updates the Engagement status to Declined, records the reason, and notifies the applicant directly. No automated notification is sent. The Client Organization and Contact records are retained permanently."),

        p(""),
        p("A structured eligibility screening workflow may be defined by CBM leadership in a future revision. The current process assumes a basic administrative review.", { italics: true }),

        // ══════════════════════════════════════════════════════════════
        // Section 4: System Requirements
        // ══════════════════════════════════════════════════════════════
        heading("4. System Requirements", HeadingLevel.HEADING_1),

        reqTable([
          ["MN-INTAKE-REQ-001", "The system must accept client mentoring requests submitted through the public website and create linked Client Organization, Client Contact, and Engagement records automatically."],
          ["MN-INTAKE-REQ-002", "The submitting individual must be automatically flagged as the Primary Contact on the new Client Organization record."],
          ["MN-INTAKE-REQ-003", "The system must notify the Client Administrator immediately upon receipt of a new submission."],
          ["MN-INTAKE-REQ-004", "New submissions must appear in a dedicated Submitted Applications view accessible to the Client Administrator."],
          ["MN-INTAKE-REQ-005", "The system must support recording of a decline reason when an application is rejected."],
          ["MN-INTAKE-REQ-006", "Client Organization and Contact records must be retained permanently regardless of Engagement outcome."],
        ]),

        // ══════════════════════════════════════════════════════════════
        // Section 5: Process Data (Pre-Existing)
        // ══════════════════════════════════════════════════════════════
        heading("5. Process Data", HeadingLevel.HEADING_1),

        p("The Client Intake process does not require pre-existing data. It is the first process in the Mentoring lifecycle and creates all of its own records from the submitted intake form. The submitted application itself is the data the Client Administrator reviews to assess eligibility."),

        // ══════════════════════════════════════════════════════════════
        // Section 6: Data Collected
        // ══════════════════════════════════════════════════════════════
        heading("6. Data Collected", HeadingLevel.HEADING_1),

        p("The following records and fields are created when the intake form is submitted. Fields are collected in Phase 1 (public intake form). Phase 2 fields collected later by the mentor are defined in the Engagement Management process (MN-ENGAGE)."),

        // ── Client Organization ──
        heading("Entity: Client Organization", HeadingLevel.HEADING_2),

        fieldTable([
          // [Field Name, Type, Required, Values, Default, ID, Description]
          ["Business Name", "Text", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-001",
           "The legal or operating name of the client business. Optional because pre-startup applicants may not yet have a business name."],
          ["Website", "URL", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-002",
           "The client business website address, if one exists."],
          ["Address", "Address", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-003",
           "The primary business address (street, city, state, zip). Used for geographic reporting and service area tracking."],
          ["Organization Type", "Dropdown", "No", "For-Profit, Non-Profit", "\u2014", "MN-INTAKE-DAT-004",
           "Whether the organization operates as a for-profit business or a nonprofit. Drives funder reporting categories."],
          ["Business Stage", "Dropdown", "Yes", "Pre-Startup, Startup, Early Stage, Growth Stage, Established", "\u2014", "MN-INTAKE-DAT-005",
           "The stage of business development the client organization is in. Used for mentor matching and funder reporting."],
          ["Industry Sector", "Dropdown", "No", "20 top-level NAICS sectors", "\u2014", "MN-INTAKE-DAT-006",
           "The primary industry sector of the client business based on the North American Industry Classification System. Used for mentor matching and impact reporting. Drives the Industry Subsector filter."],
          ["Industry Subsector", "Dropdown", "No", "~100 subsectors filtered by Industry Sector", "\u2014", "MN-INTAKE-DAT-007",
           "The specific industry subsector within the selected Industry Sector. Provides more precise industry classification for matching and reporting."],
          ["Mentoring Focus Areas", "Multi-select", "No", "TBD \u2014 see MN-ISS-001", "\u2014", "MN-INTAKE-DAT-008",
           "The specific areas where the client is seeking mentoring assistance. Primary matching criterion between clients and mentors. Values must align with the corresponding field on the Mentor profile."],
          ["Mentoring Needs Description", "Rich text", "Yes", "\u2014", "\u2014", "MN-INTAKE-DAT-009",
           "The client\u2019s own description of what they are looking for in a mentoring engagement. Reviewed by the Client Assignment Coordinator during mentor matching."],
        ]),

        p(""),

        // ── Client Contact ──
        heading("Entity: Client Contact", HeadingLevel.HEADING_2),

        fieldTable([
          ["First Name", "Text", "Yes", "\u2014", "\u2014", "MN-INTAKE-DAT-010",
           "The contact\u2019s first name."],
          ["Last Name", "Text", "Yes", "\u2014", "\u2014", "MN-INTAKE-DAT-011",
           "The contact\u2019s last name."],
          ["Email", "Email", "Yes", "\u2014", "\u2014", "MN-INTAKE-DAT-012",
           "The contact\u2019s primary email address. Used for all CBM communications including mentor introduction, meeting requests, and satisfaction surveys."],
          ["Phone", "Phone", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-013",
           "The contact\u2019s primary phone number."],
          ["Zip Code", "Text", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-014",
           "The contact\u2019s zip code. Used for geographic service area reporting and outreach targeting."],
          ["Primary Contact", "Yes/No", "Yes", "\u2014", "Yes", "MN-INTAKE-DAT-015",
           "Identifies this contact as the primary point of contact for the client organization. Defaults to Yes for the first contact created. Automated communications default to the primary contact when no specific engagement contacts are designated."],
        ]),

        p(""),

        // ── Engagement ──
        heading("Entity: Engagement", HeadingLevel.HEADING_2),

        fieldTable([
          ["Status", "Dropdown", "Yes", "Submitted, Declined, Pending Acceptance, Assigned, Active, On-Hold, Dormant, Inactive, Abandoned, Completed", "Submitted", "MN-INTAKE-DAT-016",
           "The current lifecycle stage of the mentoring engagement. Created automatically with value Submitted when the intake form is submitted. This process may transition the status to Declined. Full status transition rules are defined across Mentor Matching (MN-MATCH), Engagement Management (MN-ENGAGE), Activity Monitoring (MN-INACTIVE), and Engagement Closure (MN-CLOSE)."],
          ["Close Date", "Date", "No", "\u2014", "\u2014", "MN-INTAKE-DAT-017",
           "The date the engagement was formally closed. System-populated automatically when status transitions to Declined, Completed, or Abandoned. Not entered by users directly."],
          ["Close Reason", "Dropdown", "No", "Goals Achieved, Client Withdrew, Inactive / No Response, Other", "\u2014", "MN-INTAKE-DAT-018",
           "The reason the engagement was closed. Required when the engagement is closed but not at initial creation. Automatically set to Inactive / No Response for system-initiated Abandoned closures."],
        ]),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUTPUT_FILE, buffer);
  console.log(`${OUTPUT_FILE} created successfully`);
});

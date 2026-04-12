"""JSON payload schemas for CRM Builder Automation.

Each work item type that produces structured output has a corresponding
schema module defining the expected payload structure.  Schemas are
consumed by:

- The **Prompt Generator** (Section 10): rendered into the prompt-optimized
  guide as the output specification the AI must follow.
- The **Import Processor** (Section 11, Layer 3): validated against incoming
  payloads to catch structural errors before mapping.
"""

"""Document renderers over the V2 candidate graph (WTK-116 design spec).

Rendering is neither transform nor adapter — both existing packages
would mislead (spec §7.1). Modules here produce working documents
(Markdown) from API reads and prior-step files, and never write a DB
record: every judgment-bearing derivation (domain guesses, band
ordering, probe seeds) exists only in the rendered document.
"""

"""contexts/matcher_policy/ — the neutral matcher-policy seam (D186).

The surface where an approved matcher recommendation's effect persists as active
policy. It is the seam between the two halves of the loop: **optimization writes
policy on apply** (via the write port), **the matcher reads policy on run** (via
the read port, through a daily_driver port + the apps bridge). Neither imports
the other; this context imports neither — the producer-consumer symmetry the
independence contracts enforce (D17).

Not a daily_driver column (optimization could not write it) and not an
optimization column (the matcher could not read it): a neutral context reached by
both sides through ports is the only shape the seam permits.

The policy carries a single ``suppress_single_signal`` flag (D186/S91b). The
rule-set abstraction lands at the second rule (cross-domain), the second
instance. Hexagonal layout per D16.
"""

"""email — the email data substrate bounded context (D151, P15, S56a).

Mirrors the calendar substrate (D148/D149) with the email-specific
divergences the S56 reconnaissance surfaced: a two-call N+1 Gmail pull,
an email-local chunk store for long bodies, full-pull-only sync with
set-diff deletion, and cite-directly (content immutable; no citation
snapshot). The email_conversation surface and five-way dispatch are S56b.
"""

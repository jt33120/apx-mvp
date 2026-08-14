"""Time and presence producing an acceptance — the single most tempting affordance on a
1 700-row reading surface, and the one FR-45 forbids by name."""


def auto_validate_after_dwell(rows, seconds_on_page):
    for row in rows:
        if seconds_on_page > 30:
            row.accepted = True

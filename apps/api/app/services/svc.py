"""Flat namespace over the domain service modules, so routers can call `svc.<function>`."""

from .access import (  # noqa: F401
    ADMIN_ROLES,
    REVIEW_ROLES,
    memberships_of,
    report_role,
    require_member,
    role_in,
    scoped_location_ids,
)
from .auth import create_session, end_session, login, register, session_user  # noqa: F401
from .claims import (  # noqa: F401
    add_evidence,
    ai_assist,
    claim_found,
    claim_org,
    claim_role,
    create_claim,
    evidence_of,
    get_claim,
    history_of,
    image_of,
    my_claims,
    org_claims,
    other_approved_claim,
    review_claim,
)
from .events import emit  # noqa: F401
from .matching import (  # noqa: F401
    active_claim_for,
    dismiss_match,
    get_match,
    match_access,
    match_visible,
    matches_for_report,
    my_matches,
    verification_questions,
)
from .notifications import mark_read, my_notifications, unread_count  # noqa: F401
from .payments import (  # noqa: F401
    approval_url,
    capture_order,
    create_order,
    get_payment,
    handle_webhook,
    mock_approve,
    payer_payment,
)
from .recoveries import (  # noqa: F401
    OPEN as OPEN_RECOVERY,
    advance_courier,
    cancel_recovery,
    captured_payment,
    confirm_collection,
    confirm_received,
    create_recovery,
    dispatch,
    events_of,
    get_recovery,
    issue_pickup_token,
    latest_payment,
    recovery_for_claim,
    refresh_quote,
    validate_token,
)
from .reports import (  # noqa: F401
    can_view_image,
    claims_for_report,
    create_found,
    create_lost,
    get_report,
    my_reports,
    processing_status,
    read_image,
    report_access,
    report_images,
    request_extraction,
    require_report_editor,
    save_upload,
    submit,
    update_report,
    withdraw,
)

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.profile_summary import ProfileSummaryResponse
from app.schemas.user import (
    DiscoverySettingsRead,
    DiscoverySettingsUpdate,
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
    OnboardingStateRead,
    OnboardingStateUpdate,
    ThoughtVisibilityUpdate,
    UserProfileRead,
    UserProfileUpdate,
    UserSearchResult,
)
from app.services.profile_summary_service import get_profile_summary
from app.services.user_service import (
    bulk_update_thought_visibility,
    delete_user_account,
    export_user_data,
    get_public_user_profile,
    get_user_profile,
    search_users,
    update_discovery_settings,
    update_notification_preferences,
    update_onboarding_state,
    update_user_profile,
)

router = APIRouter(prefix="/users")


@router.get("/me", response_model=UserProfileRead)
def get_me(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> UserProfileRead:
    return get_user_profile(session, current_user_id)


@router.patch("/me", response_model=UserProfileRead)
def update_me(
    payload: UserProfileUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> UserProfileRead:
    return update_user_profile(session, current_user_id, payload)


@router.get("/search", response_model=list[UserSearchResult])
def search(
    q: str = "",
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> list[UserSearchResult]:
    return search_users(session, current_user_id, q)


@router.get("/{user_id}", response_model=UserProfileRead)
def get_user(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> UserProfileRead:
    return get_public_user_profile(session, current_user_id, user_id)


@router.get("/{user_id}/summary", response_model=ProfileSummaryResponse)
def get_user_summary(
    user_id: str,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = get_profile_summary(session, current_user_id, user_id)
    if result is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="user not found")
    return result


@router.patch("/me/notification-preferences", response_model=NotificationPreferencesRead)
def update_me_notification_preferences(
    payload: NotificationPreferencesUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> NotificationPreferencesRead:
    return NotificationPreferencesRead(
        notification_prefs=update_notification_preferences(session, current_user_id, payload)
    )


@router.patch("/me/onboarding", response_model=OnboardingStateRead)
def update_me_onboarding(
    payload: OnboardingStateUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> OnboardingStateRead:
    return OnboardingStateRead(completed=update_onboarding_state(session, current_user_id, payload.completed))


@router.patch("/me/discovery", response_model=DiscoverySettingsRead)
def update_me_discovery(
    payload: DiscoverySettingsUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> DiscoverySettingsRead:
    return DiscoverySettingsRead(
        serendipity_enabled=update_discovery_settings(
            session,
            current_user_id,
            serendipity_enabled=payload.serendipity_enabled,
        )
    )


@router.patch("/me/thought-visibility")
def update_me_thought_visibility(
    payload: ThoughtVisibilityUpdate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, int | str]:
    updated = bulk_update_thought_visibility(session, current_user_id, payload.visibility)
    return {"updated": updated, "visibility": payload.visibility}


@router.get("/me/export")
def export_me(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict:
    return export_user_data(session, current_user_id)


@router.delete("/me")
def delete_me(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, bool]:
    delete_user_account(session, current_user_id)
    return {"deleted": True}

"""FSM states for language and interest selection (spec Phase 7).

Reused for both first-time onboarding (`/start`) and later re-entry
(`/language`, `/interests`) — the `onboarding` flag carried in FSM data
(see bot/handlers/interests.py) decides what happens after the user
finishes, not a separate set of states.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choosing_language = State()
    choosing_interests = State()

"""
Gamification foundation (Phase 0 of GAMIFICATION-PLAN.md).

Three measurements are kept deliberately separate, because conflating them is
what lets a student look academically strong purely from time spent:

    TopicMastery.mastery_score  -- understanding.   CAN go down.
    XpLedger / User.points      -- participation.   NEVER goes down.
    Mastery Points (weekly)     -- league position. Resets weekly.

Everything is written through `events.record()`, which is idempotent on a
deterministic event key so no action can be rewarded twice.
"""

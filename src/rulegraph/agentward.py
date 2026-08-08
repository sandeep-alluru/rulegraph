"""AgentWard-class post-incident runtime enforcement (HN AgentWard).

Public case: After an AI agent deleted files/DB, operators need a **runtime
enforcer** that locks further high-risk work until inventory + human clearance
exist — not only a pre-action destructive classifier (groundcrew DB-WIPE).

Twin of groundcrew ``gate_destructive`` (pre-action):
  AgentWard gates **post-incident lockdown** and subsequent agent actions.

Non-Ornament:
  Call ``gate_post_incident`` after any destructive incident signal and before
  the next high-risk tool. Pair with ``gate_policy_query`` / ``gate_logprob``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

from rulegraph.closed_loop import ClosedLoopError, GateOutcome

IncidentStatus = Literal["open", "lockdown", "cleared", "false_alarm"]

# Default high-risk action verbs (post-incident continue rules).
DEFAULT_HIGH_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        "delete",
        "rm",
        "unlink",
        "drop",
        "truncate",
        "destroy",
        "wipe",
        "format",
        "force_push",
        "git_push_force",
        "send_email",
        "mass_delete",
        "chmod",
        "chown",
        "kubectl_delete",
        "terraform_destroy",
        "write_production",
        "migrate_down",
        "shell",
        "exec",
    }
)


@dataclass(frozen=True)
class IncidentEvent:
    """One destructive / loss event that opens enforcement."""

    incident_id: str
    kind: str  # e.g. file_delete, db_drop, self_delete
    paths: tuple[str, ...] = ()
    summary: str = ""
    agent_id: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "kind": self.kind,
            "paths": list(self.paths),
            "summary": self.summary,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
        }


@dataclass
class EnforcementSession:
    """Mutable post-incident lockdown session (AgentWard runtime).

    Attributes:
        status: open/lockdown/cleared/false_alarm.
        inventory: Recovered inventory of lost/affected resources.
        clearance_token: Human/owner clearance id (required to clear).
        blocked_actions: High-risk actions attempted while locked.
    """

    incident: IncidentEvent
    status: IncidentStatus = "open"
    inventory: list[str] = field(default_factory=list)
    clearance_token: str | None = None
    blocked_actions: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident": self.incident.to_dict(),
            "status": self.status,
            "inventory": list(self.inventory),
            "clearance_token": self.clearance_token,
            "blocked_actions": list(self.blocked_actions),
            "notes": self.notes,
            "lockdown_active": self.lockdown_active,
        }

    @property
    def lockdown_active(self) -> bool:
        return self.status in {"open", "lockdown"}


def _as_incident(item: IncidentEvent | dict[str, Any]) -> IncidentEvent:
    if isinstance(item, IncidentEvent):
        return item
    if not isinstance(item, dict):
        raise TypeError(f"incident must be IncidentEvent or dict, got {type(item)!r}")
    iid = str(item.get("incident_id") or item.get("id") or "").strip()
    if not iid:
        raise ValueError("incident missing incident_id")
    kind = str(item.get("kind") or item.get("type") or "destructive").strip()
    paths_raw = item.get("paths") or item.get("targets") or item.get("files") or ()
    if isinstance(paths_raw, str):
        paths: tuple[str, ...] = (paths_raw,) if paths_raw.strip() else ()
    else:
        paths = tuple(str(p) for p in paths_raw if str(p).strip())
    return IncidentEvent(
        incident_id=iid,
        kind=kind,
        paths=paths,
        summary=str(item.get("summary") or item.get("message") or ""),
        agent_id=str(item.get("agent_id") or item.get("agent") or ""),
        timestamp=float(item.get("timestamp") or item.get("ts") or 0.0),
    )


def open_incident(
    incident: IncidentEvent | dict[str, Any],
    *,
    auto_lockdown: bool = True,
) -> EnforcementSession:
    """Open an AgentWard session from a destructive incident signal."""
    ev = _as_incident(incident)
    status: IncidentStatus = "lockdown" if auto_lockdown else "open"
    # Seed inventory from incident paths when present
    inv = list(ev.paths)
    return EnforcementSession(incident=ev, status=status, inventory=inv)


def record_inventory(
    session: EnforcementSession,
    paths: Iterable[str],
    *,
    replace: bool = False,
) -> EnforcementSession:
    """Attach or merge post-incident inventory (what was lost / affected)."""
    new_paths = [str(p).strip() for p in paths if str(p).strip()]
    if replace:
        session.inventory = new_paths
    else:
        seen = set(session.inventory)
        for p in new_paths:
            if p not in seen:
                session.inventory.append(p)
                seen.add(p)
    return session


def clear_incident(
    session: EnforcementSession,
    *,
    clearance_token: str,
    require_inventory: bool = True,
) -> EnforcementSession:
    """Attempt to clear lockdown with a human/owner token.

    Does **not** clear if inventory is empty when required — status stays locked.
    """
    token = (clearance_token or "").strip()
    if not token:
        session.notes = "clear refused: empty clearance_token"
        return session
    if require_inventory and not session.inventory:
        session.notes = "clear refused: empty inventory"
        return session
    session.clearance_token = token
    session.status = "cleared"
    session.notes = "cleared"
    return session


def is_high_risk_action(
    action: str,
    *,
    extra: Iterable[str] | None = None,
) -> bool:
    """True if action name matches default or extra high-risk verbs."""
    a = (action or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not a:
        return False
    banned = set(DEFAULT_HIGH_RISK_ACTIONS)
    if extra:
        banned |= {str(x).strip().lower().replace("-", "_") for x in extra}
    if a in banned:
        return True
    for b in banned:
        if a.startswith(b + "_") or a.endswith("_" + b) or b in a.split("."):
            return True
    return False


def gate_post_incident(
    session: EnforcementSession | dict[str, Any] | None,
    *,
    proposed_action: str | None = None,
    require_session_after_incident: bool = False,
    incident_signaled: bool = False,
    require_inventory: bool = True,
    block_high_risk_while_locked: bool = True,
    high_risk_extra: Iterable[str] | None = None,
) -> GateOutcome:
    """Refuse high-risk continue under open AgentWard lockdown.

    Rules:

    * ``incident_signaled`` and no session when ``require_session_after_incident``
      → **FAIL_LOUD** (enforcer missing after known destruction)
    * No session and not required → **PASS** (nothing to enforce)
    * Session open/lockdown + empty inventory when required → **FAIL_LOUD**
    * Session locked + high-risk ``proposed_action`` → **FAIL** (record block)
    * Session cleared with inventory + token → **PASS**
    * Locked + low-risk / no proposed action → **PASS** with human_required note
      only when action is None (observe-only); if action is low-risk → **PASS**

    Args:
        session: Open enforcement session or dict; None if no incident yet.
        proposed_action: Next agent action name to gate.
        require_session_after_incident: When True and incident_signaled, missing
            session is FAIL_LOUD.
        incident_signaled: External signal that destruction already happened.
        require_inventory: Empty inventory while locked → FAIL_LOUD.
        block_high_risk_while_locked: High-risk under lockdown → FAIL.
    """
    if session is None:
        if require_session_after_incident and incident_signaled:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "AGENTWARD: destructive incident signaled but no EnforcementSession "
                    "— runtime enforcer missing after agent deletion (HN AgentWard class)"
                ),
                exit_code=2,
                human_required=True,
                action=proposed_action,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason="AGENTWARD: no open incident session; nothing to enforce",
            exit_code=0,
            human_required=False,
            action=proposed_action,
        )

    if isinstance(session, dict):
        try:
            inc = _as_incident(session.get("incident") or session)
            status = str(session.get("status") or "open").strip().lower()
            if status not in {"open", "lockdown", "cleared", "false_alarm"}:
                status = "open"
            sess = EnforcementSession(
                incident=inc,
                status=status,  # type: ignore[arg-type]
                inventory=list(session.get("inventory") or []),
                clearance_token=session.get("clearance_token"),
                blocked_actions=list(session.get("blocked_actions") or []),
                notes=str(session.get("notes") or ""),
            )
        except (TypeError, ValueError) as exc:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=f"AGENTWARD: invalid session payload: {exc}",
                exit_code=2,
                human_required=True,
                action=proposed_action,
            )
    else:
        sess = session

    if sess.status == "false_alarm":
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason="AGENTWARD: session marked false_alarm",
            exit_code=0,
            action=proposed_action,
        )

    if sess.status == "cleared":
        if require_inventory and not sess.inventory:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "AGENTWARD: status=cleared but inventory empty — clearance "
                    "without loss inventory is not load-bearing"
                ),
                exit_code=2,
                human_required=True,
                action=proposed_action,
            )
        if not (sess.clearance_token or "").strip():
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "AGENTWARD: status=cleared but clearance_token missing — "
                    "human/owner token required to lift lockdown"
                ),
                exit_code=2,
                human_required=True,
                action=proposed_action,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=(
                f"AGENTWARD ok: incident={sess.incident.incident_id} cleared "
                f"inventory={len(sess.inventory)} token=present"
            ),
            exit_code=0,
            human_required=False,
            action=proposed_action,
        )

    # open / lockdown
    if require_inventory and not sess.inventory:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=(
                f"AGENTWARD: lockdown active for incident={sess.incident.incident_id} "
                f"kind={sess.incident.kind} but inventory is empty — record lost "
                "paths/resources before any further agent work"
            ),
            exit_code=2,
            human_required=True,
            action=proposed_action,
        )

    if proposed_action and block_high_risk_while_locked:
        if is_high_risk_action(proposed_action, extra=high_risk_extra):
            sess.blocked_actions.append(proposed_action)
            return GateOutcome(
                ok=False,
                verdict="FAIL",
                reason=(
                    f"AGENTWARD: lockdown blocks high-risk action={proposed_action!r} "
                    f"after incident={sess.incident.incident_id} "
                    f"(inventory={len(sess.inventory)}) — obtain human clearance "
                    "via clear_incident before continuing (post-deletion enforcer)"
                ),
                exit_code=1,
                human_required=True,
                action=proposed_action,
            )

    # Locked but only observing / low-risk
    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"AGENTWARD: lockdown active incident={sess.incident.incident_id} "
            f"inventory={len(sess.inventory)}; proposed_action="
            f"{proposed_action!r} allowed (not high-risk) — human_required to clear"
        ),
        exit_code=0,
        human_required=True,
        action=proposed_action,
    )


def assert_post_incident_ok(
    session: EnforcementSession | dict[str, Any] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_post_incident` is ok."""
    outcome = gate_post_incident(session, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome

from typing import Any

from app.core.constants import Consensus
from app.models import Report
from app.services.work_service import WorkService


class ConsensusService:
    @staticmethod
    def calculate_work_status(votes_count: int, total_event_votes: int) -> dict[str, Any]:
        """
        Calculates the trust status and percentage for a single work based on event context.
        """
        consensus_rate = votes_count / total_event_votes if total_event_votes > 0 else 0
        percentage = int(consensus_rate * 100)

        status = "neutral"
        if votes_count >= Consensus.MIN_VOTES_FOR_VERIFICATION:
            if consensus_rate >= Consensus.VERIFICATION_THRESHOLD:
                status = "verified"
            else:
                status = "disputed"
        elif votes_count == 1:
            status = "neutral"

        return {"status": status, "percentage": percentage}

    @staticmethod
    def event_outcome(reports: list[Report]) -> dict[str, Any]:
        """What an exam's reports add up to. The single definition used by the year list,
        the exam page, work and composer pages and the statistics.

        status   "empty" (no reports), "neutral" (fewer votes than verification needs),
                 "verified" (one report holds the consensus) or "disputed".
        leader   the report with most votes, or None.
        verified the report that holds the consensus, or None.
        counted  the report that counts as "the work of this exam": the verified one, or
                 the only one when nobody has reported anything else (unconfirmed).
                 None for an empty or disputed exam.
        Report.votes must be loaded.
        """
        ranked = sorted(reports, key=lambda r: len(r.votes), reverse=True)
        total_votes = sum(len(r.votes) for r in ranked)
        verified = next(
            (
                r
                for r in ranked
                if ConsensusService.calculate_work_status(len(r.votes), total_votes)["status"]
                == "verified"
            ),
            None,
        )
        if not ranked:
            status = "empty"
        elif total_votes < Consensus.MIN_VOTES_FOR_VERIFICATION:
            status = "neutral"
        elif verified:
            status = "verified"
        else:
            status = "disputed"
        counted = verified or (ranked[0] if len(ranked) == 1 else None)
        return {
            "status": status,
            "leader": ranked[0] if ranked else None,
            "verified": verified,
            "counted": counted,
            "total_votes": total_votes,
        }

    @staticmethod
    def report_standing(report: Report, outcome: dict[str, Any]) -> str:
        """How one report stands within its exam: "verified", "unconfirmed" (the only
        report, not yet confirmed), "disputed" or "outvoted" (another work was verified)."""
        if outcome["counted"] is report:
            return "verified" if outcome["verified"] is report else "unconfirmed"
        return "outvoted" if outcome["verified"] else "disputed"

    @staticmethod
    def aggregate_event_reports(reports: list[Report]) -> dict[str, Any]:
        """
        Aggregates a list of reports for an event into view models.
        Returns serialized dicts ready for Jinja2.
        """
        total_votes = 0

        # 1. Count Total Votes
        # Note: Report.votes is expected to be loaded selectinload
        for report in reports:
            total_votes += len(report.votes)

        works_list = []
        for report in reports:
            votes_count = len(report.votes)
            metrics = ConsensusService.calculate_work_status(votes_count, total_votes)

            works_list.append(
                {
                    "report_id": report.id,
                    "work": report.work,
                    "composer": report.work.composer,
                    "votes": votes_count,
                    "percentage": metrics["percentage"],
                    "status": metrics["status"],
                    "is_flagged": report.is_flagged,
                    "details": report.movement_details,
                    "score_url": WorkService.get_score_url(report.work),
                }
            )

        # Sort
        works_list.sort(key=lambda x: x["votes"], reverse=True)

        # Event level. The exam page says "resolved" for a verified exam and "empty" for
        # reports nobody has voted on.
        outcome = ConsensusService.event_outcome(reports)
        event_status = {"verified": "resolved"}.get(outcome["status"], outcome["status"])
        if total_votes == 0:
            event_status = "empty"

        return {"works": works_list, "total_votes": total_votes, "event_status": event_status}

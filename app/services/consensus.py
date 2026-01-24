from typing import List, Dict, Any
from app.models import Report

class ConsensusService:
    @staticmethod
    def calculate_work_status(votes_count: int, total_event_votes: int) -> Dict[str, Any]:
        """
        Calculates the trust status and percentage for a single work based on event context.
        """
        consensus_rate = votes_count / total_event_votes if total_event_votes > 0 else 0
        percentage = int(consensus_rate * 100)
        
        status = "neutral"
        if votes_count >= 2:
            if consensus_rate >= 0.75:
                status = "verified"
            else:
                status = "disputed"
        elif votes_count == 1:
            status = "neutral"
            
        return {
            "status": status,
            "percentage": percentage
        }

    @staticmethod
    def aggregate_event_reports(reports: List[Report]) -> Dict[str, Any]:
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
            
            works_list.append({
                "report_id": report.id,
                "work": report.work,
                "composer": report.work.composer,
                "votes": votes_count,
                "percentage": metrics["percentage"],
                "status": metrics["status"],
                "is_flagged": report.is_flagged,
                "raw_report": report # Pass actual object just in case template needs properties not mapped
            })
            
        # Sort
        works_list.sort(key=lambda x: x["votes"], reverse=True)
        
        # Event Level Logic
        has_verified = any(w["status"] == "verified" for w in works_list)
        event_status = "neutral"
        if total_votes == 0:
            event_status = "empty"
        elif total_votes == 1:
            event_status = "neutral"
        elif has_verified:
            event_status = "resolved"
        else:
            event_status = "disputed"
            
        return {
            "works": works_list,
            "total_votes": total_votes,
            "event_status": event_status
        }

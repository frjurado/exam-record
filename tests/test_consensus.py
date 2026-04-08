import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work


@pytest.mark.asyncio
async def test_consensus_logic(client, db):
    # --- Shared data ---
    region = Region(name="Andalucia", slug="andalucia")
    discipline = Discipline(name="Piano", slug="piano")
    db.add(region)
    db.add(discipline)
    await db.commit()
    await db.refresh(region)
    await db.refresh(discipline)

    user1 = User(email="u1@test.com")
    user2 = User(email="u2@test.com")
    user3 = User(email="u3@test.com")
    db.add_all([user1, user2, user3])
    await db.commit()
    await db.refresh(user1)
    await db.refresh(user2)
    await db.refresh(user3)

    composer = Composer(name="Bach", wikidata_id="Q1")
    db.add(composer)
    await db.commit()
    await db.refresh(composer)

    work_a = Work(title="Prelude A", composer_id=composer.id)
    work_b = Work(title="Prelude B", composer_id=composer.id)
    db.add_all([work_a, work_b])
    await db.commit()
    await db.refresh(work_a)
    await db.refresh(work_b)

    # --- Case 1: Disputed (2 votes for A, 1 vote for B → 66% / 33%) ---
    event = ExamEvent(year=2026, region_id=region.id, discipline_id=discipline.id)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # One report per work (unique constraint on event_id + work_id)
    report_a = Report(user_id=user1.id, event_id=event.id, work_id=work_a.id)
    report_b = Report(user_id=user3.id, event_id=event.id, work_id=work_b.id)
    db.add_all([report_a, report_b])
    await db.commit()
    await db.refresh(report_a)
    await db.refresh(report_b)

    db.add_all(
        [
            Vote(user_id=user1.id, report_id=report_a.id),
            Vote(user_id=user2.id, report_id=report_a.id),
            Vote(user_id=user3.id, report_id=report_b.id),
        ]
    )
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2026")
    assert response.status_code == 200
    html = response.text
    assert "Prelude A" in html
    assert "Reportes conflictivos" in html
    assert "66%" in html
    assert "Prelude B" in html

    # --- Case 2: Verified (2 votes for A only → 100% ≥ 75%) ---
    event2 = ExamEvent(year=2027, region_id=region.id, discipline_id=discipline.id)
    db.add(event2)
    await db.commit()
    await db.refresh(event2)

    report_a2 = Report(user_id=user1.id, event_id=event2.id, work_id=work_a.id)
    db.add(report_a2)
    await db.commit()
    await db.refresh(report_a2)

    db.add_all(
        [
            Vote(user_id=user1.id, report_id=report_a2.id),
            Vote(user_id=user2.id, report_id=report_a2.id),
        ]
    )
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2027")
    html2 = response.text
    assert "Prelude A" in html2
    assert "Verificado por estudiantes" in html2

    # --- Case 3: Neutral (single vote for B) ---
    event3 = ExamEvent(year=2028, region_id=region.id, discipline_id=discipline.id)
    db.add(event3)
    await db.commit()
    await db.refresh(event3)

    report_b3 = Report(user_id=user3.id, event_id=event3.id, work_id=work_b.id)
    db.add(report_b3)
    await db.commit()
    await db.refresh(report_b3)

    db.add(Vote(user_id=user3.id, report_id=report_b3.id))
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2028")
    html3 = response.text
    assert "Prelude B" in html3
    assert "Reporte único para este examen" in html3

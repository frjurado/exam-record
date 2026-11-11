import pytest

from app.services import text
from app.services.titles import localize_openopus_title


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Albéniz", "albeniz"),
        ("  Dvořák,  Antonín ", "dvorak antonin"),
        ("Op. 27, n.º 2", "op 27 n 2"),
        ("op 27 nº 2", "op 27 n 2"),
        ("Sonata no. 14", "sonata n 14"),
        ("Sonata núm. 14", "sonata n 14"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert text.normalize(raw) == expected


def test_matches_requires_every_token():
    haystack = text.normalize("Sonata para piano n.º 14 en do sostenido menor, op. 27 n.º 2")
    assert text.matches(text.tokens("sonata 14"), haystack)
    assert text.matches(text.tokens("Op. 27 SONATA"), haystack)
    assert not text.matches(text.tokens("sonata 15"), haystack)
    assert text.matches([], haystack)


@pytest.mark.parametrize(
    ("raw", "title", "nickname"),
    [
        (
            'Piano Sonata no. 14 in C sharp minor, op. 27 no. 2, "Moonlight"',
            "Sonata para piano n.º 14 en do sostenido menor, op. 27 n.º 2",
            "Claro de luna",
        ),
        ("Prelude and Fugue in C major, BWV.846", "Preludio y fuga en do mayor, BWV.846", None),
        (
            "String Quartet no. 15 in A minor, op. 132",
            "Cuarteto de cuerda n.º 15 en la menor, op. 132",
            None,
        ),
        ("Symphony no. 5 in C minor, op. 67", "Sinfonía n.º 5 en do menor, op. 67", None),
        ("24 Preludes, op. 28", "24 Preludios, op. 28", None),
        ("12 Spanish Dances, op. 37, H.142", "12 Danzas españolas, op. 37, H.142", None),
        (
            "French Suite no. 5 in G major, BWV.816",
            "Suite francesa n.º 5 en sol mayor, BWV.816",
            None,
        ),
        ("Nocturne in E flat major, op. 9 no. 2", "Nocturno en mi bemol mayor, op. 9 n.º 2", None),
        (
            "Concerto for Two Violins in D minor, BWV.1043",
            "Concierto para dos violines en re menor, BWV.1043",
            None,
        ),
        ("Variations on a Theme by Paganini", "Variaciones sobre un tema de Paganini", None),
        (
            "Cello Suite no. 1 in G major, BWV.1007",
            "Suite para violonchelo n.º 1 en sol mayor, BWV.1007",
            None,
        ),
    ],
)
def test_openopus_titles_are_rendered_in_spanish(raw, title, nickname):
    assert localize_openopus_title(raw) == (title, nickname)


@pytest.mark.parametrize(
    "raw",
    [
        "Das Wohltemperierte Klavier",
        "Suite española n.º 1, op. 47",
        "Calm Sea and Prosperous Voyage, op. 112",  # unknown phrase: left whole, not half-translated
        "Thamos, King of Egypt, K.345",
        "Kinderszenen, op. 15",
    ],
)
def test_titles_outside_the_glossary_are_left_alone(raw):
    assert localize_openopus_title(raw) == (raw, None)


@pytest.mark.parametrize(
    ("raw", "nickname"),
    [
        ('Piano Sonata no. 16 in C major, K.545, "Facile"', "Fácil"),
        (
            'Divertimento in F major, K.138, "Salzburg Symphony no. 3"',
            "Sinfonía de Salzburgo n.º 3",
        ),
        # A place name with no Spanish form stays as it is.
        ('Piano Sonata no. 13 in B flat major, K. 333, "Linz"', "Linz"),
    ],
)
def test_nicknames_reported_untranslated_in_production(raw, nickname):
    assert localize_openopus_title(raw)[1] == nickname

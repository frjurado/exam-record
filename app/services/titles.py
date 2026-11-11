"""Spanish rendering of the English catalogue titles that OpenOpus returns.

OpenOpus titles follow a regular pattern ("Piano Sonata no. 14 in C sharp minor, op. 27
no. 2, "Moonlight""), so a glossary plus a few rules covers most of the catalogue. Words
the glossary does not know (proper names, titles already in German, French or Italian)
are left untouched, so the worst case is a title that stays as it was.
"""

import re

_NOTES = {"C": "do", "D": "re", "E": "mi", "F": "fa", "G": "sol", "A": "la", "B": "si"}
_ACCIDENTALS = {"sharp": " sostenido", "flat": " bemol"}
_MODES = {"major": "mayor", "minor": "menor"}

_KEY = re.compile(r"\bin ([A-G])[ -]?(sharp|flat)?[ -]?(major|minor)\b")
_NUMBER = re.compile(r"\b[Nn]os?\. ?(?=\d)")
_NICKNAME = re.compile(r',?\s*"([^"]+)"\s*$')
_EDGE_PUNCTUATION = ",.;:()"

_INSTRUMENTS = {
    "Piano": "piano",
    "Violin": "violín",
    "Viola": "viola",
    "Cello": "violonchelo",
    "Double Bass": "contrabajo",
    "Flute": "flauta",
    "Oboe": "oboe",
    "Clarinet": "clarinete",
    "Bassoon": "fagot",
    "Horn": "trompa",
    "Trumpet": "trompeta",
    "Trombone": "trombón",
    "Guitar": "guitarra",
    "Harp": "arpa",
    "Organ": "órgano",
    "Harpsichord": "clave",
    "Keyboard": "teclado",
}

# "<Instrument> <Form>" becomes "<Forma> para <instrumento>".
_SOLO_FORMS = {
    "Sonata": "Sonata",
    "Sonatas": "Sonatas",
    "Sonatina": "Sonatina",
    "Concerto": "Concierto",
    "Concertos": "Conciertos",
    "Suite": "Suite",
    "Suites": "Suites",
    "Partita": "Partita",
    "Pieces": "Piezas",
    "Piece": "Pieza",
    "Variations": "Variaciones",
    "Fantasy": "Fantasía",
    "Fantasia": "Fantasía",
}

# Fixed phrases, replaced before the word-by-word pass.
_PHRASES = {
    "String Quartet": "Cuarteto de cuerda",
    "String Quartets": "Cuartetos de cuerda",
    "String Trio": "Trío de cuerda",
    "String Quintet": "Quinteto de cuerda",
    "String Sextet": "Sexteto de cuerda",
    "Piano Trio": "Trío con piano",
    "Piano Trios": "Tríos con piano",
    "Piano Quartet": "Cuarteto con piano",
    "Piano Quintet": "Quinteto con piano",
    "Clarinet Quintet": "Quinteto con clarinete",
    "Clarinet Trio": "Trío con clarinete",
    "Horn Trio": "Trío con trompa",
    "Wind Quintet": "Quinteto de viento",
    "Wind Octet": "Octeto de viento",
    "Original Theme": "Tema original",
    "Funeral March": "Marcha fúnebre",
    "Wedding March": "Marcha nupcial",
    "Turkish March": "Marcha turca",
    "Well-tempered Clavier": "El clave bien temperado",
    "Well-Tempered Clavier": "El clave bien temperado",
    "Spanish Dances": "Danzas españolas",
    "Spanish Dance": "Danza española",
    "Hungarian Dances": "Danzas húngaras",
    "Hungarian Dance": "Danza húngara",
    "Hungarian Rhapsodies": "Rapsodias húngaras",
    "Hungarian Rhapsody": "Rapsodia húngara",
    "Slavonic Dances": "Danzas eslavas",
    "German Dances": "Danzas alemanas",
    "Polish Songs": "Canciones polacas",
    "French Suites": "Suites francesas",
    "French Suite": "Suite francesa",
    "English Suites": "Suites inglesas",
    "English Suite": "Suite inglesa",
    "Italian Concerto": "Concierto italiano",
    "Brandenburg Concertos": "Conciertos de Brandeburgo",
    "Brandenburg Concerto": "Concierto de Brandeburgo",
    "Goldberg Variations": "Variaciones Goldberg",
    "Diabelli Variations": "Variaciones Diabelli",
    "Songs without Words": "Canciones sin palabras",
    "The Art of Fugue": "El arte de la fuga",
    "Musical Offering": "Ofrenda musical",
    "Pictures at an Exhibition": "Cuadros de una exposición",
    "The Four Seasons": "Las cuatro estaciones",
}

# Nicknames with an established Spanish form. Anything else is kept as OpenOpus has it.
_NICKNAMES = {
    "Moonlight": "Claro de luna",
    "Pathétique": "Patética",
    "Pathetique": "Patética",
    "Tempest": "La tempestad",
    "Emperor": "Emperador",
    "Choral": "Coral",
    "Les Adieux": "Los adioses",
    "Farewell": "Los adioses",
    "Spring": "Primavera",
    "Ghost": "El fantasma",
    "Archduke": "Archiduque",
    "Harp": "Las arpas",
    "Eroica": "Heroica",
    "Heroic": "Heroica",
    "Unfinished": "Inacabada",
    "Trout": "La trucha",
    "Death and the Maiden": "La muerte y la doncella",
    "Raindrop": "Gota de agua",
    "Revolutionary": "Revolucionario",
    "Minute": "Minuto",
    "Winter Wind": "Viento de invierno",
    "Black Keys": "Teclas negras",
    "Surprise": "La sorpresa",
    "Italian": "Italiana",
    "Scottish": "Escocesa",
    "Reformation": "La Reforma",
    "Resurrection": "Resurrección",
    "Titan": "Titán",
    "From the New World": "Del Nuevo Mundo",
    "Funeral March": "Marcha fúnebre",
    "Facile": "Fácil",
    "Salzburg Symphony no. 1": "Sinfonía de Salzburgo n.º 1",
    "Salzburg Symphony no. 2": "Sinfonía de Salzburgo n.º 2",
    "Salzburg Symphony no. 3": "Sinfonía de Salzburgo n.º 3",
    "Jupiter": "Júpiter",
    "Prague": "Praga",
    "Paris": "París",
    "Turkish": "Turca",
    "Coronation": "Coronación",
    "Hunt": "La caza",
    "Dissonance": "Las disonancias",
    "Clock": "El reloj",
    "London": "Londres",
    "Military": "Militar",
    "Drumroll": "Redoble de timbal",
}

_WORDS = {
    "Symphony": "Sinfonía",
    "Symphonies": "Sinfonías",
    "Sonata": "Sonata",
    "Concerto": "Concierto",
    "Concertos": "Conciertos",
    "Prelude": "Preludio",
    "Preludes": "Preludios",
    "Fugue": "Fuga",
    "Fugues": "Fugas",
    "Nocturne": "Nocturno",
    "Nocturnes": "Nocturnos",
    "Waltz": "Vals",
    "Waltzes": "Valses",
    "Ballade": "Balada",
    "Ballades": "Baladas",
    "Etude": "Estudio",
    "Etudes": "Estudios",
    "Étude": "Estudio",
    "Études": "Estudios",
    "Study": "Estudio",
    "Studies": "Estudios",
    "Mazurka": "Mazurca",
    "Mazurkas": "Mazurcas",
    "Polonaise": "Polonesa",
    "Polonaises": "Polonesas",
    "Variations": "Variaciones",
    "Variation": "Variación",
    "Fantasy": "Fantasía",
    "Fantasia": "Fantasía",
    "Fantasie": "Fantasía",
    "Fantasies": "Fantasías",
    "Rhapsody": "Rapsodia",
    "Rhapsodies": "Rapsodias",
    "Rondo": "Rondó",
    "Theme": "Tema",
    "Overture": "Obertura",
    "Mass": "Misa",
    "Song": "Canción",
    "Songs": "Canciones",
    "Dance": "Danza",
    "Dances": "Danzas",
    "March": "Marcha",
    "Minuet": "Minueto",
    "Toccata": "Tocata",
    "Invention": "Invención",
    "Inventions": "Invenciones",
    "Serenade": "Serenata",
    "Bagatelle": "Bagatela",
    "Bagatelles": "Bagatelas",
    "Barcarolle": "Barcarola",
    "Caprice": "Capricho",
    "Caprices": "Caprichos",
    "Capriccio": "Capricho",
    "Romance": "Romanza",
    "Romances": "Romanzas",
    "Humoresque": "Humoresca",
    "Pieces": "Piezas",
    "Piece": "Pieza",
    "Quartet": "Cuarteto",
    "Quintet": "Quinteto",
    "Sextet": "Sexteto",
    "Octet": "Octeto",
    "Trio": "Trío",
    "Book": "Libro",
    "Orchestra": "orquesta",
    "Strings": "cuerdas",
    "Winds": "vientos",
    "Chorus": "coro",
    "Voice": "voz",
    "Hands": "manos",
    "Pianos": "pianos",
    "Violins": "violines",
    "Violas": "violas",
    "Cellos": "violonchelos",
    "Flutes": "flautas",
    "Oboes": "oboes",
    "Clarinets": "clarinetes",
    "Horns": "trompas",
    "Harpsichords": "claves",
    "Two": "Dos",
    "Three": "Tres",
    "Four": "Cuatro",
    "Five": "Cinco",
    "Six": "Seis",
    "Seven": "Siete",
    "Eight": "Ocho",
    "Twelve": "Doce",
}
_WORDS.update(_INSTRUMENTS)

_CONNECTORS = {
    "for": "para",
    "and": "y",
    "on": "sobre",
    "with": "con",
    "by": "de",
    "of": "de",
    "from": "de",
    "a": "un",
    "an": "un",
}

_PHRASE_RE = re.compile(r"\b(" + "|".join(map(re.escape, _PHRASES)) + r")\b")
_SOLO_RE = re.compile(
    r"\b("
    + "|".join(map(re.escape, _INSTRUMENTS))
    + r") ("
    + "|".join(map(re.escape, _SOLO_FORMS))
    + r")\b"
)
_SPANISH_WORDS = {
    word for text in (*_PHRASES.values(), *_WORDS.values(), "para") for word in text.split(" ")
}


def split_nickname(title: str) -> tuple[str, str | None]:
    """Separate a trailing quoted nickname: 'Sonata, op. 13, "Pathétique"' -> (..., 'Pathétique')."""
    match = _NICKNAME.search(title)
    if not match:
        return title.strip(), None
    return title[: match.start()].strip().rstrip(","), match.group(1).strip()


def _lower_first(text: str) -> str:
    return text[0].lower() + text[1:]


def _translate_words(text: str) -> str:
    """Translate glossary words, left to right.

    A word is only translated when what precedes it is already Spanish (or a number, or
    the start of the title). That keeps English phrases whole instead of half-translated:
    "Polish Songs" stays as it is rather than becoming "Polish canciones".
    """
    out: list[str] = []
    previous_ok = True
    at_start = True  # still at the first word, ignoring a leading count such as "24"
    for i, word in enumerate(text.split(" ")):
        bare = word.strip(_EDGE_PUNCTUATION)
        if bare in _WORDS and previous_ok:
            spanish = _WORDS[bare] if at_start else _lower_first(_WORDS[bare])
            out.append(word.replace(bare, spanish))
            at_start = False
        elif bare in _CONNECTORS and i > 0 and previous_ok:
            out.append(word.replace(bare, _CONNECTORS[bare]))
        else:
            out.append(word)
            at_start = at_start and bare.isdigit()
            # An untranslated capitalised word starts a phrase we do not know;
            # punctuation after it closes that phrase.
            known = bare in _SPANISH_WORDS or bare.lower() in _SPANISH_WORDS
            previous_ok = known or not bare[:1].isupper() or word[-1:] in ",:;"
            continue
        previous_ok = True
    return " ".join(out)


def to_spanish(title: str) -> str:
    """Translate the body of an OpenOpus title (without its nickname) into Spanish."""

    def at(spanish: str, m: re.Match[str]) -> str:
        # Capitalised at the start of the title, also after a leading count ("12 Danzas").
        before = m.string[: m.start()].strip()
        return spanish if not before or before.isdigit() else _lower_first(spanish)

    result = _PHRASE_RE.sub(lambda m: at(_PHRASES[m.group(1)], m), title)
    result = _SOLO_RE.sub(
        lambda m: at(_SOLO_FORMS[m.group(2)], m) + " para " + _INSTRUMENTS[m.group(1)], result
    )
    result = _translate_words(result)

    def key(m: re.Match[str]) -> str:
        return f"en {_NOTES[m.group(1)]}{_ACCIDENTALS.get(m.group(2), '')} {_MODES[m.group(3)]}"

    result = _KEY.sub(key, result)
    return _NUMBER.sub("n.º ", result)


def localize_openopus_title(raw_title: str) -> tuple[str, str | None]:
    """Return (Spanish title, nickname) for a raw OpenOpus title."""
    body, nickname = split_nickname(raw_title)
    return to_spanish(body), _NICKNAMES.get(nickname, nickname) if nickname else None

"""The rules claim text follows in each partner's language (ADR-010).

Every language keeps the same guarantees: no number written out (digits or number words), no
name written out (squad names, and any capitalised word that is not a known term), nothing about
what happens later, and only printable characters of the language. English also has a lowercase
allowlist (`vocabulary.txt`); Spanish and German do not, because a localised insight may not add
facts at all: its references are checked against the canonical English insight instead.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

from fourth_official_verifier.vocabulary import NUMBER_WORDS, SENTENCE_OPENERS, TERMS, known


@dataclass(frozen=True, slots=True)
class Language:
    locale: str
    # Characters allowed outside references beyond printable ASCII.
    letters: str
    word: re.Pattern[str]
    # Number words, compared after folding case, accents and ß (`fold`).
    number_words: frozenset[str]
    future: re.Pattern[str]
    # Capitalised words allowed only where a sentence starts.
    openers: frozenset[str]
    # Whether a capitalised word may stand anywhere (a term of the game, a German noun).
    capitalised: Callable[[str], bool]
    # The lowercase allowlist, where a language has one.
    known: Callable[[str], bool] | None
    # Phrases with a number word that state no count ("the final third").
    place_phrases: re.Pattern[str] | None
    # A reference may take this possessive ending: "{{club:NGT}}'s", "{{club:NGT}}s".
    possessive: str
    # Punctuation that may stand before the first word of a sentence.
    leading: str
    # Number words a closed list cannot hold (compounds, ordinals), matched on the folded word.
    number_forms: tuple[re.Pattern[str], ...] = ()
    # Phrases that state a count, matched on the folded text: "un par de".
    number_phrases: re.Pattern[str] | None = None
    # Words the future pattern catches that are not about the future: "alegría", "mayoría".
    not_future: frozenset[str] = frozenset()

    def states_number(self, word: str) -> bool:
        """Whether a word states a number: a number word, or a numeral formed from one."""
        folded = fold(word)
        parts = folded.split("-")
        if folded in self.number_words or any(part in self.number_words for part in parts):
            return True
        return any(form.fullmatch(folded) for form in self.number_forms)

    def future_in(self, plain: str) -> list[str]:
        found = (m.group(0) for m in self.future.finditer(plain))
        return [f for f in found if f.lower() not in self.not_future]


def fold(text: str) -> str:
    """Case, accents and ß folded away: "Dieciséis", "dieciseis"; "dreißig", "dreissig"."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _words(text: str) -> frozenset[str]:
    return frozenset(fold(word) for word in text.split())


ENGLISH = Language(
    locale="en-GB",
    letters="",
    word=re.compile(r"[A-Za-z][A-Za-z'_-]*"),
    number_words=NUMBER_WORDS,
    future=re.compile(
        r"\b(will|would|shall|soon|later|afterwards?|shortly|finally|eventually|next|going to|"
        r"about to|go on to|goes on to|went on to|full[- ]time|final whistle|final score|"
        r"in the end)\b",
        re.IGNORECASE,
    ),
    openers=SENTENCE_OPENERS,
    capitalised=lambda word: word in TERMS,
    known=known,
    place_phrases=re.compile(r"\bfinal[ -]third\b", re.IGNORECASE),
    possessive="(?:['\u2019]s\\b|s['\u2019])",
    leading=" \"'(",
)

_LATIN_WORD = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")

_ES_ORDINAL = (
    r"(primer|primer[oa]s?|segund[oa]s?|tercer|tercer[oa]s?|cuart[oa]s?|quint[oa]s?|sext[oa]s?|"
    r"(septim|setim|octav|noven|non|decim|undecim|duodecim|vigesim|trigesim)[oa]s?)"
)
SPANISH = Language(
    locale="es-MX",
    letters="áéíóúüñÁÉÍÓÚÜÑ¡¿«»",
    word=_LATIN_WORD,
    number_words=_words(
        """
        cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince
        veinte treinta cuarenta cincuenta sesenta setenta ochenta noventa cien ciento mil
        millón millones millar millares centenar centenares decena decenas docena docenas
        doble dobles doblete dobletes triple triples triplete tripletes cuádruple quíntuple
        mitad mitades tercio tercios dúo dúos trío tríos cuarteto cuartetos quinteto quintetos
        sexteto sextetos hat-trick
        """
    ),
    number_forms=(
        re.compile(r"dieci\w+|veinti\w+|\w+cient[oa]s|quinient[oa]s"),
        # Fused ordinals: decimoquinto, vigesimoprimer.
        re.compile(r"(decimo|vigesimo|trigesimo|cuadragesimo)\w*"),
        re.compile(_ES_ORDINAL),
        re.compile(r"(once|doce|trece|catorce|quince|dieci\w+|veinte|veinti\w+|treinta)av[oa]s?"),
    ),
    number_phrases=re.compile(r"(?<!\w)(un par|unos pares|treinta y|cuarenta y)(?!\w)"),
    future=re.compile(
        r"(?<!\w)(va a|van a|vamos a|voy a|vas a|a punto de|está por|están por|pronto|luego|"
        r"enseguida|en breve|a continuación|más adelante|más tarde|tarde o temprano|al final|"
        r"después(?! de)|silbatazo final|pitido final|marcador final|resultado final|mañana|"
        r"esta noche|esta tarde|próximo|próxima|"
        r"próximos|próximas|"
        # Future and conditional tenses: ganará, marcarán, ganaría, marcarían.
        r"[^\W\d_]+(?:ré|rás|rá|remos|réis|rán|ría|rías|ríamos|ríais|rían))(?!\w)",
        re.IGNORECASE,
    ),
    not_future=frozenset(
        """
        alegría galería galerías batería baterías lotería mayoría minoría teoría porquería
        tontería cafetería librería ría atrás detrás
        """.split()  # noqa: SIM905 - a word list reads best as text
    ),
    openers=_words(
        """
        el la los las un una unos unas lo al del tras con sin desde hasta en por para ante
        entre sobre durante contra según hacia gol golazo ocasión gran nueva nuevo otra otro
        penal penalti tarjeta roja amarilla presión ahora así aquí ya pese aunque cuando
        mientras como que qué cómo y o pero también todo toda nada nadie ni no sí
        balón remate pase centro contragolpe jugada error parada después antes
        casi muy más menos solo sólo incluso entonces allí aquí se le les su sus este esta
        estos estas ese esa esos esas aquel aquella cada mucho mucha poco poca tanto tanta
        """
    ),
    capitalised=lambda word: word in TERMS,
    known=None,
    # The near and far post name places, as "the final third" does in English.
    place_phrases=re.compile(r"(?<!\w)(primer|segundo) palo(?!\w)", re.IGNORECASE),
    possessive=r"",
    leading=" \"'(¡¿«",
)


_GERMAN_ENDINGS = ("s", "es", "n", "en", "e")


@cache
def _german_nouns() -> frozenset[str]:
    text = files("fourth_official_verifier").joinpath("nouns_de.txt").read_text("utf-8")
    return frozenset(
        word for line in text.splitlines() if not line.startswith("#") for word in line.split()
    )


def _is_german_noun(word: str) -> bool:
    """A known football noun, or a compound of them: Ballgewinn, Torchance, Spielstand."""
    nouns = _german_nouns()
    lower = word.lower()
    if lower in nouns:
        return True
    # Split into stems of at least three letters, with a linking s or n allowed between them.
    reachable = {0}
    for start in range(len(lower)):
        if start not in reachable:
            continue
        for end in range(start + 3, len(lower) + 1):
            if lower[start:end] in nouns:
                reachable.add(end)
                # A linking s or n joins two stems; it never ends the word ("Tors", "Torn").
                if lower[end : end + 1] in {"s", "n"} and end + 1 < len(lower):
                    reachable.add(end + 1)
    # A noun may end in its case or plural ending: des Gegners, des Tors, die Torchancen.
    ends = {len(lower) - len(ending) for ending in _GERMAN_ENDINGS if lower.endswith(ending)}
    whole = len(lower) in reachable or bool(ends & reachable)
    return whole and not GERMAN.states_number(lower)


_DE_UNITS = r"(ein|zwei|drei|vier|funf|sechs|sieben|acht|neun)"
_DE_TENS = r"(zwanzig|dreissig|vierzig|funfzig|sechzig|siebzig|achtzig|neunzig)"
_DE_CARDINAL = (
    r"(ein|zwei|zwo|drei|vier|funf|sechs|sieben|acht|neun|zehn|elf|zwolf|"
    r"\w+zehn|\w*zig|\w*hundert|\w*tausend)"
)
GERMAN = Language(
    locale="de-DE",
    # Umlauts, eszett, and the German low and high quotation marks, double and single.
    letters="äöüßÄÖÜ\u201e\u201c\u201a\u2018«»",
    word=_LATIN_WORD,
    number_words=_words(
        """
        null eins zwei zwo drei vier fünf sechs sieben acht neun zehn elf zwölf zwanzig
        dreißig vierzig fünfzig sechzig siebzig achtzig neunzig hundert hunderte tausend
        tausende million millionen dutzend dutzende paar
        """
    ),
    number_forms=(
        # Compound cardinals: dreiundzwanzig, zweihundert, dreitausend.
        re.compile(rf"{_DE_UNITS}und{_DE_TENS}\w*|{_DE_UNITS}?(hundert|tausend)\w*|\w+zehn"),
        # Ordinals, and first, secondly...: zehnte, achten, zwanzigste, erstens.
        re.compile(
            r"(erst|zweit|dritt|viert|funft|sechst|siebt|siebent|acht|neunt|zehnt|elft|zwolft|"
            r"\w+zehnt|\w*zigst|\w*ssigst|\w*hundertst|\w*tausendst)(e|er|en|es|em|ens)"
        ),
        # How many times, and counts as nouns: zehnmal, Zweier, Viererkette.
        re.compile(
            rf"{_DE_CARDINAL}mal|(zwei|drei|vier|funf|sechs|sieben|acht|neun|zehn|elf|zwolf)er\w*"
        ),
        # Doubles, halves: doppelt, Doppelpack, Halbzeit, Spielhälfte.
        re.compile(r"doppel\w*|halb\w*|\w*halfte\w*|dreifach\w*|\w+fach"),
        # Firsts and one-offs, and decimals written out: erstmals, einmalig, nullkommafünf.
        re.compile(r"erstmal\w*|einmalig\w*|\w*komma\w+"),
    ),
    future=re.compile(
        r"(?<!\w)(wird|werden|wirst|werde|werdet|würde|würden|würdest|dürfte|dürften|will|"
        r"soll|sollte|sollten|könnte|könnten|müsste|müssten|bald|später|demnächst|künftig|"
        r"zukünftig|gleich|danach|darauf|anschließend|nachher|hinterher|alsbald|fortan|"
        r"spätestens|bevorstehend\w*|schlusspfiff|"
        r"endstand|endergebnis|am ende|zum ende|noch vor der pause|bis zur pause|nächste|"
        r"nächsten|nächster|nächstes)(?!\w)",
        re.IGNORECASE,
    ),
    openers=_words(
        """
        der die das den dem des ein eine einen einem einer eines nach mit seit bei vor in im
        am an auf aus durch gegen ohne unter über trotz während wegen so damit jetzt nun dann
        doch aber und auch noch nur schon wieder hier da dort davor zuvor plötzlich
        früh spät kurz große großer großes starke starker klare klarer neue neuer
        er sie es wir ihr man viel viele mehr weniger jedoch dahinter weiter
        """
    ),
    capitalised=lambda word: word in TERMS or _is_german_noun(word),
    known=None,
    place_phrases=None,
    possessive=r"(?:s\b)",
    leading=" \"'(\u201e\u201a«",
)

LANGUAGES: dict[str, Language] = {
    language.locale: language for language in (ENGLISH, SPANISH, GERMAN)
}

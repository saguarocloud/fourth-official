"""Words a claim may capitalise without them being a name.

Mid-sentence, only these terms may start with a capital letter. At the start of a sentence, a
capitalised word must be one of the common sentence openers below; anything else could be a name
the model invented, and names must be references.
"""

TERMS = frozenset({"VAR", "PPDA", "AI", "Meridian", "League"})

SENTENCE_OPENERS = frozenset(
    """
    a after against all also an and another any as at back before behind being both but by
    certainly clearly control despite during each early either even every few for from half
    having here how however if in inside into it its just late leading less little long many
    meanwhile more most much neither never no none nor not now once only or other out over
    possession pressing pressure since so still such than that the their them then there these
    they this those though through throughout thus to too under until up what when where whether
    which while who why with within without yet
    """.split()  # noqa: SIM905 - a word list reads best as text
)

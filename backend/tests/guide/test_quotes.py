from cressey.domain.guides import Unit
from cressey.guide.quotes import verify_quote

U = Unit(
    id="anssi-fr:R9",
    source="anssi",
    lang="fr",
    title="R9",
    text="Un système d’IA doit être configuré de manière à ne pas être en mesure d’exécuter des actions critiques.",
)


def test_verify_quote_accepts_typographic_variants():
    assert verify_quote(
        "un système d'IA doit être  configuré de manière à ne pas être en mesure", U
    )


def test_verify_quote_rejects_invented_text():
    assert not verify_quote(
        "le système doit toujours demander l'accord du directeur général avant", U
    )


def test_verify_quote_rejects_too_short_or_too_long():
    assert not verify_quote("doit être configuré", U)
    assert not verify_quote(" ".join(["mot"] * 31), U)

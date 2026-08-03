from app.pipeline.recognition.instruments import identify


def test_nome_exato():
    assert identify("Trompete")[0] == "Trompete"


def test_voz_arabe():
    canon, voice, _conf = identify("Clarinete 1º")
    assert canon == "Clarinete"
    assert voice == 1


def test_voz_romana():
    canon, voice, _ = identify("Trompete III")
    assert canon == "Trompete"
    assert voice == 3


def test_alias_ingles_com_tonalidade():
    canon, voice, _ = identify("Trumpet in Bb II")
    assert canon == "Trompete"
    assert voice == 2


def test_sax():
    assert identify("Saxofone Alto Mib")[0] == "Sax Alto"
    assert identify("Baritone Sax")[0] == "Sax Barítono"


def test_bombardino():
    assert identify("Euphonium")[0] == "Bombardino"


def test_percussao():
    assert identify("Bass Drum")[0] == "Percussão"


def test_desconhecido_preservado():
    canon, _, conf = identify("Theremin")
    assert canon == "Theremin"
    assert conf <= 0.5


def test_abreviaturas_americanas():
    """Abreviaturas típicas de partituras impressas (Picc., B. Cl., …)."""
    esperados = {
        "Picc.": "Flautim",
        "Fl.": "Flauta",
        "Ob.": "Oboé",
        "Cl.": "Clarinete",
        "B. Cl.": "Clarinete Baixo",
        "Bsn.": "Fagote",
        "Alto Sax.": "Sax Alto",
        "Ten. Sax.": "Sax Tenor",
        "Bari. Sax.": "Sax Barítono",
        "Hn.": "Trompa",
        "Tpt.": "Trompete",
        "Tbn.": "Trombone",
        "B. Tbn.": "Trombone",
        "Perc.": "Percussão",
        "Timp.": "Tímpanos",
    }
    for abrev, canon in esperados.items():
        assert identify(abrev)[0] == canon, f"{abrev} devia dar {canon}"


def test_bass_sozinho_nao_vira_tuba():
    """«bass» é ambíguo numa banda — um nome errado é pior do que nenhum."""
    assert identify("Bass Drum")[0] == "Percussão"
    assert identify("Bass Clarinet")[0] == "Clarinete Baixo"
    assert identify("Bass Trombone")[0] == "Trombone"
    assert identify("Double Bass")[0] == "Contrabaixo"


def test_texto_colado_do_ocr():
    """O OCR devolve as palavras coladas: «AltoSaxophoneII»."""
    assert identify("AltoSaxophone")[0] == "Sax Alto"
    assert identify("BaritoneSaxophon")[0] == "Sax Barítono"
    assert identify("ClarinetinBb")[0] == "Clarinete"
    assert identify("TrumpetinBb")[0] == "Trompete"
    canon, voice, _ = identify("FluteII")
    assert (canon, voice) == ("Flauta", 2)
    canon, voice, _ = identify("BassoonII")
    assert (canon, voice) == ("Fagote", 2)


def test_abreviaturas_com_voz():
    canon, voice, _ = identify("Cl. 2")
    assert canon == "Clarinete"
    assert voice == 2
    canon, voice, _ = identify("Tpt. II")
    assert canon == "Trompete"
    assert voice == 2

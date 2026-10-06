import pytest

from app.db import get_db
from app.localidades import resolver_municipio
from app.util import (
    formatar_numero, formatar_quantidade, formatar_reais, formatar_telefone, ler_quantidade, ler_telefone,
    link_whatsapp, normalizar_busca, por_unidade, reais_para_centavos,
)


@pytest.mark.parametrize("texto, centavos", [
    ("147", 14700), ("147,5", 14750), ("147,50", 14750), ("1.234,56", 123456),
    ("1234.56", 123456), ("R$ 2.000,00", 200000), ("0,01", 1),
    ("100.000", 10_000_000), ("1.250.000", 125_000_000), ("147.5", 14750), ("12.50", 1250),
])
def test_reais_para_centavos(texto, centavos):
    assert reais_para_centavos(texto) == centavos


@pytest.mark.parametrize("texto", ["", "abc", "1,2,3", "NaN", "inf"])
def test_reais_invalidos(texto):
    with pytest.raises(ValueError):
        reais_para_centavos(texto)


def test_formatacao_brasileira():
    assert formatar_reais(123456) == "R$ 1.234,56"
    assert formatar_reais(5) == "R$ 0,05"
    assert formatar_reais(None) == "A combinar"
    assert formatar_numero(30.0) == "30"
    assert formatar_numero(2.5) == "2,5"
    assert formatar_numero(1234.5) == "1.234,5"
    assert ler_quantidade("2,5") == 2.5


def test_quantidades_e_unidades():
    assert formatar_quantidade(30, "t") == "30 toneladas"
    assert formatar_quantidade(1, "t") == "1 tonelada"
    assert formatar_quantidade(500, "sc60") == "500 sacas de 60 kg"
    assert por_unidade("sc60") == "por saca de 60 kg"
    assert por_unidade("cab") == "por cabeça"


def test_normalizar_busca():
    assert normalizar_busca("  Café   Arábica ") == "cafe arabica"
    assert normalizar_busca("Pulverização") == "pulverizacao"


@pytest.mark.parametrize("texto", ["Uberaba/MG", "uberaba - mg", "UBERABA MG", "Uberaba, MG", " uberaba/mg "])
def test_resolver_municipio_formatos(app, texto):
    with app.app_context():
        assert resolver_municipio(get_db(), texto) == 3170107


@pytest.mark.parametrize("texto", ["Uberaba", "Uberaba/GO", "Cidade Inventada/MG", "Uberaba/XX", ""])
def test_resolver_municipio_invalido(app, texto):
    with app.app_context():
        assert resolver_municipio(get_db(), texto) is None


def test_resolver_municipio_com_acento(app):
    with app.app_context():
        assert resolver_municipio(get_db(), "goiania/go") == 5208707


@pytest.mark.parametrize("texto, digitos", [
    ("(34) 99876-5432", "34998765432"),
    ("34 3333-0000", "3433330000"),
    ("+55 34 99876 5432", "34998765432"),
    ("55 34 3333 0000", "3433330000"),
    ("(55) 99876-5432", "55998765432"),  # DDD 55 (RS) não é confundido com o código do país
])
def test_ler_telefone(texto, digitos):
    assert ler_telefone(texto) == digitos


@pytest.mark.parametrize("texto", ["99876-5432", "0800 123 4567", "abc", "", "34 9 9876 54321"])
def test_telefone_invalido(texto):
    with pytest.raises(ValueError):
        ler_telefone(texto)


def test_formatar_telefone_e_whatsapp():
    assert formatar_telefone("34998765432") == "(34) 99876-5432"
    assert formatar_telefone("3433330000") == "(34) 3333-0000"
    assert link_whatsapp("34998765432") == "https://wa.me/5534998765432"

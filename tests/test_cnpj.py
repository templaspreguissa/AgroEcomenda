"""CNPJ numérico e alfanumérico (Receita Federal, IN RFB nº 2.229/2024)."""
import pytest

from app import cnpj


@pytest.mark.parametrize("texto", [
    "11.222.333/0001-81",
    "11222333000181",
    "12.ABC.345/01DE-35",  # alfanumérico (julho de 2026 em diante)
    "12abc34501de35",      # minúsculas são aceitas e viram maiúsculas
    " 12.ABC.345/01DE-35 ",
])
def test_cnpjs_validos(texto):
    assert cnpj.valido(texto)


@pytest.mark.parametrize("texto", [
    "11.222.333/0001-82",  # dígito verificador errado
    "12.ABC.345/01DE-36",
    "00.000.000/0000-00",  # sequência repetida passa no cálculo, mas não é CNPJ
    "AAAAAAAAAAAAAA",
    "1122233300018",       # 13 caracteres
    "12.ABC.345/01DE-3X",  # dígito verificador com letra
    "12.ABC.345/01D!-35",
    "",
    None,
])
def test_cnpjs_invalidos(texto):
    assert not cnpj.valido(texto)


def test_normalizar_e_formatar():
    assert cnpj.normalizar("12.abc.345/01de-35") == "12ABC34501DE35"
    assert cnpj.formatar("12ABC34501DE35") == "12.ABC.345/01DE-35"
    assert cnpj.formatar("11222333000181") == "11.222.333/0001-81"


def test_digitos_de_um_cnpj_novo():
    base = "AGRO2026PROD"
    completo = base + cnpj.digitos_verificadores(base)
    assert cnpj.valido(completo)

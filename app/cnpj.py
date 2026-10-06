"""Validação de CNPJ, no formato numérico e no alfanumérico.

Desde julho de 2026, a Receita Federal atribui CNPJ alfanumérico às novas inscrições
(Instrução Normativa RFB nº 2.229/2024). Os 12 primeiros caracteres podem ter letras
maiúsculas e números, e os 2 dígitos verificadores continuam numéricos. O cálculo segue o
módulo 11, trocando cada caractere pelo código ASCII menos 48 ('0' = 0, 'A' = 17, 'Z' = 42).
Os CNPJs só com números seguem válidos e o cálculo dá o mesmo resultado para eles.
"""
import re

PESOS_PRIMEIRO = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_SEGUNDO = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
FORMATO = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def normalizar(texto):
    """Tira pontos, barra, traço e espaços, e passa para maiúsculas."""
    return re.sub(r"[.\-/\s]", "", texto or "").upper()


def _digito(base, pesos):
    soma = sum((ord(caractere) - 48) * peso for caractere, peso in zip(base, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def digitos_verificadores(base12):
    primeiro = _digito(base12, PESOS_PRIMEIRO)
    return primeiro + _digito(base12 + primeiro, PESOS_SEGUNDO)


def valido(texto):
    cnpj = normalizar(texto)
    if not FORMATO.match(cnpj) or len(set(cnpj)) == 1:
        return False
    return cnpj[12:] == digitos_verificadores(cnpj[:12])


def formatar(cnpj):
    """'11222333000181' -> '11.222.333/0001-81'."""
    if not cnpj or len(cnpj) != 14:
        return cnpj or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

"""Funções de apoio: busca sem acentos, valores em reais, quantidades, unidades e datas."""
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Nome da unidade no singular e no plural, para frases como "30 toneladas" e "R$ 150,00 por tonelada".
UNIDADES = {
    "kg": ("kg", "kg"),
    "t": ("tonelada", "toneladas"),
    "sc60": ("saca de 60 kg", "sacas de 60 kg"),
    "@": ("arroba", "arrobas"),
    "L": ("litro", "litros"),
    "cab": ("cabeça", "cabeças"),
    "un": ("unidade", "unidades"),
    "ha": ("hectare", "hectares"),
    "h": ("hora", "horas"),
    "serv": ("serviço", "serviços"),
}

TRANSPORTE = {
    "comprador_retira": "Comprador retira",
    "vendedor_entrega": "Vendedor entrega",
    "a_combinar": "Transporte a combinar",
}

STATUS_ENCOMENDA = {
    "aberta": "Aberta",
    "em_negociacao": "Em negociação",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
    "expirada": "Prazo encerrado",
}

STATUS_PROPOSTA = {
    "pendente": "Aguardando resposta",
    "aceita": "Aceita",
    "recusada": "Recusada",
    "retirada": "Retirada",
    "nao_selecionada": "Não selecionada",
    "concluida": "Concluída",
    "cancelada": "Cancelada",
}

MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]


def hoje():
    """Data de hoje no fuso do servidor (prazos são datas locais)."""
    return date.today()


def agora_utc_texto():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def normalizar_busca(texto):
    """Minúsculas e sem acentos: 'Café' e 'cafe' viram a mesma coisa na busca."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def _decimal(texto):
    """Aceita '1.234,56', '1234,56' e '1234.56'."""
    if texto is None:
        raise ValueError("vazio")
    limpo = str(texto).strip().replace("R$", "").replace(" ", "")
    if not limpo:
        raise ValueError("vazio")
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(limpo)
    except InvalidOperation as erro:
        raise ValueError("número inválido") from erro
    if not valor.is_finite():
        raise ValueError("número inválido")
    return valor


def reais_para_centavos(texto):
    valor = _decimal(texto)
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ler_quantidade(texto):
    valor = _decimal(texto)
    return float(valor.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def formatar_reais(centavos):
    if centavos is None:
        return "A combinar"
    inteiro, resto = divmod(int(centavos), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def formatar_numero(valor):
    """30.0 -> '30', 2.5 -> '2,5', 1234.5 -> '1.234,5'."""
    if valor is None:
        return ""
    texto = f"{float(valor):,.3f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_quantidade(valor, sigla):
    singular, plural = UNIDADES.get(sigla, (sigla, sigla))
    return f"{formatar_numero(valor)} {singular if float(valor) == 1 else plural}"


def por_unidade(sigla):
    return f"por {UNIDADES.get(sigla, (sigla, sigla))[0]}"


def data_br(texto_ou_data):
    """'2026-11-15' -> '15 nov. 2026'."""
    if not texto_ou_data:
        return ""
    if isinstance(texto_ou_data, str):
        texto_ou_data = date.fromisoformat(texto_ou_data[:10])
    return f"{texto_ou_data.day} {MESES[texto_ou_data.month - 1]} {texto_ou_data.year}"


def prazo_relativo(texto_data):
    dias = (date.fromisoformat(texto_data[:10]) - hoje()).days
    if dias < 0:
        return "prazo encerrado"
    if dias == 0:
        return "vence hoje"
    if dias == 1:
        return "falta 1 dia"
    return f"faltam {dias} dias"


def primeiro_nome(nome):
    return (nome or "").split()[0] if (nome or "").split() else ""


def registrar_filtros(app):
    app.add_template_filter(formatar_reais, "reais")
    app.add_template_filter(formatar_numero, "numero")
    app.add_template_filter(data_br, "data_br")
    app.add_template_filter(prazo_relativo, "prazo_relativo")
    app.add_template_filter(primeiro_nome, "primeiro_nome")
    app.add_template_filter(por_unidade, "por_unidade")
    app.add_template_global(formatar_quantidade, "quantidade")
    app.add_template_global(TRANSPORTE, "TRANSPORTE")
    app.add_template_global(STATUS_ENCOMENDA, "STATUS_ENCOMENDA")
    app.add_template_global(STATUS_PROPOSTA, "STATUS_PROPOSTA")

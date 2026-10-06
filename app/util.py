"""Funções de apoio: busca sem acentos, valores em reais, quantidades, unidades e datas."""
import re
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
    "dz": ("dúzia", "dúzias"),
    "mc": ("maço", "maços"),
    "cx": ("caixa", "caixas"),
    "bdj": ("bandeja", "bandejas"),
    "pct": ("pacote", "pacotes"),
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

STATUS_PRODUTO = {
    "ativo": "Ativo",
    "pausado": "Pausado",
    "encerrado": "Encerrado",
    "oculto": "Oculto pela moderação",
}

TIPOS_COMERCIO = {
    "mercado": "Mercado ou supermercado",
    "hortifruti": "Hortifrúti ou sacolão",
    "restaurante": "Restaurante, bar ou lanchonete",
    "padaria": "Padaria ou confeitaria",
    "distribuidor": "Distribuidor ou atacadista",
    "cooperativa": "Cooperativa",
    "agroindustria": "Agroindústria",
    "emporio": "Empório, feira ou loja de produtos naturais",
    "outro": "Outro tipo de comércio",
}

FORMAS_VENDA = {
    "vende_retirada": "Retirada na propriedade ou no ponto de venda",
    "vende_entrega": "Entrega na região",
    "vende_feira": "Feira ou ponto fixo",
    "vende_envio": "Envio para outras regiões (a combinar)",
}

ORGANICO = {
    "nao": "Não",
    "certificado": "Sim, com certificação",
    "ocs": "Sim, venda direta com Organização de Controle Social (OCS)",
}

MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
MESES_POR_EXTENSO = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
                     "Setembro", "Outubro", "Novembro", "Dezembro"]

DISPONIBILIDADE = {
    "ano_todo": "O ano todo",
    "safra": "Só em alguns meses (safra)",
    "sob_encomenda": "Sob encomenda",
}


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
    """Aceita '1.234,56', '1234,56', '1234.56' e '100.000' (cem mil, como se escreve no Brasil)."""
    if texto is None:
        raise ValueError("vazio")
    limpo = str(texto).strip().replace("R$", "").replace(" ", "")
    if not limpo:
        raise ValueError("vazio")
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpo):
        limpo = limpo.replace(".", "")  # pontos separando milhares, sem centavos
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


def ler_telefone(texto):
    """'(34) 99999-0000' ou '+55 34 99999 0000' -> '34999990000'. Exige DDD. ValueError se inválido."""
    digitos = re.sub(r"\D", "", texto or "")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11) or digitos[0] == "0":
        raise ValueError("telefone inválido")
    return digitos


def formatar_telefone(digitos):
    if not digitos:
        return ""
    return f"({digitos[:2]}) {digitos[2:-4]}-{digitos[-4:]}"


def link_whatsapp(digitos):
    return f"https://wa.me/55{digitos}"


def bit_do_mes(data=None):
    """Bit do mês na máscara de safra (bit 0 = janeiro)."""
    return 1 << ((data or hoje()).month - 1)


def em_safra(mascara, data=None):
    return bool(mascara & bit_do_mes(data))


def descrever_meses(mascara):
    """Máscara de meses -> 'mar. a jun.', 'nov. a fev.' ou 'jan., abr. a jun. e out.'."""
    if not mascara:
        return ""
    if mascara == 0b111111111111:
        return "o ano todo"
    # Conta a partir de janeiro. Se a safra vira o ano (dezembro e janeiro), começa logo depois de um
    # mês fora da safra, para juntar dezembro e janeiro numa faixa só ("nov. a fev.").
    vira_o_ano = mascara & 1 and mascara >> 11 & 1
    inicio = next(mes for mes in range(12) if not mascara >> mes & 1) if vira_o_ano else 11
    trechos, atual = [], []
    for mes in ((inicio + 1 + passo) % 12 for passo in range(12)):
        if mascara >> mes & 1:
            atual.append(mes)
        elif atual:
            trechos.append(atual)
            atual = []
    if atual:
        trechos.append(atual)
    partes = [MESES[t[0]] if len(t) == 1 else f"{MESES[t[0]]} a {MESES[t[-1]]}" for t in trechos]
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]


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
    app.add_template_global(STATUS_PRODUTO, "STATUS_PRODUTO")
    app.add_template_global(DISPONIBILIDADE, "DISPONIBILIDADE")
    app.add_template_filter(descrever_meses, "meses")
    app.add_template_global(em_safra, "em_safra")
    app.add_template_filter(formatar_telefone, "telefone")
    app.add_template_global(link_whatsapp, "link_whatsapp")
    app.add_template_global(TIPOS_COMERCIO, "TIPOS_COMERCIO")
    app.add_template_global(FORMAS_VENDA, "FORMAS_VENDA")
    app.add_template_global(ORGANICO, "ORGANICO")

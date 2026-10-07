"""Regras de negócio, separadas por assunto.

Toda mudança de status passa por estes módulos, dentro de uma transação, e os UPDATEs conferem
o status atual na própria consulta. O resto do sistema usa `from .. import servicos` e chama
`servicos.<função>`, sem precisar saber em qual módulo ela está.
"""
from . import contratos, conversas
from .alertas import avisar_lojas_da_regiao, avisar_produtores_da_regiao
from .comum import (
    SQL_PROPOSTA, RegraNegocio, abrir_aviso, avisos_do_usuario, buscar_proposta, marcar_todos_lidos, notificar,
    total_de_avisos,
)
from .encomendas import (
    SQL_ENCOMENDA, STATUS_ENCOMENDA_ATIVA, aceitar_proposta, buscar_encomenda, cancelar_encomenda,
    criar_encomenda, editar_encomenda, editar_proposta, enviar_proposta, expirar_encomendas_vencidas,
    pode_editar_encomenda, proposta_pendente_do_vendedor, propostas_da_encomenda, recusar_proposta,
    retirar_proposta,
)
from .produtos import (
    SQL_PRODUTO, TRANSICOES_PRODUTO, atributos_do_produto, buscar_produto, criar_produto, editar_produto,
    editar_proposta_produto, enviar_proposta_produto, fotos_do_produto, mudar_status_produto,
    proposta_pendente_do_comprador, propostas_do_produto, responder_proposta_produto, retirar_proposta_produto,
)

__all__ = [
    "RegraNegocio", "SQL_ENCOMENDA", "SQL_PRODUTO", "SQL_PROPOSTA", "STATUS_ENCOMENDA_ATIVA", "TRANSICOES_PRODUTO",
    "abrir_aviso", "aceitar_proposta", "atributos_do_produto", "avisar_lojas_da_regiao",
    "avisar_produtores_da_regiao", "avisos_do_usuario", "buscar_encomenda", "buscar_produto", "buscar_proposta",
    "cancelar_encomenda", "contratos", "conversas", "criar_encomenda", "criar_produto", "editar_encomenda", "editar_produto",
    "editar_proposta", "editar_proposta_produto", "enviar_proposta", "enviar_proposta_produto",
    "expirar_encomendas_vencidas", "fotos_do_produto", "marcar_todos_lidos", "mudar_status_produto", "notificar",
    "pode_editar_encomenda", "proposta_pendente_do_comprador", "proposta_pendente_do_vendedor",
    "propostas_da_encomenda", "propostas_do_produto", "recusar_proposta", "responder_proposta_produto",
    "retirar_proposta", "retirar_proposta_produto", "total_de_avisos",
]

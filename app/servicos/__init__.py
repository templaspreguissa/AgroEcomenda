"""Regras de negócio, separadas por assunto.

Toda mudança de status passa por estes módulos, dentro de uma transação, e os UPDATEs conferem
o status atual na própria consulta. O resto do sistema usa `from .. import servicos` e chama
`servicos.<função>`, sem precisar saber em qual módulo ela está.
"""
from .comum import SQL_PROPOSTA, RegraNegocio, buscar_proposta, notificar
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
    "SQL_ENCOMENDA", "SQL_PRODUTO", "SQL_PROPOSTA", "STATUS_ENCOMENDA_ATIVA", "TRANSICOES_PRODUTO",
    "RegraNegocio", "aceitar_proposta", "atributos_do_produto", "buscar_encomenda", "buscar_produto",
    "buscar_proposta", "cancelar_encomenda", "criar_encomenda", "criar_produto", "editar_encomenda",
    "editar_produto", "editar_proposta", "editar_proposta_produto", "enviar_proposta", "enviar_proposta_produto",
    "expirar_encomendas_vencidas", "fotos_do_produto", "mudar_status_produto", "notificar",
    "pode_editar_encomenda", "proposta_pendente_do_comprador", "proposta_pendente_do_vendedor",
    "propostas_da_encomenda", "propostas_do_produto", "recusar_proposta", "responder_proposta_produto",
    "retirar_proposta", "retirar_proposta_produto",
]

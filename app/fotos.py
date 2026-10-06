"""Upload seguro de fotos de produtos e vitrines (OWASP File Upload Cheat Sheet).

- só JPEG, PNG ou WebP, conferidos pelo conteúdo (Pillow), não pela extensão nem pelo Content-Type;
- tamanho máximo por arquivo e proteção contra "bombas de descompressão";
- a imagem é reprocessada: rotação do celular aplicada, redimensionada e gravada como JPEG
  SEM metadados EXIF (que podem conter as coordenadas GPS de onde a foto foi tirada);
- nome gerado pelo sistema (uuid4) e arquivos guardados fora de /static (instance/uploads).
"""
import os
import re
import uuid
import warnings
from io import BytesIO

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS_ACEITOS = ("JPEG", "PNG", "WEBP")
EXTENSOES_ACEITAS = {"jpg", "jpeg", "png", "webp"}
LADO_MAXIMO = 1280
PIXELS_MAXIMOS = 40_000_000
NOME_VALIDO = re.compile(r"^[0-9a-f]{32}\.jpg$")

# Acima disso a Pillow avisa (e, com o dobro, recusa): protege contra imagens enormes que esgotam a memória.
Image.MAX_IMAGE_PIXELS = PIXELS_MAXIMOS


class FotoInvalida(Exception):
    """Arquivo recusado. A mensagem é mostrada ao usuário."""


def pasta_fotos():
    pasta = current_app.config["PASTA_FOTOS"]
    os.makedirs(pasta, exist_ok=True)
    return pasta


def caminho_foto(nome):
    if not NOME_VALIDO.match(nome or ""):
        raise FotoInvalida("Nome de arquivo inválido.")
    return os.path.join(pasta_fotos(), nome)


def arquivos_enviados(lista):
    """Ignora campos de arquivo vazios (o navegador envia um item vazio quando nada é escolhido)."""
    return [arquivo for arquivo in lista if arquivo and arquivo.filename]


def processar_foto(arquivo):
    """Valida, reprocessa e grava a foto. Devolve o nome do arquivo salvo."""
    rotulo = arquivo.filename or "arquivo"
    extensao = rotulo.rsplit(".", 1)[-1].lower() if "." in rotulo else ""
    if extensao not in EXTENSOES_ACEITAS:
        raise FotoInvalida(f'"{rotulo}" não é uma foto aceita. Envie JPG, PNG ou WebP.')

    limite = current_app.config["FOTO_TAMANHO_MAXIMO"]
    dados = arquivo.stream.read(limite + 1)
    if len(dados) > limite:
        raise FotoInvalida(f'"{rotulo}" passa de {limite // (1024 * 1024)} MB.')

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(dados), formats=FORMATOS_ACEITOS) as teste:
                teste.verify()  # confere a integridade do arquivo
            imagem = Image.open(BytesIO(dados), formats=FORMATOS_ACEITOS)
            imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as erro:
        raise FotoInvalida(f'"{rotulo}" não é uma imagem válida.') from erro

    imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    nome = f"{uuid.uuid4().hex}.jpg"
    imagem.save(os.path.join(pasta_fotos(), nome), "JPEG", quality=82, optimize=True)  # sem exif=...
    return nome


def apagar_fotos(nomes):
    for nome in nomes:
        try:
            os.remove(caminho_foto(nome))
        except (FileNotFoundError, FotoInvalida):
            pass

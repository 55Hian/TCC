"""Cadastro e consulta do catalogo de produtos."""
import psycopg
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from services.database import (
    atualizar_produto, criar_produto, listar_produtos, remover_produto,
)

router = APIRouter(prefix="/api/produtos", tags=["produtos"])


class ProdutoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    classe_modelo: str = Field(min_length=1, max_length=100)
    peso: float = Field(gt=0, description="Peso unitario na mesma unidade recebida da balanca")
    descricao: str = Field(default="", max_length=2000)
    ativo: bool = True


def _salvar(acao, *args):
    try:
        return acao(*args)
    except psycopg.errors.UniqueViolation as erro:
        raise HTTPException(status_code=409, detail="Ja existe um produto com essa classe do modelo") from erro
    except psycopg.Error as erro:
        raise HTTPException(status_code=503, detail="Banco indisponivel; produto nao foi salvo") from erro


@router.get("")
def listar():
    return {"produtos": _salvar(listar_produtos)}


@router.post("", status_code=201)
def criar(entrada: ProdutoEntrada):
    dados = entrada.model_dump()
    dados["nome"] = dados["nome"].strip()
    dados["classe_modelo"] = dados["classe_modelo"].strip()
    if not dados["nome"] or not dados["classe_modelo"]:
        raise HTTPException(status_code=422, detail="Nome e classe do modelo sao obrigatorios")
    return _salvar(criar_produto, dados)


@router.put("/{id_produto}")
def atualizar(id_produto: int, entrada: ProdutoEntrada):
    dados = entrada.model_dump()
    dados["nome"] = dados["nome"].strip()
    dados["classe_modelo"] = dados["classe_modelo"].strip()
    if not dados["nome"] or not dados["classe_modelo"]:
        raise HTTPException(status_code=422, detail="Nome e classe do modelo sao obrigatorios")
    produto = _salvar(atualizar_produto, id_produto, dados)
    if produto is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return produto


@router.delete("/{id_produto}", status_code=204)
def remover(id_produto: int):
    if not _salvar(remover_produto, id_produto):
        raise HTTPException(status_code=404, detail="Produto nao encontrado")
    return Response(status_code=204)

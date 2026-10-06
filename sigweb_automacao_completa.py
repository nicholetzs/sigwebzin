#!/usr/bin/env python3
"""
Automação completa do Sigweb (um comando só).

ETAPA 1 - Repo do GitLab com o block (gma-jdk-sigweb):
  a) Backup da pasta atual (libs que já estavam + libs novas), fora do git
     e sem precisar commitar (assim o block não atrapalha)
  b) Cria uma branch nova a partir da origin/develop
  c) Apaga tudo dela e joga as libs do backup
  d) Commit + push
  e) Mostra o nome da branch criada

ETAPA 2 - Repo SCM (gma-jdk-gestaoambiental):
  a) Deixa na branch feature/gma-sigweb-libs-deployer
  b) Apaga tudo (menos .git) e copia os arquivos do GitLab por cima
  c) git add -A, commit "Atualização do Sigweb DD/MM/AAAA", push

Uso:
  python sigweb_automacao_completa.py                 # roda as duas etapas
  python sigweb_automacao_completa.py --etapa 1       # só o GitLab
  python sigweb_automacao_completa.py --etapa 2       # só o SCM
  python sigweb_automacao_completa.py --dry-run       # só mostra o que faria
  python sigweb_automacao_completa.py --yes           # sem confirmação
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ======================= CONFIGURAÇÃO (ajuste aqui) =======================
# Etapa 1
REPO_BLOCK = Path(r"C:\el\projetos\workspace\gma-jdk-sigweb")   # pasta com o block
BASE_BRANCH = "develop"                                         # de onde a branch nasce
PREFIXO_BRANCH = "feature/gma-sigweb-libs-deployer"                # nome + data/hora
PASTA_BACKUP = Path(r"C:\el\projetos\backup-sigweb")            # backups ficam aqui
# Arquivos/pastas que compõem o block e NÃO devem ir para a branch nova
# (caminhos relativos à raiz do repo). Deixe vazio se o block não for arquivo.
BLOCK_ARQUIVOS = []

# Etapa 2
ORIGEM_GITLAB = Path(r"C:\el\projetos\workspace\gpi\gma\sigweb")
DESTINO_SCM = Path(r"C:\el\projetos\workspace\gma-jdk-gestaoambiental")  # ajuste o caminho
BRANCH_SCM = "feature/gma-sigweb-libs-deployer"
MENSAGEM_SCM = "Atualização do Sigweb {data}"
# ==========================================================================

DRY = False


def git(*args, cwd, check=True, capture=False):
    cmd = ["git", *args]
    print(f"$ [{cwd.name}] {' '.join(cmd)}")
    if DRY:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, cwd=cwd, check=check, text=True,
                          capture_output=capture)


def saida(*args, cwd):
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=cwd, text=True,
        capture_output=True, encoding="utf-8", errors="replace",
    ).stdout.strip()


RELATORIO = []


def log(msg=""):
    print(msg)
    RELATORIO.append(msg)


def relatorio_mudancas(repo: Path, titulo: str):
    """Lista o que vai no commit: NOVO, MODIFICADO, APAGADO, RENOMEADO."""
    log(f"\n--- {titulo} ---")
    if DRY:
        log("(dry-run) sem relatório de mudanças.")
        return
    linhas = saida("diff", "--cached", "--name-status", cwd=repo).splitlines()
    nomes = {"A": "NOVO", "M": "MODIFICADO", "D": "APAGADO",
             "R": "RENOMEADO", "T": "TIPO ALTERADO"}
    contagem = {}
    for linha in linhas:
        partes = linha.split("\t")
        st = partes[0][0]
        contagem[st] = contagem.get(st, 0) + 1
        log(f"  {nomes.get(st, st):<13} {' -> '.join(partes[1:])}")
    if not linhas:
        log("Nenhum arquivo alterado.")
        return
    resumo = ", ".join(f"{nomes.get(k, k)}: {v}" for k, v in sorted(contagem.items()))
    log(f"Total: {len(linhas)} arquivo(s)  ({resumo})")


def verificar_push(repo: Path, branch: str):
    """Confere se o commit local realmente chegou no remoto."""
    if DRY:
        return
    local = saida("rev-parse", "HEAD", cwd=repo)
    partes = saida("ls-remote", "origin", f"refs/heads/{branch}", cwd=repo).split()
    remoto = partes[0] if partes else ""
    if local and local == remoto:
        log(f"OK: push confirmado (commit {local[:10]} está no remoto).")
    else:
        log(f"ATENÇÃO: o remoto NÃO tem o seu commit "
            f"(local {local[:10]} / remoto {remoto[:10] or 'nada'}). Verifique o push.")


def _forcar(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def limpar(pasta: Path):
    for item in pasta.iterdir():
        if item.name == ".git":
            continue
        print(f"  apagando: {item.name}")
        if DRY:
            continue
        if item.is_dir():
            shutil.rmtree(item, onerror=_forcar)
        else:
            item.unlink()


def copiar(origem: Path, destino: Path):
    fonte = origem
    if DRY and not origem.exists() and destino.exists():
        fonte = destino
    for item in fonte.iterdir():
        if item.name == ".git":
            continue
        print(f"  copiando: {item.name}")
        if DRY:
            continue
        alvo = destino / item.name
        if item.is_dir():
            shutil.copytree(item, alvo)
        else:
            shutil.copy2(item, alvo)


# ------------------------------- ETAPA 1 --------------------------------
def etapa1():
    print("\n===== ETAPA 1: branch nova sem block =====")
    if not (REPO_BLOCK / ".git").is_dir():
        sys.exit(f"Não é um repo git: {REPO_BLOCK}")

    agora = datetime.now().strftime("%Y%m%d-%H%M")
    branch_nova = f"{PREFIXO_BRANCH}-{agora}"
    branch_atual = saida("rev-parse", "--abbrev-ref", "HEAD", cwd=REPO_BLOCK)
    commit_atual = saida("rev-parse", "HEAD", cwd=REPO_BLOCK)

    # a) backup fora do git (não depende de commit, então o block não atrapalha)
    destino_backup = PASTA_BACKUP / f"gma-jdk-sigweb-{agora}"
    print(f"\nBackup em: {destino_backup}")
    if not DRY:
        destino_backup.mkdir(parents=True, exist_ok=True)
    copiar(REPO_BLOCK, destino_backup)
    if not DRY:
        (destino_backup / "_backup_info.txt").write_text(
            f"branch: {branch_atual}\ncommit: {commit_atual}\ndata: {agora}\n",
            encoding="utf-8",
        )

    # b) branch nova a partir da develop (-f descarta o working tree, já salvo)
    git("fetch", "origin", cwd=REPO_BLOCK)
    git("checkout", "-f", "-B", branch_nova, f"origin/{BASE_BRANCH}", cwd=REPO_BLOCK)

    # c) apaga tudo e joga as libs do backup
    print("\nLimpando a branch nova...")
    limpar(REPO_BLOCK)
    print("\nCopiando libs do backup...")
    copiar(destino_backup, REPO_BLOCK)
    if not DRY:
        (REPO_BLOCK / "_backup_info.txt").unlink(missing_ok=True)
        for rel in BLOCK_ARQUIVOS:
            alvo = REPO_BLOCK / rel
            if alvo.is_dir():
                shutil.rmtree(alvo, onerror=_forcar)
            elif alvo.exists():
                alvo.unlink()
            print(f"  removido do block: {rel}")

    # d) commit + push
    git("add", "-A", cwd=REPO_BLOCK)
    relatorio_mudancas(REPO_BLOCK, "Arquivos que diferem da develop (o que a branch nova altera)")
    if not DRY and not saida("status", "--porcelain", cwd=REPO_BLOCK):
        print("Sem diferenças em relação à develop. Nada a commitar.")
        return branch_nova
    git("commit", "-m", f"Libs do Sigweb ({branch_atual}) sem block", cwd=REPO_BLOCK)
    git("push", "-u", "origin", branch_nova, cwd=REPO_BLOCK)
    verificar_push(REPO_BLOCK, branch_nova)

    # e) resultado
    log("\n" + "=" * 60)
    log(f"BRANCH CRIADA: {branch_nova}")
    log(f"Backup local : {destino_backup}")
    log("=" * 60)
    return branch_nova


# ------------------------------- ETAPA 2 --------------------------------
def etapa2():
    print("\n===== ETAPA 2: atualizar SCM =====")
    if not ORIGEM_GITLAB.is_dir():
        sys.exit(f"Origem não encontrada: {ORIGEM_GITLAB}")
    if not (DESTINO_SCM / ".git").is_dir():
        sys.exit(f"Destino não é repo git: {DESTINO_SCM}")

    atual = saida("rev-parse", "--abbrev-ref", "HEAD", cwd=DESTINO_SCM)
    if atual != BRANCH_SCM:
        git("fetch", "origin", cwd=DESTINO_SCM)
        existe = subprocess.run(
            ["git", "rev-parse", "--verify", BRANCH_SCM],
            cwd=DESTINO_SCM, capture_output=True,
        ).returncode == 0
        if existe:
            git("checkout", BRANCH_SCM, cwd=DESTINO_SCM)
        else:
            git("checkout", "-b", BRANCH_SCM, f"origin/{BRANCH_SCM}", cwd=DESTINO_SCM)
    git("pull", "--ff-only", cwd=DESTINO_SCM, check=False)

    print("\nLimpando SCM...")
    limpar(DESTINO_SCM)
    print("\nCopiando do GitLab...")
    copiar(ORIGEM_GITLAB, DESTINO_SCM)

    git("add", "-A", cwd=DESTINO_SCM)
    relatorio_mudancas(DESTINO_SCM, "Arquivos alterados no SCM (o que veio do GitLab)")
    if not DRY and not saida("status", "--porcelain", cwd=DESTINO_SCM):
        print("Sem mudanças no SCM. Nada a commitar.")
        return
    msg = MENSAGEM_SCM.format(data=datetime.now().strftime("%d/%m/%Y"))
    git("commit", "-m", msg, cwd=DESTINO_SCM)
    git("push", "origin", BRANCH_SCM, cwd=DESTINO_SCM)
    verificar_push(DESTINO_SCM, BRANCH_SCM)
    log(f"\nSCM atualizado na branch {BRANCH_SCM}.")


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", choices=["1", "2", "todas"], default="todas")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    DRY = args.dry_run

    print("Este script APAGA e recria o conteúdo das pastas de trabalho "
          "(o backup é feito antes).")
    if not DRY and not args.yes:
        if input("Continuar? [s/N] ").strip().lower() != "s":
            sys.exit("Cancelado.")

    try:
        if args.etapa in ("1", "todas"):
            etapa1()
        if args.etapa in ("2", "todas"):
            etapa2()
    except subprocess.CalledProcessError as e:
        log(f"\nERRO: o comando falhou: {' '.join(e.cmd)}")
        log("O processo foi interrompido. Seu backup (etapa 1) continua em "
            f"{PASTA_BACKUP}.")
        salvar_relatorio()
        sys.exit(1)

    salvar_relatorio()
    print("\nConcluído." if not DRY else "\n(dry-run) nada foi alterado.")


def salvar_relatorio():
    if DRY or not RELATORIO:
        return
    pasta = PASTA_BACKUP / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"relatorio-{datetime.now().strftime('%Y%m%d-%H%M')}.txt"
    arq.write_text("\n".join(RELATORIO), encoding="utf-8")
    print(f"Relatório salvo em: {arq}")


if __name__ == "__main__":
    main()
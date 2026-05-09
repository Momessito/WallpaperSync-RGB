# -*- coding: utf-8 -*-
"""
Gera certificado SSL confiavel pra localhost usando mkcert.
mkcert cria uma CA local que e confiavel por todo o sistema (incluindo Chromium embarcado).
"""

import os
import subprocess
import sys
import shutil
import urllib.request
import zipfile

CERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
CERT_FILE = os.path.join(CERT_DIR, "localhost.pem")
KEY_FILE = os.path.join(CERT_DIR, "localhost-key.pem")
MKCERT_EXE = os.path.join(CERT_DIR, "mkcert.exe")

MKCERT_URL = "https://dl.filippo.io/mkcert/latest?for=windows/amd64"


def download_mkcert():
    """Baixa o mkcert se nao existir."""
    if os.path.exists(MKCERT_EXE):
        return True

    os.makedirs(CERT_DIR, exist_ok=True)
    print("Baixando mkcert...")
    try:
        urllib.request.urlretrieve(MKCERT_URL, MKCERT_EXE)
        print("mkcert baixado com sucesso!")
        return True
    except Exception as e:
        print("Erro ao baixar mkcert: {}".format(e))
        print("Baixe manualmente de: https://github.com/FiloSottile/mkcert/releases")
        print("Coloque o .exe em: {}".format(CERT_DIR))
        return False


def setup_mkcert():
    """Instala a CA local do mkcert e gera certificado pra localhost."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print("Certificado ja existe em: {}".format(CERT_DIR))
        return True

    if not download_mkcert():
        return False

    print()
    print("Instalando CA local do mkcert (precisa de Administrador)...")
    result = subprocess.run([MKCERT_EXE, "-install"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Erro ao instalar CA: {}".format(result.stderr))
        print("Tente rodar como Administrador!")
        return False
    print(result.stdout)

    print("Gerando certificado pra localhost...")
    result = subprocess.run(
        [MKCERT_EXE, "-cert-file", CERT_FILE, "-key-file", KEY_FILE,
         "localhost", "127.0.0.1"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Erro: {}".format(result.stderr))
        return False

    print(result.stdout)
    print("Certificado gerado com sucesso!")
    return True


if __name__ == "__main__":
    if setup_mkcert():
        print()
        print("Tudo pronto! Agora rode: run_sync.bat")
    else:
        print()
        print("FALHOU - tente rodar como Administrador")
    input("Pressione Enter para sair...")

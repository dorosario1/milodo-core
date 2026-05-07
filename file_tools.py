from pathlib import Path

from logger import log_info, log_error, log_warn, log_debug


def read_file(path):
    file_path = Path(path)

    try:
        content = file_path.read_text(encoding="utf-8")
        log_debug(f"Fichier lu : {file_path}")
        return content
    except OSError as error:
        if not file_path.exists():
            log_warn(f"Fichier introuvable : {file_path}")
        log_error(f"Erreur fichier {file_path} : {error}")
        raise


def write_file(path, content):
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        log_info(f"Fichier écrit : {file_path}")
    except OSError as error:
        log_error(f"Erreur fichier {file_path} : {error}")
        raise


def append_file(path, content):
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("a", encoding="utf-8") as file:
            file.write(content)
        log_info(f"Fichier écrit : {file_path}")
    except OSError as error:
        log_error(f"Erreur fichier {file_path} : {error}")
        raise


def replace_in_file(path, old, new):
    file_path = Path(path)

    try:
        content = file_path.read_text(encoding="utf-8")
        log_debug(f"Fichier lu : {file_path}")
        updated_content = content.replace(old, new)
        file_path.write_text(updated_content, encoding="utf-8")
        log_info(f"Fichier écrit : {file_path}")
    except OSError as error:
        if not file_path.exists():
            log_warn(f"Fichier introuvable : {file_path}")
        log_error(f"Erreur fichier {file_path} : {error}")
        raise


def delete_file(path):
    file_path = Path(path)

    try:
        if not file_path.exists():
            log_warn(f"Fichier introuvable : {file_path}")
            return

        if not file_path.is_file():
            raise IsADirectoryError(f"Le chemin n'est pas un fichier: {file_path}")

        file_path.unlink()
        log_info(f"Fichier supprimé : {file_path}")
    except OSError as error:
        log_error(f"Erreur fichier {file_path} : {error}")
        raise


def exists(path):
    file_path = Path(path)
    result = file_path.exists()
    log_debug(f"Existence {file_path}: {result}")
    return result

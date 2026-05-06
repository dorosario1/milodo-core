from pathlib import Path


def read_file(path):
    file_path = Path(path)

    try:
        content = file_path.read_text(encoding="utf-8")
        print(f"Fichier lu: {file_path}")
        return content
    except OSError as error:
        print(f"Erreur lecture fichier: {file_path} ({error})")
        raise


def write_file(path, content):
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        print(f"Fichier ecrit: {file_path}")
    except OSError as error:
        print(f"Erreur ecriture fichier: {file_path} ({error})")
        raise


def append_file(path, content):
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("a", encoding="utf-8") as file:
            file.write(content)
        print(f"Contenu ajoute: {file_path}")
    except OSError as error:
        print(f"Erreur ajout fichier: {file_path} ({error})")
        raise


def replace_in_file(path, old, new):
    file_path = Path(path)

    try:
        content = file_path.read_text(encoding="utf-8")
        updated_content = content.replace(old, new)
        file_path.write_text(updated_content, encoding="utf-8")
        print(f"Texte remplace: {file_path}")
    except OSError as error:
        print(f"Erreur remplacement fichier: {file_path} ({error})")
        raise


def delete_file(path):
    file_path = Path(path)

    try:
        if not file_path.exists():
            print(f"Fichier absent, suppression ignoree: {file_path}")
            return

        if not file_path.is_file():
            raise IsADirectoryError(f"Le chemin n'est pas un fichier: {file_path}")

        file_path.unlink()
        print(f"Fichier supprime: {file_path}")
    except OSError as error:
        print(f"Erreur suppression fichier: {file_path} ({error})")
        raise


def exists(path):
    file_path = Path(path)
    result = file_path.exists()
    print(f"Existence {file_path}: {result}")
    return result

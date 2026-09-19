"""Validador de solo lectura para preservar la fuente autoritativa de en_orbita_golden_v2.jsonl."""

from scripts.validate_golden_dataset import validate_dataset


def main():
    print("Iniciando verificación de seguridad sobre el dataset v2 curado...")
    validate_dataset()


if __name__ == "__main__":
    main()

import re


def count_words(text: str) -> int:
    """Cuenta de forma determinista el número de palabras en un texto en español.

    Limpia signos de puntuación y divide por espacios en blanco.
    """
    if not text:
        return 0
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def calculate_estimated_duration(word_count: int, wpm: int = 150) -> float:
    """Calcula la duración estimada de locución en segundos basada en una velocidad de lectura fija.

    La velocidad predeterminada es de 150 palabras por minuto (WPM), estándar para narraciones divulgativas claras.
    """
    if word_count <= 0 or wpm <= 0:
        return 0.0
    seconds = (word_count / wpm) * 60.0
    return round(seconds, 1)

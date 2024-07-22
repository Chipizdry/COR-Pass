import string
import secrets
from cor_pass.schemas import PasswordGeneratorSettings, WordPasswordGeneratorSettings
from cor_pass.services import words

# Список слов для генерации паролей из слов / заменить на открытую базу слов
# WORDS_LIST = ["apple", "banana", "cherry", "date", "fig", "grape", "kiwi", "lemon", "mango", "nectarine", "orange", "papaya"]
WORDS_LIST = words.word_list

def generate_password(settings: PasswordGeneratorSettings) -> str:
    characters = ""
    if settings.include_uppercase:
        characters += string.ascii_uppercase
    if settings.include_lowercase:
        characters += string.ascii_lowercase
    if settings.include_digits:
        characters += string.digits
    if settings.include_special:
        characters += string.punctuation

    if not characters:
        raise ValueError("No characters available for password generation.")

    return ''.join(secrets.choice(characters) for _ in range(settings.length))



def generate_word_password(settings: WordPasswordGeneratorSettings):
    if settings.separator_hyphen:
        separator = "-"
    elif settings.separator_underscore:
        separator = "_"
    else:
        separator = ""

    filtered_words = [word for word in WORDS_LIST if word[0] in string.ascii_lowercase]
    if not settings.include_uppercase:
        words_list = filtered_words
    else:
        words_list = [word.capitalize() for word in filtered_words]

    password = separator.join(secrets.choice(words_list) for _ in range(settings.length))
    return password
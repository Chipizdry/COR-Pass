import re
from typing import List, Optional

def generate_ngrams(text: str, n: int = 2) -> List[str]:
    """
    Генерирует N-граммы из текста.
    Приводит текст к нижнему регистру и удаляет небуквенно-цифровые символы.
    Возвращает пустой список, если входной текст пуст или None.
    """
    if not text: 
        return []
    

    normalized_text = re.sub(r'[^a-zа-я0-9]', '', text.lower())
    
    if len(normalized_text) < n:
        return [normalized_text] if normalized_text else [] 
        
    ngrams = []
    for i in range(len(normalized_text) - n + 1):
        ngrams.append(normalized_text[i : i + n])
    return ngrams

def get_patient_search_tokens(
    first_name: Optional[str],
    last_name: Optional[str],
    middle_name: Optional[str] = None
) -> str: 
    """
    Объединяет токены для имени, фамилии и отчества.
    Поля с None или пустыми строками будут игнорироваться.
    """
    all_tokens = set() 
    

    if first_name:
        all_tokens.update(generate_ngrams(first_name, n=2))
        all_tokens.update(generate_ngrams(first_name, n=3))
    
    if last_name:
        all_tokens.update(generate_ngrams(last_name, n=2))
        all_tokens.update(generate_ngrams(last_name, n=3))


    if middle_name: 
        all_tokens.update(generate_ngrams(middle_name, n=2))
        all_tokens.update(generate_ngrams(middle_name, n=3))

    

    return " ".join(sorted(list(all_tokens)))
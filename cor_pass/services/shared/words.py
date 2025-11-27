word_file_path = "en-basic"


def get_word_list(word_file_path):
    with open(word_file_path, "r") as file:
        words_list = [line.strip() for line in file]
        return words_list


word_list = get_word_list(word_file_path)

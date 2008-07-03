def num(number,numlen):
    number=str(number)
    try:
        numlen = long(numlen)
    except ValueError:
        return number
    if len(number)<numlen:
        number='0' * (numlen - len(number)) + number
    if len(number)>numlen:
        while number.startswith('0') and len(number)>numlen:
            number=number[1:]
    return number

def what(number):
    return "this is not the shit" + str(number)

def titleCase(text, characters = ['.', '(', ')', ' ', '!']):
    text = [z for z in text]
    try:
        text[0] = text[0].upper()
    except IndexError:
        return ""
    for char in range(len(text)):
        try:
            if text[char] in characters:
                    text[char + 1] = text[char + 1].upper()
            else:
                text[char + 1] = text[char + 1].lower()
        except IndexError:
            pass
    return "".join(text)

def replaceAsWord(text, word, replaceword, characters = ['.', '(', ')', ' ', '!']):
    start = 0
    newtext = text
    while True:
        start = text.find(word, start)
        if start == -1:
            break
        end = start + len(word)
        if text[start - 1] in characters and text[start - 1] in characters:
            text = text.replace(text[start: end], replaceword)
        start = start + len(replaceword) + 1
    return text
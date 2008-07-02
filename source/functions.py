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


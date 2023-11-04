def QuestionsMarks(strParam):
    from string import ascii_letters
    # all_letters = ascii_letters + '?'
    for i, character in enumerate(strParam):
        if character.isdigit():
            count_question_marks = 0
            for c in strParam[i + 1:]:
                if c == '?':
                    count_question_marks += 1
                elif c.isdigit():
                    if count_question_marks >= 3 and int(c) + int(character) >= 10:
                        # character is the first then c must be the next
                        return True
                    else:
                        break
                else:
                    continue
    return False


def is_leap(year):
    """
    >>> is_leap(2000)
    True
    >>> is_leap(2400)
    True
    >>> is_leap(1800)
    False
    >>> is_leap(1900)
    False
    >>> is_leap(2100)
    False
    >>> is_leap(2200)
    False
    >>> is_leap(2300)
    False
    >>> is_leap(2500)
    False
    >>> is_leap(1992)
    True
    """
    is_leap = False

    if not year % 4:
        is_leap = True

        # It means that divided by 100 is not a Leap year
        if not year % 100:
            is_leap = False

            # It means that divided by 100 is not a Leap year
            if not year % 400:
                is_leap = True
            else:
                is_leap = False


    return is_leap


if __name__ == '__main__':
    print(QuestionsMarks('aa6?9'))

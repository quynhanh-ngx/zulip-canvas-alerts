import pprint
from lark import Lark

CASES = """\
message students with no submissions for lab
show me students with no submissions for assignment 1
message students with score < 70% on test 1
# extend deadline by 2 days for student_name
message students who did not attend the last lecture
message students who did not attend lecture on 7/30
show me comments on lab 2
# (a initialize command that asks for canvas keys, who tas are, list of students, etc)
# (commands to add student to list of students, etc)\
""".splitlines()

grammar = """
    sentence: action noun preposition condition? preposition? noun -> simple
    action: ACTION
    noun: adj? NOUN preposition? value?
    adj: ADJ
    preposition: PREPOSITION
    condition: CONDITION | binary_expr
    value: date | number | percentage | noun
    binary_expr: value comparator value
    number: NUMBER
    percentage: PERCENTAGE
    date: DATE
    comparator: COMPARATOR
    
    NUMBER: /\d+/
    DATE: /\d{1,2}\/\d{1,2}(\/\d{4})?/
    PERCENTAGE: /\d+%/
    COMPARATOR: /[<>=]/
    ACTION: "show me" | "message" | "extend"
    NOUN: "students" | "deadlines" | "comments" | "lab" | "assignment" | "test" | "lecture" | "score"
    ADJ: "last"
    PREPOSITION: "with" | "who" | "on" | "for" | "the" 
    CONDITION: "no submissions" | "did not attend"
    %import common.WS
    %ignore WS
"""
l = Lark(grammar, start='sentence', ambiguity='explicit')

for case in CASES:
    if case.startswith("#"):
        continue

    print(case)
    print(l.parse(case).pretty())
    print()
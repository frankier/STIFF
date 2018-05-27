import sys
import re


untok = open(sys.argv[1])
tok = open(sys.argv[2])

untok_line = untok.readline()
tok_line = tok.readline()
skipped = 0
while 1:
    tok_line_nospace = re.sub(r'\s', '', tok_line)
    untok_line_nospace = re.sub(r'\s', '', untok_line)
    #print('tok_line_nospace', tok_line_nospace)
    #print('untok_line_nospace', untok_line_nospace)
    if tok_line_nospace != untok_line_nospace:
        print(untok_line, end="")
        skipped += 1
    else:
        tok_line = tok.readline()
        skipped = 0
    untok_line = untok.readline()
    if tok_line == '':
        if untok_line == '':
            print('Ended cleanly')
            break
        else:
            print('Tok line ended first')
            break
    if skipped > 200:
        print('Skipped too much!')
        break

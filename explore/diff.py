import opencc
import sys
import re
import os

dir_path = os.path.dirname(os.path.realpath(__file__))

untok = open(sys.argv[1])
tok = open(sys.argv[2])

use_opencc = len(sys.argv) > 3
occ = None
if use_opencc:
    opencc_config = os.path.join(dir_path, "../t2s_char.json")
    occ = opencc.OpenCC(opencc_config)

untok_line = untok.readline()
tok_line = tok.readline()
skipped = 0
conversions = 0
try:
    while 1:
        if use_opencc:
            tok_line = occ.convert(tok_line)
            prev_untok_line = untok_line
            untok_line = occ.convert(untok_line)
            if untok_line != prev_untok_line:
                conversions += 1
        tok_line_nospace = re.sub(r"\s", "", tok_line)
        untok_line_nospace = re.sub(r"\s", "", untok_line)
        # print('tok_line_nospace', tok_line_nospace)
        # print('untok_line_nospace', untok_line_nospace)
        if tok_line_nospace != untok_line_nospace:
            print(untok_line, end="")
            skipped += 1
        else:
            tok_line = tok.readline()
            skipped = 0
        untok_line = untok.readline()
        if tok_line == "":
            if untok_line == "":
                print("Ended cleanly")
                break
            else:
                print("Tok line ended first")
                break
        if skipped > 200:
            print("Skipped too much!")
            break
finally:
    if use_opencc:
        print("Conversions:", conversions)

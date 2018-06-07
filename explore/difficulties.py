from sqlalchemy.sql import column
from cihai.core import Cihai
from cihai.bootstrap import bootstrap_unihan
from utils import parse_vars

print("References from https://www.unicode.org/reports/tr38/#N10211")

cihan = Cihai()
if not cihan.is_bootstrapped:
    bootstrap_unihan(cihan.metadata)

cihan.reflect_db()


double_var = (
    cihan.session.query(cihan.base.classes.Unihan)
    .filter(column("kTraditionalVariant").isnot(None))
    .filter(column("kSimplifiedVariant").isnot(None))
    .all()
)


print("## 3.7.1 bullet 4")

for c in double_var:
    print("Character: {}".format(c.char))
    trad = parse_vars(c.kTraditionalVariant)
    simp = parse_vars(c.kSimplifiedVariant)
    if c.char in trad and c.char in simp:
        print("Case 1")
    else:
        print("Case 2 (non-idempotent)")
    for trad_var in trad:
        print("s2t: {}".format(trad_var))
    for simp_var in simp:
        print("t2s: {}".format(simp_var))


def multi_list(field, max_freq_rank=1):
    multi_q = (
        cihan.session.query(cihan.base.classes.Unihan)
        .filter(column(field).like("% %"))
        .filter(column("kFrequency") <= max_freq_rank)
    )
    multi = multi_q.all()

    for c in multi:
        print("Character: {}".format(c.char))
        vars = parse_vars(getattr(c, field))
        for var in vars:
            print(var)


print("kTraditionalVariant")
multi_list("kTraditionalVariant")

print("kSimplifiedVariant")
multi_list("kSimplifiedVariant", max_freq_rank=3)

from sqlalchemy.sql import column
from cihai.core import Cihai
from cihai.bootstrap import bootstrap_unihan
from utils import parse_vars


cihan = Cihai()
if not cihan.is_bootstrapped:
    bootstrap_unihan(cihan.metadata)

cihan.reflect_db()


def variant_list(field):
    have_variants = [
        x
        for x in cihan.session.query(cihan.base.classes.Unihan).filter(
            column(field).isnot(None)
        )
    ]

    for c in have_variants:
        print("Character: {}".format(c.char))
        vars = parse_vars(getattr(c, field))
        for var in vars:
            print(var)


print("## ZVariants")
variant_list("kZVariant")

print("## kSemanticVariant")
variant_list("kSemanticVariant")

print("## kSpecializedSemanticVariant")
variant_list("kSpecializedSemanticVariant")

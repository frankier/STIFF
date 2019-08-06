cp -r $1 $2
poetry run scripts/munge.py senseval-rm-lemma --lemmas olla,ei $1/corpus.sup.xml $2/corpus.sup.xml $2/keys.pkl
poetry run scripts/munge.py senseval-rm-lemma --lemmas olla,ei $1/corpus.sup.seg.xml $2/corpus.sup.seg.xml
poetry run scripts/munge.py senseval-rm-lemma --lemmas olla,ei $1/corpus.sup.tag.xml $2/corpus.sup.tag.xml
poetry run scripts/munge.py key-rm-lemma --two $1/corpus.sup.key $2/corpus.sup.key $2/keys.pkl
poetry run scripts/munge.py key-rm-lemma --three $1/corpus.sup.3.key $2/corpus.sup.3.key $2/keys.pkl

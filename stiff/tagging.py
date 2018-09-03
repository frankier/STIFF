def same_tags(tags1, tags2):
    def filter_tags(tags):
        return [{k: v for k, v in t.items() if k != "id"} for t in tags]

    return filter_tags(tags1) == filter_tags(tags2)


class Tagging:
    def __init__(self, tokens=None):
        self.wnlemmas = {}
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = tokens
            for tok_idx, tok in enumerate(self.tokens):
                self._index_tags(tok_idx, tok["tags"])

    def _index_tags(self, tok_idx, tags):
        for tag in tags:
            for synset in tag["synset"]:
                self._index_lemma(tok_idx, synset)

    def _index_lemma(self, tok_idx, synset):
        self.wnlemmas[synset[1]] = (synset[0], tok_idx)

    def lemma_set(self):
        return set(self.wnlemmas.keys())

    def add_tags(self, token, anchors, tags):
        self.tokens.append({"token": token, "anchors": anchors, "tags": tags})
        self._index_tags(len(self.tokens) - 1, tags)

    def iter_tags(self):
        for token in self.tokens:
            for tag in token["tags"]:
                yield token, tag

    def _combine(self, other, matcher, combiner):
        num_tokens = len(self.tokens)
        tok = self.tokens[:]
        for t2 in other.tokens:
            combined = False
            for idx in range(0, num_tokens):
                if matcher(tok[idx], t2):
                    combined = True
                    combiner(tok[idx], t2)
                    break
            if not combined:
                tok.append(t2)
        return Tagging(tok)

    def combine_cross_wn(self, other):
        def match(t1, t2):
            assert len(t1["anchors"]) == 1
            assert len(t2["anchors"]) == 1
            return t1["token"] == t2["token"] and t1["anchors"][0] == t2["anchors"][0]

        def combine(t1, t2):
            if len(t1["tags"]) == 0 and len(t2["tags"]) == 0:
                return
            # XXX: Aribitrary limitation: Currently all lemmas must be the same
            lemma = t1["tags"][0]["lemma"] if t1["tags"] else t2["tags"][0]["lemma"]
            for other_tag in t2["tags"]:
                assert other_tag["lemma"] == lemma
                combined = False
                for tag in t1["tags"][:]:
                    assert tag["lemma"] == lemma
                    if other_tag["wnlemma"] == tag["wnlemma"]:
                        tag["wordnet"] |= other_tag["wordnet"]
                        combined = True
                if not combined:
                    t1["tags"].append(other_tag)

        return self._combine(other, match, combine)

    def combine_cross_toks(self, other, matcher):
        def match(untok_tok, tok_tok):
            # XXX: Aribitrary number of anchors required
            assert len(untok_tok["anchors"]) == 1
            assert len(tok_tok["anchors"]) == 1
            matched = untok_tok["token"] == tok_tok["token"] and matcher(
                untok_tok["anchors"][0], tok_tok["anchors"][0]
            )
            if matched:
                # XXX: Aribitrary ordering required
                assert same_tags(untok_tok["tags"], tok_tok["tags"])
                return True
            return False

        def combine(t1, t2):
            t1["token"] += t2["token"]

        return self._combine(other, match, combine)

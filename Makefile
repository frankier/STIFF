.SECONDARY:
.EXPORT_ALL_VARIABLES:

print-%:
	@echo $*=$($*)

## Environment variables -- overriding encouraged!

# Workdirs
WORK=work
STIFFWORK=${WORK}/stiff
EUROPARLWORK=${WORK}/eurosense
CORPUSPREVALWORK=${WORK}/corpus-pr-eval

# STIFF
OPENSUBS=${STIFFWORK}/cmn-fin
RAWSTIFF=${STIFFWORK}/stiff.raw.xml.zst
BP4=${STIFFWORK}/bp4.zst
BP4UNI=${STIFFWORK}/bp4.uni
BR4=${STIFFWORK}/br4.zst
BR4UNI=${STIFFWORK}/br4.uni
MANANN=finn-man-ann

# Eurosense
EUROSENSEHC=${EUROPARLWORK}/eurosense-hc.fixed.xml.zst
EUROSENSEHP=${EUROPARLWORK}/eurosense-hp.fixed.xml.zst
BABELWNMAP=${EUROPARLWORK}/babelwnmap.clean.tsv 
EUROSENSEUNI=${EUROPARLWORK}/eurosense.unified

# wsd-eval outputs
BP4EVAL=${STIFFWORK}/bp4-wsd-eval
BR4EVAL=${STIFFWORK}/br4-wsd-eval
EUROPARLEVAL=${EUROPARLWORK}/wsd-eval
EVALWORDS = ${WORK}/evalwords.pkl

# corpus-pr-eval outputs
CORPUSPREVALPLOT=${CORPUSPREVALWORK}/plot.pgf

## Top levels
.PHONY: all wsd-eval stiff-wsd-eval corpus-eval
all: wsd-eval corpus-eval
wsd-eval: stiff-wsd-eval ${EUROPARLEVAL}/trainf
stiff-wsd-eval: ${BP4EVAL}/trainf ${BR4EVAL}/trainf
corpus-eval: ${CORPUSPREVALPLOT}

## Directory creation
${STIFFWORK} ${EUROPARLWORK} ${CORPUSPREVALWORK} ${CORPUSPREVALWORK}/eurosense-pr:
	mkdir -p $@

## Finn-man-ann preparation

# Fetch finn-man-ann
${MANANN}/ann.xml:
	git clone https://github.com/frankier/finn-man-ann.git ${MANANN}

# Calling into Makefile.manann
${STIFFWORK}/%: ${MANANN}/ann.xml | ${STIFFWORK}
	${MAKE} WORK=${STIFFWORK} SOURCE="OpenSubtitles2018" INPUT_FMT="man-ann-stiff" -f Makefile.manann $@

${EUROPARLWORK}/%: ${MANANN}/ann.xml | ${EUROPARLWORK}
	${MAKE} WORK=${EUROPARLWORK} SOURCE="europarl" INPUT_FMT="man-ann-europarl" -f Makefile.manann $@

## STIFF preparation

# Fetch OpenSubtitles2018
${OPENSUBS}:
	python scripts/fetch_opensubtitles2018.py $@

# Make raw STIFF
${RAWSTIFF}: ${OPENSUBS} | ${STIFFWORK}
	python scripts/pipeline.py mk-stiff $< $@

## Eurosense preparation

# Fetch eurosense-hp.fixed
${EUROSENSEHP}:
	wget https://archive.org/download/eurosense-hp.fixed.xml/eurosense-hp.fixed.xml.zstd -O $@

${EUROSENSEHC}:
	wget https://archive.org/download/eurosense-hp.fixed.xml/eurosense-hc.fixed.xml.zstd -O $@

# Convert Eurosense => unified
${EUROSENSEUNI}.target: ${EUROSENSEHP} ${BABELWNMAP}
	python scripts/pipeline.py eurosense2unified \
		--babel2wn-map=${BABELWNMAP} \
		${EUROSENSEHP} ${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key
	touch $@ ${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key

${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key: ${EUROSENSEUNI}.target

## Evaluation creation

# STIFF
${BP4EVAL}: ${RAWSTIFF} ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.xml ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.key
	${MAKE} VAR=${BP4} VARUNI=${BP4UNI} VARLONG="bilingual-precision-4" VAREVAL=$@ -f Makefile.var $@

${BR4EVAL}: ${RAWSTIFF} ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.xml ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.key
	${MAKE} VAR=${BR4} VARUNI=${BR4UNI} VARLONG="bilingual-recall-4" VAREVAL=$@ -f Makefile.var $@

# Eurosense
${EUROPARLEVAL}: ${EUROSENSEUNI}.xml ${EUROPARLWORK}/man-ann-europarl.uni.xml ${EUROSENSEUNI}.key ${EUROPARLWORK}/man-ann-europarl.uni.key
	python scripts/pipeline.py unified-auto-man-to-evals $^ $@

# Training data filtering
${EVALWORDS}: ${BP4EVAL} ${BR4EVAL} ${EUROPARLEVAL}
	python scripts/munge.py extract-words \
		${BP4EVAL}/test/corpus.sup.xml ${BP4EVAL}/dev/corpus.sup.xml \
		${BR4EVAL}/test/corpus.sup.xml ${BR4EVAL}/dev/corpus.sup.xml \
		${EUROPARLEVAL}/test/corpus.sup.xml ${EUROPARLEVAL}/dev/corpus.sup.xml $@

${BP4EVAL}/trainf: ${EVALWORDS} ${BP4EVAL}
	mkdir -p $@
	python scripts/pipeline.py train-filter filter ${BP4EVAL}/train $@ $<

${BR4EVAL}/trainf: ${EVALWORDS} ${BR4EVAL}
	mkdir -p $@
	python scripts/pipeline.py train-filter filter ${BR4EVAL}/train $@ $<

${EUROPARLEVAL}/trainf: ${EVALWORDS} ${EUROPARLEVAL}
	mkdir -p $@
	python scripts/pipeline.py train-filter filter ${EUROPARLEVAL}/train $@ $<

## Make STIFF and EuroSense P/R plot

# STIFF data
${CORPUSPREVALWORK}/stiff-eval-out: ${RAWSTIFF} | ${CORPUSPREVALWORK}
	python scripts/variants.py eval $< $@

${CORPUSPREVALWORK}/stiff-eval.csv: ${STIFFWORK}/man-ann-OpenSubtitles2018.xml ${CORPUSPREVALWORK}/stiff-eval-out
	python scripts/eval.py pr-eval --score=tok $^ $@

# Eurosense data
${EUROPARLWORK}/man-ann-europarl.synset.xml: ${EUROPARLWORK}/man-ann-europarl.xml 
	python scripts/munge.py lemma-to-synset $< $@

${CORPUSPREVALWORK}/eurosense-pr/EC.xml: ${EUROSENSEHC} ${BABELWNMAP} | ${CORPUSPREVALWORK}/eurosense-pr
	python scripts/pipeline.py eurosense2stifflike \
		--head 1000 \
		--babel2wn-map=${BABELWNMAP} $< $@

${CORPUSPREVALWORK}/eurosense-pr/EP.xml: ${EUROSENSEHP} ${BABELWNMAP} | ${CORPUSPREVALWORK}/eurosense-pr
	python scripts/pipeline.py eurosense2stifflike \
		--head 1000 \
		--babel2wn-map=${BABELWNMAP} $< $@

${CORPUSPREVALWORK}/europarl-eval.csv: ${EUROPARLWORK}/man-ann-europarl.synset.xml ${CORPUSPREVALWORK}/eurosense-pr/EC.xml  ${CORPUSPREVALWORK}/eurosense-pr/EP.xml
	python scripts/eval.py pr-eval --score=tok $< ${CORPUSPREVALWORK}/eurosense-pr/ $@

# Plot
${CORPUSPREVALPLOT}: ${CORPUSPREVALWORK}/stiff-eval.csv ${CORPUSPREVALWORK}/europarl-eval.csv
	python scripts/eval.py pr-plot --out $@ $^

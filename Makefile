.SECONDARY:
.EXPORT_ALL_VARIABLES:

## Environment variables -- overriding encouraged!

# Workdirs
WORK=work
STIFFWORK=${WORK}/stiff
EUROPARLWORK=work/eurosense
CORPUSPREVALWORK=work/corpus-pr-eval

# STIFF
OPENSUBS=${STIFFWORK}/cmn-fin
RAWSTIFF=${STIFFWORK}/stiff.raw.xml.zst
BP6=${STIFFWORK}/bp6.zst
BP6UNI=${STIFFWORK}/bp6.uni
MANANN=finn-man-ann

# Eurosense
EUROSENSEHC=${EUROPARLWORK}/eurosense-hc.fixed.xml.zstd
EUROSENSEHP=${EUROPARLWORK}/eurosense-hp.fixed.xml.zstd
BABELWNMAP=${EUROPARLWORK}/babelwnmap.clean.tsv 
EUROSENSEUNI=${EUROPARLWORK}/eurosense.unified

# wsd-eval outputs
STIFFEVAL=${STIFFWORK}/wsd-eval
EUROPARLEVAL=${EUROPARLWORK}/wsd-eval

# corpus-pr-eval outputs
CORPUSPREVALPLOT=${CORPUSPREVALWORK}/plot.pgf

## Top levels
.PHONY: all wsd-eval corpus-eval
all: wsd-eval corpus-eval
wsd-eval: ${STIFFEVAL} ${EUROPARLEVAL}
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
	make WORK=${STIFFWORK} SOURCE="OpenSubtitles2018" S2U_FLAG="--man-ann" -f Makefile.manann $@

${EUROPARLWORK}/%: ${MANANN}/ann.xml | ${EUROPARLWORK}
	make WORK=${EUROPARLWORK} SOURCE="europarl" S2U_FLAG="--eurosense" -f Makefile.manann $@

## STIFF preparation

# Fetch OpenSubtitles2018
${OPENSUBS}:
	python scripts/fetch_opensubtitles2018.py $@

# Make raw STIFF
${RAWSTIFF}: ${OPENSUBS}
	python scripts/pipeline.py mk-stiff $< $@

# Make recommended STIFF variant
${BP6}: ${RAWSTIFF}
	python scripts/variants.py proc \
		bilingual-precision-6 $< $@

# Convert STIFF => unified
${BP6UNI}.target: ${BP6}
	python scripts/pipeline.py stiff2unified \
		$< ${BP6UNI}.xml ${BP6UNI}.key
	touch $@ ${BP6UNI}.xml ${BP6UNI}.key

${BP6UNI}.xml ${BP6UNI}.key: ${BP6UNI}.target

## Eurosense preparation

# Fetch eurosense-hp.fixed
${EUROSENSEHP}:
	wget https://archive.org/download/eurosense-hp.fixed.xml/eurosense-hp.fixed.xml.zstd $@

# Convert Eurosense => unified
${EUROSENSEUNI}.target: ${EUROSENSEHP} ${BABELWNMAP}
	python scripts/pipeline.py eurosense2unified \
		--babel2wn-map=${BABELWNMAP} \
		${EUROSENSEHP} ${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key
	touch $@ ${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key

${EUROSENSEUNI}.xml ${EUROSENSEUNI}.key: ${EUROSENSEUNI}.target

## Evaluation creation

# STIFF
${STIFFEVAL}: ${BP6UNI}.xml ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.xml ${BP6UNI}.key ${STIFFWORK}/man-ann-OpenSubtitles2018.uni.key
	python scripts/pipeline.py unified-auto-man-to-evals $^ $@

# Eurosense
${EUROPARLEVAL}: ${EUROSENSEUNI}.xml ${EUROPARLWORK}/man-ann-europarl.uni.xml ${EUROSENSEUNI}.key ${EUROPARLWORK}/man-ann-europarl.uni.key
	python scripts/pipeline.py unified-auto-man-to-evals $^ $@

## Make STIFF and EuroSense P/R plot

# STIFF data
${CORPUSPREVALWORK}/stiff-eval-out: ${RAWSTIFF}
	python scripts/variants.py eval $< $@

${CORPUSPREVALWORK}/stiff-eval.csv: ${STIFFWORK}/man-ann-OpenSubtitles2018.xml ${CORPUSPREVALWORK}/stiff-eval-out
	python scripts/eval.py pr-eval --score=tok $^ $@

# Eurosense data
${EUROPARLWORK}/man-ann-europarl.synset.xml: ${EUROPARLWORK}/man-ann-europarl.xml 
	python scripts/munge.py lemma-to-synset $< $@

${CORPUSPREVALWORK}/eurosense-pr/EC.xml: ${EUROSENSEHC}
	ln -sf ${EUROSENSEHC} eurosense-pr/EC.xml

${CORPUSPREVALWORK}/eurosense-pr/EP.xml: ${EUROSENSEHP}
	ln -sf ${EUROSENSEHP} eurosense-pr/EP.xml

${CORPUSPREVALWORK}/europarl-eval.csv: ${EUROPARLWORK}/man-ann-europarl.xml ${CORPUSPREVALWORK}/eurosense-pr
	python scripts/eval.py pr-eval --score=tok $^ $@

# Plot
${CORPUSPREVALPLOT}: ${CORPUSPREVALWORK}/stiff-eval.csv ${CORPUSPREVALWORK}/europarl-eval.csv
	python scripts/eval.py pr-plot $^ $@
